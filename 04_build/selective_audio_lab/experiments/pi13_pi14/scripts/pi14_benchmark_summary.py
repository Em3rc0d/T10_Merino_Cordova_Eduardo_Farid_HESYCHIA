#!/usr/bin/env python3
"""Resumen verificable de trazas offline por hop, no captura/salida física E2E.

El CSV debe proceder de una ejecución instrumental real de M4. Se descartan los
primeros warmup_hops de cada run_id. La herramienta jamás inventa mediciones.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,math
from collections import defaultdict
from pathlib import Path
import numpy as np

REQUIRED=('run_id','hop_index','stft_ms','m4_ms','istft_ms','total_ms','chunk_duration_ms')
STAGES=('stft_ms','m4_ms','istft_ms','total_ms')

def summarize(path:Path,*,warmup_hops:int=10):
    if warmup_hops<0:raise ValueError('warmup_hops no puede ser negativo')
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        rdr=csv.DictReader(f)
        if not rdr.fieldnames or any(k not in rdr.fieldnames for k in REQUIRED):
            raise ValueError('Columnas requeridas: '+','.join(REQUIRED))
        rows=list(rdr)
    by_run=defaultdict(list);seen=set()
    for row in rows:
        run_id=row['run_id'].strip()
        if not run_id:raise ValueError('run_id vacío')
        ix=int(row['hop_index'])
        if ix<0 or (run_id,ix) in seen:raise ValueError('hop_index repetido o negativo')
        seen.add((run_id,ix))
        vals={}
        for k in (*STAGES,'chunk_duration_ms'):
            v=float(row[k]);
            if not math.isfinite(v) or v<=0 and k=='chunk_duration_ms' or v<0:
                raise ValueError(f'Duración no válida en {run_id}:{ix}/{k}')
            vals[k]=v
        if 'peak_rss_mb' in row and row['peak_rss_mb'].strip():
            mem=float(row['peak_rss_mb'])
            if not math.isfinite(mem) or mem<0:raise ValueError('Memoria inválida')
            vals['peak_rss_mb']=mem
        by_run[run_id].append((ix,vals))
    kept=[];discarded=0
    for run_id,rs in sorted(by_run.items()):
        rs.sort(key=lambda x:x[0]);discarded+=min(warmup_hops,len(rs))
        kept.extend([(run_id,i,v) for i,v in rs[warmup_hops:]])
    if len(kept)<10:raise ValueError('Menos de 10 hops instrumentados después del warmup')
    pctl=lambda values:{'p50_ms':float(np.percentile(values,50)),
                         'p95_ms':float(np.percentile(values,95)),
                         'p99_ms':float(np.percentile(values,99)),
                         'mean_ms':float(np.mean(values))}
    metric={stage:pctl([v[stage] for _,_,v in kept]) for stage in STAGES}
    total=sum(v['total_ms'] for _,_,v in kept)
    audio=sum(v['chunk_duration_ms'] for _,_,v in kept)
    memories=[v['peak_rss_mb'] for _,_,v in kept if 'peak_rss_mb' in v]
    result={'schema':'hesychia.pi14-offline-benchmark-summary.v1','input':str(path),
       'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'run_count':len(by_run),'samples_total':len(rows),'samples_after_warmup':len(kept),
       'samples_discarded':discarded,'warmup_per_run':warmup_hops,
       'latency_ms':metric,'real_time_factor_total':total/audio,
       'peak_rss_mb_max':max(memories) if memories else None,
       'real_time_factor_interpretation':'RTF<1 indicates observed processing faster than nominal audio block duration, not physical realtime streaming',
       'limitations':['Solo resume trazas suministradas; no valida su origen físico',
                      'No mide E2E de micrófono a altavoz, jitter del driver ni Bluetooth',
                      'Percentiles por hop no sustituyen estabilidad de streaming continuo',
                      'No marca éxito RNF; requiere trazas reales, protocolo y aprobación']}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--warmup-hops',type=int,default=10)
    a=p.parse_args();res=summarize(a.csv,warmup_hops=a.warmup_hops)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Offline hops: {res['samples_after_warmup']}; RTF: {res['real_time_factor_total']:.3f}; NOT E2E")
if __name__=='__main__':main()
