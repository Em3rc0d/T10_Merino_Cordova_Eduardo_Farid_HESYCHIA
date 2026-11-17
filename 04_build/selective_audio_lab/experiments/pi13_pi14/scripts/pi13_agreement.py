#!/usr/bin/env python3
"""Acuerdo Cohen κ para revisiones independientes del mismo conjunto de activos.

Entrada: CSV con asset_id,reviewer_id,review_decision. Sólo registra los activos con
exactamente dos decisiones válidas de revisores distintos. No reemplaza adjudicación.
"""
from __future__ import annotations
import argparse,csv,json
from collections import defaultdict,Counter
from pathlib import Path
CATEGORIES=('eligible','restricted','reject')

def calculate(path:Path):
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        required={'asset_id','reviewer_id','review_decision'}
        if not r.fieldnames or not required.issubset(set(r.fieldnames)):
            raise ValueError('Se requieren asset_id, reviewer_id, review_decision')
        rows=list(r)
    assets=defaultdict(dict)
    for row in rows:
        aid=row['asset_id'].strip();rid=row['reviewer_id'].strip();decision=row['review_decision'].strip().lower()
        if not aid or not rid:raise ValueError('asset_id y reviewer_id son obligatorios')
        if decision not in CATEGORIES: raise ValueError(f'Decisión inválida en {aid}: {decision}')
        if rid in assets[aid]:raise ValueError(f'Decisión repetida {aid}/{rid}')
        assets[aid][rid]=decision
    if any(len(reviews)!=2 for reviews in assets.values()):
        raise ValueError('Cada asset_id debe tener exactamente dos revisores distintos')
    n=len(assets)
    if n==0: raise ValueError('No hay activos evaluados')
    # El orden de anotación del CSV NO identifica a los revisores.
    # Cohen kappa sólo se calcula con las dos columnas de evaluadores fijos.
    reviewer_ids=sorted({rid for reviews in assets.values() for rid in reviews})
    if len(reviewer_ids)!=2 or any(set(reviews)!=set(reviewer_ids) for reviews in assets.values()):
        raise ValueError('Los mismos dos reviewer_id deben evaluar cada activo')
    pairs=[(reviews[reviewer_ids[0]],reviews[reviewer_ids[1]])
           for _,reviews in sorted(assets.items())]
    p0=sum(a==b for a,b in pairs)/n
    freq_a=Counter(a for a,b in pairs);freq_b=Counter(b for a,b in pairs)
    pe=sum((freq_a[k]/n)*(freq_b[k]/n) for k in CATEGORIES)
    if abs(1-pe)<1e-12:
        kappa=None;warning='κ no definido: ambos revisores usan una única categoría sin variabilidad'
    else:
        kappa=(p0-pe)/(1-pe);warning=None
    confusion={a:{b:sum(x==a and y==b for x,y in pairs) for b in CATEGORIES} for a in CATEGORIES}
    return {'schema':'hesychia.pi13-kappa.v1','pairs':n,'reviewer_column_order':reviewer_ids,'observed_agreement':p0,'chance_agreement':pe,
            'cohen_kappa':kappa,'warning':warning,'matrix':confusion,
            'warning_scope':'La interpretación del κ depende de prevalencias y criterios de adjudicación',
            'independent_reviews_verified_by_software':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reviews',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();res=calculate(a.reviews);a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'pairs':res['pairs'],'kappa':res['cohen_kappa']}))
if __name__=='__main__':main()
