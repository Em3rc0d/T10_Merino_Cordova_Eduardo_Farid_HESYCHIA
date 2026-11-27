#!/usr/bin/env python3
"""One-shot HESYCHIA PI15 confirmatory campaign: CNN vs DSP vs Oracle.

Requires a PI15 external freeze created before inference. On first invocation it
writes a test-open receipt BEFORE reading external PCM. The run is never tuned or
repeated based on results; negative outcomes are valid scientific results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = LAB_ROOT / "src"
for _path in (LAB_ROOT, SRC_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np
import soundfile as sf
import torch
from pystoi import stoi as stoi_metric

try:
    from pesq import pesq as pesq_metric
except ImportError:  # PESQ is supplemental; the confirmatory primary analysis must still run.
    pesq_metric = None

from src.dsp_class_template import ClassTemplateDSP
from src.m4_scientific.corpus import SR, TARGETS
from src.m4_scientific.evaluation import attenuation, si_sdr
from src.m4_scientific.model import features, load_checkpoint, spectrum, synthesize
from pi14_analysis_v2 import analyze, cluster_intervals

EPS=1e-9


def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def read_rows(path: Path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    return rows


def map_rows(path: Path):
    rows=read_rows(path)
    d={r["candidate_id"]:r for r in rows}
    if len(d)!=len(rows):
        raise ValueError("duplicate candidate_id")
    return d


def resolve_pcm(manifest: Path,row: dict):
    p=Path(row["pcm_path"])
    return p if p.is_absolute() else (manifest.resolve().parent/p).resolve()


def load_pcm(manifest: Path,row: dict):
    p=resolve_pcm(manifest,row)
    if sha256(p).lower()!=row["pcm_sha256"].strip().lower():
        raise ValueError(f"PCM hash changed after freeze: {row['candidate_id']}")
    x,rate=sf.read(p,dtype="float32",always_2d=False)
    if rate!=SR or x.ndim!=1 or len(x)!=SR*4 or not np.isfinite(x).all():
        raise ValueError(f"invalid frozen PCM: {row['candidate_id']}")
    return np.asarray(x,dtype=np.float32)


def to_rms(x: np.ndarray, dbfs: float):
    y=np.asarray(x,dtype=np.float32)-np.float32(np.mean(x,dtype=np.float64))
    rms=float(np.sqrt(np.mean(y.astype(np.float64)**2)+EPS))
    if rms<1e-5:
        raise ValueError("near-silent frozen stem")
    desired=10**(float(dbfs)/20.0)
    return (y*(desired/rms)).astype(np.float32)


def mix_sha(x):
    return hashlib.sha256(np.asarray(x,dtype="<f4").tobytes()).hexdigest()


def process_gain(mix,target,speech,gain):
    waves=torch.from_numpy(np.stack([mix,target,speech]).astype(np.float32))
    specs=spectrum(waves)
    with torch.no_grad():
        out=synthesize(specs*gain[None],len(mix)).cpu().numpy()
    return out[0],out[1],out[2]


def power_snr_db(signal, noise):
    signal_power=float(np.mean(np.asarray(signal,dtype=np.float64)**2))
    noise_power=float(np.mean(np.asarray(noise,dtype=np.float64)**2))
    if signal_power <= EPS or noise_power <= EPS:
        return None
    return float(10.0*np.log10(signal_power/noise_power))


def speech_quality_metrics(reference, degraded):
    ref=np.asarray(reference,dtype=np.float64)
    deg=np.asarray(degraded,dtype=np.float64)
    value={
        "stoi_protected":float(stoi_metric(ref,deg,SR,extended=False)),
        "pesq_wb_protected":None,
        "pesq_available":pesq_metric is not None,
        "pesq_status":"NOT_INSTALLED" if pesq_metric is None else "PENDING",
    }
    if pesq_metric is not None:
        # P.862/PESQ is reported only as a supplemental jury metric. It is not
        # used for the pre-specified H1/H0 decision. A PESQ-specific failure
        # must not invalidate or force a rerun of the one-shot primary test.
        try:
            value["pesq_wb_protected"]=float(
                pesq_metric(SR,np.clip(ref,-1.0,1.0),np.clip(deg,-1.0,1.0),"wb")
            )
            value["pesq_status"]="OK"
        except Exception as exc:
            value["pesq_status"]="ERROR_"+type(exc).__name__
    return value


def metrics(mix,target,speech,gain):
    out,target_out,speech_out=process_gain(mix,target,speech,gain)
    at=attenuation(target,target_out)
    ap=attenuation(speech,speech_out)
    before=si_sdr(mix,speech)
    after=si_sdr(out,speech)
    snr_before=power_snr_db(speech,target)
    snr_after=power_snr_db(speech_out,target_out)
    quality=speech_quality_metrics(speech,speech_out)
    return {
        "a_target_db":at,
        "a_protected_db":ap,
        "si_sdri_protected_db":(
            after-before if before is not None and after is not None else None
        ),
        "snr_protected_vs_target_db":snr_after,
        "snr_improvement_db":(
            snr_after-snr_before if snr_before is not None and snr_after is not None else None
        ),
        **quality,
        "max_abs_output":float(np.max(np.abs(out))),
        "gain_mean":float(gain.mean().item()),
    }


def verify_freeze(freeze_path: Path):
    frozen=json.loads(freeze_path.read_text(encoding="utf-8"))
    if frozen.get("status")!="FROZEN_NOT_OPENED" or frozen.get("test_opened") is not False:
        raise ValueError("freeze is not unopened")
    for name,path in frozen["artifact_paths"].items():
        p=Path(path)
        if not p.is_file() or sha256(p)!=frozen["artifact_sha256"][name]:
            raise ValueError(f"frozen artifact changed: {name}")
    return frozen


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    frozen=verify_freeze(a.freeze)
    if a.out.exists():
        raise ValueError("confirmatory output already exists; one-shot run refuses overwrite")
    receipt=a.freeze.with_suffix(a.freeze.suffix+".TEST_OPENED.json")
    if receipt.exists():
        raise ValueError("test was already opened; do not rerun/tune on this cohort")

    a.out.mkdir(parents=True,exist_ok=False)
    with receipt.open("x",encoding="utf-8") as f:
        json.dump({
            "schema":"hesychia.pi15-test-open-receipt.v1",
            "status":"TEST_OPENED_DO_NOT_TUNE",
            "opened_at_utc":datetime.now(timezone.utc).isoformat(),
            "freeze_sha256":sha256(a.freeze),
            "output":str(a.out.resolve()),
        },f,indent=2)
        f.write("\n")

    paths={k:Path(v) for k,v in frozen["artifact_paths"].items()}
    target_manifest=paths["target_manifest"]
    speech_manifest=paths["speech_manifest"]
    targets=map_rows(target_manifest)
    speeches=map_rows(speech_manifest)
    dsp=ClassTemplateDSP.from_npz(paths["dsp_templates"])
    model,obj=load_checkpoint(paths["checkpoint"])
    model.eval()
    torch.set_num_threads(4)

    rows=[]
    cp02=[]
    cp10=[]
    for scene in frozen["scenes"]:
        tr=targets[scene["target_candidate_id"]]
        sr=speeches[scene["speech_candidate_id"]]
        speech=to_rms(load_pcm(speech_manifest,sr),scene["speech_rms_dbfs"])
        target=to_rms(
            load_pcm(target_manifest,tr),
            scene["speech_rms_dbfs"]+scene["target_relative_db"]
        )
        mix=(speech+target).astype(np.float32)
        peak=float(np.max(np.abs(mix)))
        if peak>float(frozen["scene_rule"]["fail_on_abs_peak_gt"]):
            raise ValueError(f"pre-specified mixture clips: {scene['scene_id']} peak={peak}")
        mh=mix_sha(mix)
        target_id=TARGETS.index(scene["target_class"])
        spec=spectrum(torch.from_numpy(mix))[0]
        feat=features(spec)[None]
        label=torch.tensor([target_id],dtype=torch.long)

        with torch.no_grad():
            cnn_mask=model(feat,label)[0]
            cnn_gain=model.gain(cnn_mask)
            wrong_label=torch.tensor([1-target_id],dtype=torch.long)
            wrong_gain=model.gain(model(feat,wrong_label)[0])

        dsp_mask=dsp.predict(mix,target_id)
        dsp_gain=torch.from_numpy(dsp.gain(dsp_mask))

        target_spec=spectrum(torch.from_numpy(target))[0]
        speech_spec=spectrum(torch.from_numpy(speech))[0]
        target_ratio=target_spec.abs()/(target_spec.abs()+speech_spec.abs()+1e-8)
        oracle_gain=(1.0-target_ratio).clamp_min(10**(-12/20))

        method_gains={"CNN":cnn_gain,"DSP":dsp_gain,"ORACLE":oracle_gain}
        scene_hashes=set()
        cnn_correct=None
        for method,gain in method_gains.items():
            m=metrics(mix,target,speech,gain)
            row={
                "scene_id":scene["scene_id"],
                "source_group":scene["source_group"],
                "speaker_group":scene["speaker_group"],
                "target_class":scene["target_class"],
                "target_candidate_id":scene["target_candidate_id"],
                "speech_candidate_id":scene["speech_candidate_id"],
                "target_relative_db":scene["target_relative_db"],
                "mix_sha256":mh,
                "method":method,
                **m,
            }
            rows.append(row)
            scene_hashes.add(row["mix_sha256"])
            if method=="CNN":
                cnn_correct=m["a_target_db"]
        if len(scene_hashes)!=1:
            raise AssertionError("CP10 failed: method mixtures differ")

        wrong=metrics(mix,target,speech,wrong_gain)
        cp02.append({
            "scene_id":scene["scene_id"],
            "source_group":scene["source_group"],
            "speaker_group":scene["speaker_group"],
            "target_class":scene["target_class"],
            "mix_sha256":mh,
            "a_target_correct_db":cnn_correct,
            "a_target_permuted_db":wrong["a_target_db"],
            "delta_correct_minus_permuted_db":cnn_correct-wrong["a_target_db"],
            "a_protected_permuted_db":wrong["a_protected_db"],
        })
        cp10.append({"scene_id":scene["scene_id"],"mix_sha256":mh,"methods":"CNN,DSP,ORACLE","pass":True})

    by_scene=a.out/"confirmatory_by_scene.csv"
    with by_scene.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()),lineterminator="\n")
        w.writeheader();w.writerows(rows)

    cp02_csv=a.out/"cp02_by_scene.csv"
    with cp02_csv.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(cp02[0].keys()),lineterminator="\n")
        w.writeheader();w.writerows(cp02)

    with (a.out/"cp10_report.json").open("w",encoding="utf-8") as f:
        json.dump({
            "schema":"hesychia.cp10.v1","status":"COMPLETE","scenes":len(cp10),
            "identical_mix_sha256_for_all_methods":True,
            "unique_mixtures":len({r["mix_sha256"] for r in cp10})
        },f,indent=2);f.write("\n")

    analysis=analyze(by_scene,seed=20261117,n_boot=10000,voice_margin_db=1.0)
    (a.out/"confirmatory_analysis.json").write_text(
        json.dumps(analysis,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    deltas=np.array([r["delta_correct_minus_permuted_db"] for r in cp02],dtype=float)
    groups=[r["source_group"] for r in cp02]
    cp02_stats=cluster_intervals(deltas,groups,seed=20261119,n_boot=10000)
    cp02_report={
        "schema":"hesychia.cp02.v1",
        "status":"COMPLETE",
        "scene_count":len(cp02),
        "source_group_count":len(set(groups)),
        "correct_minus_permuted_target_db":cp02_stats,
        "criterion":"lower one-sided 95% BCa bound > 0 dB",
        "criterion_met":cp02_stats["bca_one_sided95"]["lower"]>0.0,
        "interpretation":(
            "Target conditioning demonstrated under the pre-specified criterion."
            if cp02_stats["bca_one_sided95"]["lower"]>0.0
            else "Pre-specified evidence for effective target conditioning was not established."
        ),
    }
    (a.out/"cp02_report.json").write_text(
        json.dumps(cp02_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    run_manifest={
        "schema":"hesychia.pi15-confirmatory-run.v1",
        "status":"COMPLETE_DO_NOT_TUNE",
        "freeze_sha256":sha256(a.freeze),
        "checkpoint_sha256":sha256(paths["checkpoint"]),
        "dsp_templates_sha256":sha256(paths["dsp_templates"]),
        "scene_count":len(frozen["scenes"]),
        "source_group_count":len({s["source_group"] for s in frozen["scenes"]}),
        "speaker_group_count":len({s["speaker_group"] for s in frozen["scenes"]}),
        "outputs":{p.name:sha256(p) for p in sorted(a.out.iterdir()) if p.is_file()},
        "joint_decision":analysis["joint_decision"],
        "cp02_criterion_met":cp02_report["criterion_met"],
        "supplemental_signal_metrics":{
            "snr":True,
            "si_sdri":True,
            "stoi":True,
            "pesq_wb":pesq_metric is not None,
            "decision_role":"descriptive_only_not_used_for_H1_H0",
        },
        "note":"Negative H1/CP02 outcomes remain valid final results; no rerun for tuning is permitted.",
    }
    (a.out/"run_manifest.json").write_text(
        json.dumps(run_manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        "status":run_manifest["status"],
        "scenes":run_manifest["scene_count"],
        "joint_decision":run_manifest["joint_decision"],
        "cp02_criterion_met":run_manifest["cp02_criterion_met"],
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
