#!/usr/bin/env python3
"""Acquire deterministic 4 s protected-speech stems from LibriSpeech test-clean AFTER OE1.

The official OpenSLR SLR12 archive is verified against the publisher MD5. Only
preselected speaker IDs are extracted. No CNN/DSP/Oracle inference occurs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

SR=16000
N=SR*4
URL="https://www.openslr.org/resources/12/test-clean.tar.gz"
EXPECTED_MD5="32fa31d27d2e1cad72775fee3f4849a9"
ACK="I_CONFIRM_OE1_HUMAN_AUDIT_CLOSED"


def digest(path: Path,name="sha256"):
    h=hashlib.new(name)
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def download(dest: Path):
    if dest.exists():
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    part=dest.with_suffix(dest.suffix+".part")
    req=urllib.request.Request(URL,headers={"User-Agent":"HESYCHIA-thesis-external/1"})
    with urllib.request.urlopen(req,timeout=120) as r,part.open("wb") as f:
        total=0
        while b:=r.read(1024*1024):
            total+=len(b)
            if total>500_000_000:
                raise ValueError("LibriSpeech archive exceeds expected bound")
            f.write(b)
    part.replace(dest)


def best_window(x):
    if len(x)<N:
        return None,None
    hop=SR//2
    starts=list(range(0,len(x)-N+1,hop))
    if starts[-1]!=len(x)-N:
        starts.append(len(x)-N)
    score=[(float(np.mean(x[s:s+N].astype(np.float64)**2)),s) for s in starts]
    _,start=max(score,key=lambda z:(z[0],-z[1]))
    return x[start:start+N].astype(np.float32),int(start)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-csv",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--attestation",required=True)
    a=p.parse_args()
    if a.attestation!=ACK:
        raise ValueError("OE1 attestation missing; external speech remains sealed")

    with a.candidate_csv.open(newline="",encoding="utf-8-sig") as f:
        candidates=list(csv.DictReader(f))
    speakers={r["reader_id"].strip():r for r in candidates}
    if len(speakers)<4:
        raise ValueError("need >=4 preselected speakers")

    archive=a.out_dir/"downloads/test-clean.tar.gz"
    download(archive)
    if digest(archive,"md5")!=EXPECTED_MD5:
        raise ValueError("OpenSLR test-clean archive MD5 mismatch")

    extracted=a.out_dir/"extracted"
    extracted.mkdir(parents=True,exist_ok=True)
    files={sid:[] for sid in speakers}
    pattern=re.compile(r"LibriSpeech/test-clean/(\d+)/(\d+)/(\d+-\d+-\d+\.flac)")
    with tarfile.open(archive,"r:gz") as tf:
        for member in tf:
            m=pattern.fullmatch(member.name)
            if not m or not member.isfile():
                continue
            sid=m.group(1)
            if sid not in speakers:
                continue
            if member.size>30_000_000:
                raise ValueError("unexpectedly large FLAC")
            dest=extracted/sid/m.group(3)
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():
                src=tf.extractfile(member)
                if src is None:
                    raise ValueError("cannot extract FLAC")
                with src,dest.open("wb") as out:
                    while b:=src.read(1024*1024):
                        out.write(b)
            files[sid].append(dest)

    pcm_dir=a.out_dir/"pcm";pcm_dir.mkdir(parents=True,exist_ok=True)
    prepared=[]
    for sid,row in sorted(speakers.items()):
        options=[]
        for path in sorted(files[sid]):
            info=sf.info(path)
            if info.samplerate!=SR or info.channels!=1:
                raise ValueError(f"unexpected LibriSpeech format: {path}")
            if info.frames>=N:
                options.append((info.frames,path))
        if not options:
            continue
        _,chosen=max(options,key=lambda z:(z[0],str(z[1])))
        x,rate=sf.read(chosen,dtype="float32",always_2d=False)
        segment,start=best_window(np.asarray(x,dtype=np.float32))
        if segment is None:
            continue
        out=pcm_dir/f"{row['candidate_id']}.wav"
        if out.exists():
            raise ValueError(f"refusing overwrite: {out}")
        sf.write(out,segment,SR,subtype="FLOAT")
        prepared.append({
            **row,
            "source_flac":str(chosen.resolve()),
            "source_flac_sha256":digest(chosen),
            "segment_start_sample":start,
            "pcm_path":str(out.resolve()),
            "pcm_sha256":digest(out),
            "human_audit_status":"DATASET_VERIFIED",
        })

    if len(prepared)<4:
        raise ValueError(f"only {len(prepared)} speakers yielded >=4 s PCM")
    out_csv=a.out_dir/"speech_frozen_candidates.csv"
    with out_csv.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(prepared[0].keys()));w.writeheader();w.writerows(prepared)
    report={
        "schema":"hesychia.pi15-speech-preparation.v1",
        "archive_url":URL,
        "archive_md5":digest(archive,"md5"),
        "archive_sha256":digest(archive),
        "publisher_md5_expected":EXPECTED_MD5,
        "prepared_speakers":len(prepared),
        "speaker_ids":[r["speaker_id"] for r in prepared],
        "output_manifest":str(out_csv.resolve()),
        "license":"CC BY 4.0",
        "note":"No model inference was executed.",
    }
    (a.out_dir/"speech_preparation_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
