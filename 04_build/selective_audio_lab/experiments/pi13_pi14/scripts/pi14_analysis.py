#!/usr/bin/env python3
"""PI14: análisis pareado, IC bootstrap por grupos originales y banderas de sesgo.

Nunca toma decisiones de aceptación clínica o científica sin protocolo firmado.
El CSV requiere una fila por mezcla/método (CNN, DSP, ORACLE) y los campos:
scene_id,source_group,speaker_group,mix_sha256,method,a_target_db,a_protected_db.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
import numpy as np

METHODS=('CNN','DSP','ORACLE')
REQUIRED=['scene_id','source_group','speaker_group','mix_sha256','method','a_target_db','a_protected_db']

def read_pairs(path:Path):
    with path.open('r',newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in REQUIRED):
            raise ValueError('CSV con columnas faltantes; se requieren: '+','.join(REQUIRED))
        rows=list(reader)
    if not rows: raise ValueError('CSV sin filas')
    scenes=defaultdict(dict); groups={}; speakers={}; mixtures={}
    for r in rows:
        sid=r['scene_id'].strip(); method=r['method'].strip().upper()
        if not sid or not r['source_group'].strip() or not r['speaker_group'].strip():
            raise ValueError('IDs de escena/grupo/hablante obligatorios')
        if method not in METHODS: raise ValueError(f'Método desconocido: {method}')
        if method in scenes[sid]: raise ValueError(f'Duplicado escena/método: {sid}/{method}')
        if sid in groups and groups[sid]!=r['source_group']:
            raise ValueError(f'Grupo fuente inconsistente: {sid}')
        if sid in speakers and speakers[sid]!=r['speaker_group']:
            raise ValueError(f'Grupo hablante inconsistente: {sid}')
        mh=r['mix_sha256'].strip().lower()
        if len(mh)!=64 or any(c not in '0123456789abcdef' for c in mh):
            raise ValueError(f'Hash de mezcla inválido: {sid}/{method}')
        if sid in mixtures and mixtures[sid]!=mh:
            raise ValueError(f'Mezcla distinta entre métodos: {sid}/{method}')
        mixtures[sid]=mh
        groups[sid]=r['source_group'];speakers[sid]=r['speaker_group']
        vals=[]
        for k in ('a_target_db','a_protected_db'):
            v=float(r[k]);
            if not math.isfinite(v):raise ValueError(f'Valor no finito {sid}/{method}/{k}')
            vals.append(v)
        scenes[sid][method]=vals
    bad=[k for k,v in scenes.items() if set(v)!=set(METHODS)]
    if bad:raise ValueError('Faltan métodos en escenas: '+','.join(bad[:6]))
    ids=sorted(scenes)
    return ids,groups,speakers,np.array([[scenes[i][m] for m in METHODS] for i in ids],dtype=float)


def ci_cluster(values, groups, *, seed=20261108, n_boot=3000):
    """Bootstrap de grupos; los grupos se seleccionan con reemplazo y conservan todas sus escenas."""
    if n_boot < 100:raise ValueError('n_boot insuficiente (<100)')
    unique=sorted(set(groups))
    if len(unique)<2:raise ValueError('Al menos dos grupos independientes necesarios para IC')
    by={g:np.array([i for i,x in enumerate(groups) if x==g],dtype=int) for g in unique}
    rg=np.random.default_rng(seed)
    stats=np.empty(n_boot)
    for b in range(n_boot):
        chosen=rg.integers(0,len(unique),size=len(unique))
        idx=np.concatenate([by[unique[j]] for j in chosen])
        stats[b]=float(np.mean(values[idx]))
    return {'mean':float(np.mean(values)), 'ci95_low':float(np.quantile(stats,.025)),
            'ci95_high':float(np.quantile(stats,.975)), 'cluster_count':len(unique),
            'method':'cluster-bootstrap-percentile-v1', 'n_boot':n_boot,'seed':seed}


def analyze(path:Path, *,seed=20261108,n_boot=3000):
    ids,groups,speakers,data=read_pairs(path)
    source=[groups[i] for i in ids];speakers_list=[speakers[i] for i in ids]
    target=data[:,0,0]-data[:,1,0]  # CNN - DSP, higher means greater target attenuation
    protected=data[:,0,1]-data[:,1,1] # CNN - DSP, lower is less speech damage
    raw={
      'schema':'hesychia.pi14-paired-analysis.v1',
      'input':str(path),'scene_count':len(ids),'paired_mix_sha256_verified':True,'source_group_count':len(set(source)),
      'speaker_group_count':len(set(speakers_list)),
      'estimands':{'cnn_minus_dsp_target_db':ci_cluster(target,source,seed=seed,n_boot=n_boot),
                   'cnn_minus_dsp_protected_loss_db':ci_cluster(protected,source,seed=seed+1,n_boot=n_boot)},
      'speaker_cluster_sensitivity':{'target_db':ci_cluster(target,speakers_list,seed=seed+2,n_boot=n_boot),
                                     'protected_loss_db':ci_cluster(protected,speakers_list,seed=seed+3,n_boot=n_boot)},
      'historical_both_ok':{},'model_eligible_for_unsealed_test':False,
      'limitations':['Remuestreo por fuente y sensibilidad por hablante no equivalen a bootstrap multivía exacto',
                     'Los IC son descriptivos si el test se usó para tuning',
                     'No se infiere éxito sin margen de preservación aprobado antes de evaluar',
                     'Oracle IRM es referencia privilegiada, no límite matemático universal de todas las métricas']
    }
    for j,m in enumerate(METHODS):
        ok=(data[:,j,0]>=6.0)&(data[:,j,1]<=1.0)
        raw['historical_both_ok'][m]={'n':int(ok.sum()),'denominator':len(ids),'fraction':float(ok.mean())}
    # No collapse of denominators near zero or negative; report only aggregate gap with full disclosure
    dsp=float(data[:,1,0].mean());ora=float(data[:,2,0].mean());cnn=float(data[:,0,0].mean())
    delta=ora-dsp
    raw['oracle_gap_target_db']={'cnn_mean':cnn,'dsp_mean':dsp,'oracle_mean':ora,
        'gap_closure_fraction':(cnn-dsp)/delta if delta>1e-6 else None,
        'definition':'aggregate mean attenuation; only defined for Oracle-DSP>1e-6 dB'}
    return raw

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--by-scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=20261108)
    p.add_argument('--boot',type=int,default=3000)
    a=p.parse_args()
    res=analyze(a.by_scene,seed=a.seed,n_boot=a.boot)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Completed {res['scene_count']} paired scenes. NOT a certification of GO.")

if __name__=='__main__':main()
