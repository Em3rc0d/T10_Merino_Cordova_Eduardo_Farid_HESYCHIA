#!/usr/bin/env python3
"""Acquire and prepare the preselected FSD50K target reserve pool AFTER OE1 closes.

This script is intentionally blocked behind an explicit attestation. It downloads
only versioned candidate IDs, converts them deterministically to mono 16 kHz and
extracts a 4 s maximum-RMS window for human target-purity review. No model is run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import urllib.request
from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf

SR=16000
SECONDS=4
N=SR*SECONDS
ACK="I_CONFIRM_OE1_HUMAN_AUDIT_CLOSED"


def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def download(url: str,dest: Path,max_bytes=20_000_000):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    part=dest.with_suffix(dest.suffix+".part")
    req=urllib.request.Request(url,headers={"User-Agent":"HESYCHIA-thesis-external/1"})
    with urllib.request.urlopen(req,timeout=90) as r,part.open("wb") as f:
        total=0
        while b:=r.read(1024*1024):
            total+=len(b)
            if total>max_bytes:
                raise ValueError(f"download too large: {url}")
            f.write(b)
    part.replace(dest)


def resample_mono(path: Path):
    x,rate=sf.read(path,dtype="float32",always_2d=True)
    x=x.mean(axis=1)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError(f"invalid audio: {path}")
    if rate!=SR:
        g=math.gcd(rate,SR)
        x=scipy.signal.resample_poly(x,SR//g,rate//g).astype(np.float32)
    return x.astype(np.float32)


def best_four_seconds(x: np.ndarray):
    if len(x)<N:
        return None,None
    hop=SR//2
    starts=list(range(0,len(x)-N+1,hop))
    if starts[-1]!=len(x)-N:
        starts.append(len(x)-N)
    scores=[]
    for s in starts:
        y=x[s:s+N].astype(np.float64)
        scores.append((float(np.mean(y*y)),s))
    _,start=max(scores,key=lambda z:(z[0],-z[1]))
    return x[start:start+N].astype(np.float32),int(start)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-csv",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--attestation",required=True)
    a=p.parse_args()
    if a.attestation!=ACK:
        raise ValueError("OE1 attestation missing; external target audio remains sealed")

    with a.candidate_csv.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if len(rows)<20:
        raise ValueError("candidate reserve pool must contain >=20 rows")

    raw_dir=a.out_dir/"raw"
    pcm_dir=a.out_dir/"pcm"
    pcm_dir.mkdir(parents=True,exist_ok=True)
    prepared=[]
    review=[]
    for row in rows:
        cid=row["candidate_id"].strip()
        fid=row["freesound_id"].strip()
        partition="eval" if row["source_partition"].endswith("eval") else "dev"
        url=f"https://huggingface.co/datasets/Fhrozen/FSD50k/resolve/main/clips/{partition}/{fid}.wav"
        raw=raw_dir/f"{fid}.wav"
        download(url,raw)
        x=resample_mono(raw)
        segment,start=best_four_seconds(x)
        status="READY_FOR_HUMAN_REVIEW" if segment is not None else "TOO_SHORT_LT_4S"
        pcm_path=""
        pcm_sha=""
        if segment is not None:
            out=pcm_dir/f"{cid}.wav"
            if out.exists():
                raise ValueError(f"refusing overwrite: {out}")
            sf.write(out,segment,SR,subtype="FLOAT")
            pcm_path=str(out.resolve())
            pcm_sha=sha256(out)
            review.append({
                "asset_id":cid,
                "pcm_sha256":pcm_sha,
                "acoustic_class":row["target_class"].strip().lower(),
                "split":"external_confirmatory_candidate",
                "source_group":row["source_group"],
                "license":row["license"],
            })
        prepared.append({
            **row,
            "download_url":url,
            "raw_sha256":sha256(raw),
            "segment_start_sample_16k":"" if start is None else start,
            "pcm_path":pcm_path,
            "pcm_sha256":pcm_sha,
            "human_audit_status":"NOT_REVIEWED" if segment is not None else status,
            "prep_status":status,
        })

    a.out_dir.mkdir(parents=True,exist_ok=True)
    prep=a.out_dir/"target_prepared_candidates.csv"
    with prep.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(prepared[0].keys()));w.writeheader();w.writerows(prepared)
    manifest=a.out_dir/"target_review_manifest.csv"
    if not review:
        raise ValueError("no >=4 s candidates available")
    with manifest.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(review[0].keys()));w.writeheader();w.writerows(review)
    print({
        "candidates":len(rows),
        "ready_for_human_review":len(review),
        "too_short":len(rows)-len(review),
        "review_manifest":str(manifest),
        "note":"No model inference was executed."
    })


if __name__=="__main__":
    main()
