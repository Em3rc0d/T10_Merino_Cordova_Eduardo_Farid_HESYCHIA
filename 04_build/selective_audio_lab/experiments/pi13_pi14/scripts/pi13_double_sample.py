#!/usr/bin/env python3
"""Reproducible *proposal* for blinded second listening review.

Group sampling is stratified by acoustic_class and split, seeded by SHA-256;
all items belonging to selected source groups are retained within each stratum.
Selections should be frozen before second reviewer opens the audios.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def choose(manifest, out_csv, out_json, *, rate=.2, seed=20261108, minimum=2):
    if not 0<rate<=1 or minimum<1:raise ValueError('Invalid review fraction/minimum')
    with Path(manifest).open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames
        if not fields or not {'asset_id','acoustic_class','split','source_group'}.issubset(fields):
            raise ValueError('Manifest missing sampling columns')
        rows=list(reader)
    if not rows or len({r['asset_id'] for r in rows})!=len(rows):
        raise ValueError('Empty or duplicate asset IDs')
    strata=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if not all(r.get(k,'').strip() for k in ('acoustic_class','split','source_group')):
            raise ValueError('Missing group/stratum')
        key=(r['acoustic_class'],r['split'])
        strata[key][r['source_group']].append(r)
    selected=[];summary=[]
    for (cls,split),g in sorted(strata.items()):
        ordered=sorted(g,key=lambda group:(hashlib.sha256(f'{seed}|{cls}|{split}|{group}'.encode()).hexdigest(),group))
        k=min(len(ordered),max(minimum,math.ceil(len(ordered)*rate)))
        groups=set(ordered[:k])
        subset=[r for r in rows if (r['acoustic_class'],r['split'])==(cls,split) and r['source_group'] in groups]
        selected.extend(subset)
        summary.append(dict(acoustic_class=cls,split=split,available_groups=len(ordered),selected_groups=k,selected_items=len(subset)))
    selected.sort(key=lambda r:r['asset_id'])
    out_csv=Path(out_csv);out_json=Path(out_json)
    if out_csv.resolve()==Path(manifest).resolve():raise ValueError('Cannot overwrite original manifest')
    out_csv.parent.mkdir(parents=True,exist_ok=True)
    with out_csv.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(selected)
    meta=dict(schema='hesychia.pi13-double-review-sampling.v1',created_utc=datetime.now(timezone.utc).isoformat(),
       source_manifest_sha256=digest(manifest),selection_manifest_sha256=digest(out_csv),seed=seed,rate=rate,minimum_per_stratum=minimum,
       algorithm='SHA256(seed|class|split|source_group), group selection within stratum',
       total_items=len(rows),selected_items=len(selected),strata=summary,
       limitations=['Selection for second listen only, not independent scientific train/val/test partition',
                    'All selected assets must still be evaluated by the same two independent human reviewers',
                    'Do not change sampling after observing disagreements or outcomes'])
    out_json.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return meta

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--rate',type=float,default=.2)
    p.add_argument('--min-groups-per-stratum',type=int,default=2);p.add_argument('--seed',type=int,default=20261108)
    a=p.parse_args();res=choose(a.manifest,a.out,a.report,rate=a.rate,minimum=a.min_groups_per_stratum,seed=a.seed)
    print(json.dumps({'total':res['total_items'],'second_review_items':res['selected_items'],'selected_sha256':res['selection_manifest_sha256']}))
if __name__=='__main__':main()
