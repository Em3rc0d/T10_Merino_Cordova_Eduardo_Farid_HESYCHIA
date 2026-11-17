#!/usr/bin/env python3
"""Build the final target-conditioned DSP templates from the admissible V1 training pool.

This step is PRE-TEST. It uses only archived training PCM and human-audit
exclusions. It never reads the external confirmatory cohort.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = LAB_ROOT / "src"
for _path in (LAB_ROOT, SRC_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np
import soundfile as sf

from src.dsp_class_template import fit_class_templates, save_templates
from src.m4_scientific.corpus import SR, TARGETS


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def rows(path: Path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def review_exclusions(path: Path):
    result={}
    for r in rows(path):
        aid=r.get("asset_id","").strip()
        if not aid or aid in result:
            raise ValueError("invalid/duplicate final review asset_id")
        decision=r.get("review_decision","").strip().lower()
        purity=r.get("purity_judgement","").strip().lower()
        audible=r.get("main_event_audible","").strip().lower()
        pcm=r.get("pcm_sha256","").strip().lower()
        if len(pcm)!=64:
            raise ValueError(f"invalid review PCM SHA for {aid}")
        eligible=(decision=="eligible" and purity=="isolated" and audible=="yes")
        result[aid]={"eligible":eligible,"pcm_sha256":pcm}
    if len(result)!=93:
        raise ValueError(f"final human review must contain 93 rows, got {len(result)}")
    return result


def load_pcm(path: Path, expected_sha: str):
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256(path).lower()!=expected_sha.lower():
        raise ValueError(f"PCM SHA mismatch: {path.name}")
    x,rate=sf.read(path,dtype="float32",always_2d=False)
    if rate!=SR or x.ndim!=1 or len(x)<SR or not np.isfinite(x).all():
        raise ValueError(f"invalid frozen PCM: {path}")
    return np.asarray(x,dtype=np.float32)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--audio-root",type=Path,required=True)
    p.add_argument("--final-review-93",type=Path,required=True)
    p.add_argument("--out-npz",type=Path,required=True)
    p.add_argument("--out-json",type=Path,required=True)
    a=p.parse_args()
    if a.out_npz.exists() or a.out_json.exists():
        raise ValueError("refusing to overwrite DSP freeze evidence")

    manifest=rows(a.manifest)
    review=review_exclusions(a.final_review_93)
    by_id={r.get("asset_id","").strip():r for r in manifest}
    if len(by_id)!=len(manifest):
        raise ValueError("duplicate asset_id in corpus manifest")

    for aid,v in review.items():
        if aid not in by_id:
            raise ValueError(f"review asset absent from corpus: {aid}")
        if by_id[aid].get("pcm_sha256","").strip().lower()!=v["pcm_sha256"]:
            raise ValueError(f"review/corpus PCM SHA mismatch: {aid}")

    exclusions={aid for aid,v in review.items() if not v["eligible"]}
    clips={0:[],1:[]}
    source_groups={0:set(),1:set()}
    used=[]
    for r in manifest:
        if r.get("split","").strip().lower()!="train":
            continue
        cls=r.get("acoustic_class","").strip().lower()
        if cls not in TARGETS:
            continue
        aid=r["asset_id"].strip()
        if aid in exclusions:
            continue
        cid=TARGETS.index(cls)
        pcm=a.audio_root/(aid+".wav")
        x=load_pcm(pcm,r["pcm_sha256"].strip())
        clips[cid].append(x)
        source_groups[cid].add(r.get("source_group","").strip() or aid)
        used.append(aid)

    for cid,name in enumerate(TARGETS):
        if len(clips[cid])<10 or len(source_groups[cid])<5:
            raise ValueError(f"insufficient admissible training material for {name}")

    templates=fit_class_templates(clips,class_ids=(0,1))
    metadata={
        "schema":"hesychia.dsp-template-build.v1",
        "targets":list(TARGETS),
        "corpus_manifest_sha256":sha256(a.manifest),
        "final_review_93_sha256":sha256(a.final_review_93),
        "human_review_rows":93,
        "excluded_reviewed_assets":sorted(exclusions),
        "admissible_training_assets_sha256":hashlib.sha256(
            ("\n".join(sorted(used))+"\n").encode()
        ).hexdigest(),
        "training_counts":{TARGETS[i]:len(clips[i]) for i in (0,1)},
        "training_source_groups":{TARGETS[i]:len(source_groups[i]) for i in (0,1)},
    }
    template_sha=save_templates(a.out_npz,templates,metadata)
    report={
        **metadata,
        "status":"DSP_TEMPLATES_FROZEN_PRE_TEST",
        "template_npz":str(a.out_npz.resolve()),
        "template_sha256":template_sha,
        "note":"No external confirmatory audio was read by this build step.",
    }
    a.out_json.parent.mkdir(parents=True,exist_ok=True)
    a.out_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "template_sha256":template_sha,
        "training_counts":report["training_counts"],
        "excluded_reviewed_assets":len(exclusions)
    },ensure_ascii=False))


if __name__=="__main__":
    main()
