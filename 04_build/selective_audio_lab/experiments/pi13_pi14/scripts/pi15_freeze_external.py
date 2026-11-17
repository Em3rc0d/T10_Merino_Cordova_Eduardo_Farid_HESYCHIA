#!/usr/bin/env python3
"""Freeze the independent HESYCHIA PI15 confirmatory cohort before inference.

This command validates and hashes the already human-approved external target and
speech PCM, the frozen DSP templates, checkpoint and analysis code. It creates a
deterministic scene plan but NEVER runs CNN/DSP/Oracle inference.
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

import soundfile as sf

from src.dsp_class_template import ClassTemplateDSP
from src.m4_scientific.corpus import SR, TARGETS
from src.m4_scientific.model import load_checkpoint, frontend_contract

EXPECTED_CHECKPOINT = "c0b34027fe1d4165b062f4145ca7173b3d547cedc39846e17298295e99fb1966"
EXPECTED_FRAMES = SR * 4


def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def load_rows(path: Path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"empty manifest: {path}")
    return rows


def resolve_pcm(manifest: Path, value: str):
    p=Path(value)
    return p if p.is_absolute() else (manifest.resolve().parent/p).resolve()


def validate_pcm(manifest: Path, row: dict):
    raw=row.get("pcm_path","").strip()
    digest=row.get("pcm_sha256","").strip().lower()
    if not raw or len(digest)!=64:
        raise ValueError("pcm_path/pcm_sha256 required for every frozen row")
    path=resolve_pcm(manifest,raw)
    if not path.is_file() or sha256(path).lower()!=digest:
        raise ValueError(f"PCM missing/hash mismatch: {row.get('candidate_id')}")
    info=sf.info(path)
    if info.samplerate!=SR or info.channels!=1 or info.frames!=EXPECTED_FRAMES:
        raise ValueError(
            f"Frozen PCM must be mono {SR} Hz exactly 4 s: {row.get('candidate_id')}"
        )
    return path


def normalize_target(value: str):
    v=value.strip().lower()
    if v=="vacuum_cleaner":
        return "vacuum_cleaner"
    if v=="chainsaw":
        return "chainsaw"
    raise ValueError(f"unsupported target class: {value}")


def require_human_status(row, *, speech=False):
    status=row.get("human_audit_status","").strip().upper()
    allowed={"ELIGIBLE","DATASET_VERIFIED"} if speech else {"ELIGIBLE"}
    if status not in allowed:
        raise ValueError(f"external PCM not approved for freeze: {row.get('candidate_id')}={status}")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target-manifest",type=Path,required=True)
    p.add_argument("--speech-manifest",type=Path,required=True)
    p.add_argument("--dsp-templates",type=Path,required=True)
    p.add_argument("--checkpoint",type=Path,required=True)
    p.add_argument("--kappa-report",type=Path,required=True)
    p.add_argument("--contamination-report",type=Path,required=True)
    p.add_argument("--campaign-script",type=Path,required=True)
    p.add_argument("--analysis-script",type=Path,required=True)
    p.add_argument("--dsp-code",type=Path,required=True)
    p.add_argument("--dsp-config",type=Path,required=True)
    p.add_argument("--metric-protocol",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():
        raise ValueError("refusing to overwrite freeze")

    kappa=json.loads(a.kappa_report.read_text(encoding="utf-8"))
    kval=kappa.get("cohen_kappa",kappa.get("kappa"))
    if kappa.get("pairs")!=93 or kval is None:
        raise ValueError("kappa report must contain 93 paired human reviews")
    if float(kval)<0.60:
        raise ValueError("kappa <0.60; adjudication/review must be resolved before freeze")
    contamination=json.loads(a.contamination_report.read_text(encoding="utf-8"))
    if contamination.get("n")!=93 or "ci95" not in contamination:
        raise ValueError("contamination report does not close the 93-record audit")

    checkpoint_sha=sha256(a.checkpoint)
    if checkpoint_sha!=EXPECTED_CHECKPOINT:
        raise ValueError("checkpoint differs from validation-selected M4")
    _,obj=load_checkpoint(a.checkpoint)
    if obj.get("frontend")!=frontend_contract():
        raise ValueError("checkpoint frontend mismatch")
    dsp=ClassTemplateDSP.from_npz(a.dsp_templates)
    if dsp.metadata.get("frontend")!=frontend_contract():
        raise ValueError("DSP/CNN frontend parity failed")

    targets=load_rows(a.target_manifest)
    speeches=load_rows(a.speech_manifest)
    tgroups=set()
    classes=set()
    target_entries=[]
    for row in targets:
        require_human_status(row)
        cls=normalize_target(row.get("target_class",""))
        group=row.get("source_group","").strip()
        cid=row.get("candidate_id","").strip()
        if not group or not cid or group in tgroups:
            raise ValueError("target source_group/candidate_id missing or duplicate group")
        validate_pcm(a.target_manifest,row)
        tgroups.add(group); classes.add(cls)
        target_entries.append({**row,"target_class":cls})
    if len(tgroups)<20 or classes!=set(TARGETS):
        raise ValueError("freeze requires >=20 independent target groups covering both target classes")

    sgroups=set()
    speech_entries=[]
    for row in speeches:
        require_human_status(row)
        group=(row.get("source_group") or row.get("speaker_id") or "").strip()
        cid=row.get("candidate_id","").strip()
        if not group or not cid or group in sgroups:
            raise ValueError("speech source_group/candidate_id missing or duplicate group")
        validate_pcm(a.speech_manifest,row)
        sgroups.add(group)
        speech_entries.append(row)
    if len(sgroups)<4:
        raise ValueError("freeze requires >=4 independent external speakers")

    target_entries=sorted(target_entries,key=lambda r:(r["target_class"],r["source_group"],r["candidate_id"]))
    speech_entries=sorted(speech_entries,key=lambda r:(r.get("source_group",""),r["candidate_id"]))
    levels=(-3.0,3.0)
    scenes=[]
    for i,t in enumerate(target_entries):
        for j,rel in enumerate(levels):
            speech=speech_entries[(2*i+j)%len(speech_entries)]
            scenes.append({
                "scene_id":f"PI15_EXT_{i+1:03d}_{'M3' if rel<0 else 'P3'}",
                "target_candidate_id":t["candidate_id"],
                "target_class":t["target_class"],
                "source_group":t["source_group"],
                "speech_candidate_id":speech["candidate_id"],
                "speaker_group":speech.get("source_group") or speech.get("speaker_id"),
                "speech_rms_dbfs":-26.0,
                "target_relative_db":rel,
                "duration_samples":EXPECTED_FRAMES,
            })
    if len({s["scene_id"] for s in scenes})!=len(scenes):
        raise AssertionError("scene IDs not unique")

    files={
        "target_manifest":a.target_manifest,
        "speech_manifest":a.speech_manifest,
        "dsp_templates":a.dsp_templates,
        "checkpoint":a.checkpoint,
        "kappa_report":a.kappa_report,
        "contamination_report":a.contamination_report,
        "campaign_script":a.campaign_script,
        "analysis_script":a.analysis_script,
        "dsp_code":a.dsp_code,
        "dsp_config":a.dsp_config,
        "metric_protocol":a.metric_protocol,
    }
    hashes={k:sha256(v) for k,v in files.items()}
    value={
        "schema":"hesychia.pi15-external-freeze.v1",
        "status":"FROZEN_NOT_OPENED",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256":checkpoint_sha,
        "frontend":frontend_contract(),
        "target_source_groups":len(tgroups),
        "speech_groups":len(sgroups),
        "scene_count":len(scenes),
        "scene_rule":{
            "scenes_per_target_group":2,
            "speech_rms_dbfs":-26.0,
            "target_relative_db":[-3.0,3.0],
            "no_post_mix_normalization":True,
            "fail_on_abs_peak_gt":0.98,
        },
        "artifact_paths":{k:str(Path(v).resolve()) for k,v in files.items()},
        "artifact_sha256":hashes,
        "scenes":scenes,
        "test_opened":False,
        "scientific_boundary":"This freeze hashes approved data and code but does not run any inference.",
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",encoding="utf-8") as f:
        json.dump(value,f,ensure_ascii=False,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":value["status"],
        "target_source_groups":len(tgroups),
        "speech_groups":len(sgroups),
        "scene_count":len(scenes),
        "freeze_sha256":sha256(a.out)
    },ensure_ascii=False))


if __name__=="__main__":
    main()
