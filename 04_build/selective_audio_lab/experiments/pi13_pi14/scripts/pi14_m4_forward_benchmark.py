#!/usr/bin/env python3
"""Measured M4 CNN forward-pass-only benchmark, with a real pinned checkpoint.

The input is deterministic artificial audio; this never opens a thesis test split.
Chunks use real historical context in an offline feature sequence and output only
new frames. This is NOT physical streaming, STFT+iSTFT E2E or capture latency.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import torch

def hashfile(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):h.update(b)
    return h.hexdigest()

def fixture(sr,seconds,seed,device):
    rng=np.random.default_rng(seed)
    t=np.arange(int(sr*seconds),dtype=np.float32)/sr
    return torch.from_numpy((.045*np.sin(2*np.pi*470*t)+.03*np.sin(2*np.pi*940*t)
                 +.008*rng.normal(size=t.shape)).astype('float32')).to(device)

def benchmark(checkpoint:Path,model_src:Path,out:Path,*,seed=20261108,runs=40,warmup=4,
              hops=16,seconds=2.,device='cpu',threads=4):
    if runs<5 or warmup<1 or hops<1 or seconds<=.05:raise ValueError('Invalid benchmark configuration')
    if device not in ('cpu','cuda'):raise ValueError('Only cpu/cuda are supported')
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
    if not checkpoint.is_file() or not model_src.is_dir():raise FileNotFoundError('Checkpoint/model-src missing')
    if device=='cpu':torch.set_num_threads(threads)
    sys.path.insert(0,str(model_src.resolve()))
    from m4_scientific.model import (features, spectrum, load_checkpoint, SR, HOP, frontend_contract)
    model,obj=load_checkpoint(checkpoint)
    # Hash and contract are checked by load_checkpoint; no random weights, no fallback.
    model=model.to(device).eval()
    label=torch.tensor([0],device=device,dtype=torch.long)
    sig=fixture(SR,seconds,seed,device)
    with torch.inference_mode():
        f=features(spectrum(sig))[0]
    left=max(0, int(model.receptive_frames)-1)
    blocks=[]
    for end in range(hops,f.shape[0]+hops,hops):
        hi=min(end,f.shape[0]);lo=max(0,hi-hops-left)
        if hi<=lo:continue
        blocks.append((lo,hi,hi-(end-hops),f[lo:hi][None].contiguous()))
    if not blocks:raise ValueError('Insufficient frames for a single block')
    sync=(lambda:torch.cuda.synchronize()) if device=='cuda' else (lambda:None)
    samples=[]
    for run in range(warmup+runs):
        for bi,(lo,hi,n_new,inp) in enumerate(blocks):
            sync();t0=time.perf_counter_ns()
            with torch.inference_mode():
                mask=model(inp,label)[:,-n_new:]
                gain=model.gain(mask)
                if not bool(torch.isfinite(gain).all()):raise ValueError('Non-finite output')
            sync();elapsed=(time.perf_counter_ns()-t0)/1e6
            if run>=warmup:
                samples.append(dict(run_id=run-warmup,block_index=bi,
                                    input_context_frames=hi-lo,output_frames=n_new,
                                    m4_ms=elapsed,chunk_duration_ms=n_new*HOP/SR*1000))
    elapsed=np.array([r['m4_ms'] for r in samples],dtype=float)
    dur=np.array([r['chunk_duration_ms'] for r in samples],dtype=float)
    out.mkdir(parents=True,exist_ok=True)
    csv_file=out/'m4_forward_samples.csv'
    with csv_file.open('w',newline='',encoding='utf-8') as handle:
        w=csv.DictWriter(handle,fieldnames=list(samples[0]));w.writeheader();w.writerows(samples)
    report=dict(schema='hesychia.pi14-m4-forward-only.v1',
        measured_at_utc=datetime.now(timezone.utc).isoformat(),
        checkpoint_sha256=hashfile(checkpoint), checkpoint_file=str(checkpoint.resolve()),
        source_file=str((model_src/'m4_scientific'/'model.py').resolve()),
        script_sha256=hashfile(Path(__file__)),
        frontend=frontend_contract(), model_type=type(model).__name__,
        torch_version=torch.__version__,python=platform.python_version(),platform=platform.platform(),
        logical_cpus_visible=os.cpu_count(),device=device,threads=threads,
        seed=seed,runs=runs,warmup_runs=warmup,block_count=len(blocks),
        receptive_frames=int(model.receptive_frames),block_hops=hops,
        input_audio_seconds=float(seconds),signal='synthetic deterministic mixed tones+Gaussian noise; NOT test audio',
        block_ms=dict(p50=float(np.percentile(elapsed,50)),p95=float(np.percentile(elapsed,95)),
                      p99=float(np.percentile(elapsed,99)),mean=float(elapsed.mean())),
        model_only_rtf=float(elapsed.sum()/dur.sum()),samples=int(len(samples)),
        source='real checkpoint loaded; synthetic features of a fixed offline audio signal',
        measurement_scope='M4 forward+gain on offline chunks with historical context; no STFT/feature or iSTFT processing in timed interval',
        warnings=['Does not demonstrate real-time audio capture/output, physical streaming or E2E latency',
                  'Inputs are precomputed from an offline clip; does not measure streaming FFT/buffering',
                  'Repeated chunks are dependent; percentiles describe repeated-run timing, not independent scenes',
                  'Model-only RTF<1 is not sufficient to claim realtime system',
                  'Model checkpoint must be explicitly identified; never compare this number with baseline whole-clip latency'])
    (out/'m4_forward_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--model-src',type=Path,required=True,help='path to selective_audio_lab/src')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--runs',type=int,default=40);p.add_argument('--warmup',type=int,default=4)
    p.add_argument('--hops',type=int,default=16)
    p.add_argument('--seconds',type=float,default=2)
    p.add_argument('--seed',type=int,default=20261108)
    p.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    p.add_argument('--threads',type=int,default=4)
    a=p.parse_args()
    report=benchmark(a.checkpoint,a.model_src,a.out,seed=a.seed,runs=a.runs,
                 warmup=a.warmup,hops=a.hops,seconds=a.seconds,device=a.device,threads=a.threads)
    print(json.dumps({'checkpoint_sha256':report['checkpoint_sha256'],'scope':report['measurement_scope'],
          'block_ms':report['block_ms'],'model_only_rtf':report['model_only_rtf']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
