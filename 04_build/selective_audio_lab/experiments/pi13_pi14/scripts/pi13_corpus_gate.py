#!/usr/bin/env python3
"""PI13: Validación conservadora de metadatos y revisión humana sin escuchar audio.

Este programa NO certifica pureza acústica, licencias, procedencia real ni independencia
perceptual. El estado PASS sólo certifica reglas verificables del CSV aportado.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

VALID_DECISIONS = {'eligible', 'restricted', 'reject'}
VALID_PURITY = {'isolated', 'minor_contamination', 'mixed', 'undetermined'}
REQUIRED = ['asset_id','split','source_group','pcm_sha256','reviewer_id',
            'review_date_utc','purity_judgement','review_decision']


def file_hash(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1024*1024), b''):
            h.update(buf)
    return h.hexdigest()


def load_csv(path: Path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV vacío o sin cabecera')
        rows=list(reader)
        return reader.fieldnames,rows


def quality_gate(path: Path) -> dict:
    fields,rows=load_csv(path)
    missing=[name for name in REQUIRED if name not in fields]
    if missing: raise ValueError('Columnas requeridas ausentes: '+', '.join(missing))
    splits=Counter(); classes=Counter(); licenses=Counter();
    source_splits=defaultdict(set); speech_splits=defaultdict(set);
    sha_seen={}; asset_seen=set(); errors=[]; incomplete=[]; invalid=[]
    for idx,row in enumerate(rows,start=2):
        asset=row['asset_id'].strip()
        if not asset:errors.append(f'Fila {idx}: asset_id vacío')
        if asset in asset_seen:errors.append(f'Fila {idx}: asset_id duplicado {asset}')
        asset_seen.add(asset)
        split=row['split'].strip().lower()
        splits[split]+=1
        if split not in {'train','val','test'}: errors.append(f'Fila {idx}: split inválido {split}')
        classes[row.get('acoustic_class','').strip()]+=1
        licenses[row.get('license','').strip()]+=1
        source=row['source_group'].strip()
        if not source:errors.append(f'Fila {idx}: source_group vacío')
        else: source_splits[source].add(split)
        speaker=row.get('speaker_id','').strip()
        if speaker:speech_splits[speaker].add(split)
        sha=row['pcm_sha256'].strip().lower()
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            errors.append(f'Fila {idx}: pcm_sha256 inválido')
        elif sha in sha_seen:
            errors.append(f'Fila {idx}: audio SHA repetido ({sha_seen[sha]} y {idx})')
        else:sha_seen[sha]=idx
        decision=row['review_decision'].strip().lower()
        purity=row['purity_judgement'].strip().lower()
        reviewer=row['reviewer_id'].strip()
        date=row['review_date_utc'].strip()
        if not decision or not purity or not reviewer or not date:
            incomplete.append(asset)
        elif decision not in VALID_DECISIONS or purity not in VALID_PURITY:
            invalid.append(asset)
    cross_source={key:sorted(v) for key,v in source_splits.items() if len(v)>1}
    cross_speaker={key:sorted(v) for key,v in speech_splits.items() if len(v)>1}
    if cross_source:errors.append(f'Source group compartido entre splits: {len(cross_source)}')
    if cross_speaker:errors.append(f'Hablante compartido entre splits: {len(cross_speaker)}')
    if invalid:errors.append(f'Revisiones con valores inválidos: {len(invalid)}')
    all_reviewed=len(incomplete)==0 and len(invalid)==0
    return {
        'schema':'hesychia.pi13-corpus-gate.v1',
        'scope':'CSV metadata validation; not audio listening or legal license verification',
        'input':str(path), 'input_sha256':file_hash(path),
        'n':len(rows),'splits':dict(splits),'acoustic_classes':dict(classes),
        'licenses_as_declared':dict(licenses),
        'unique_source_groups':len(source_splits),'unique_speakers_with_id':len(speech_splits),
        'duplicated_pcm_sha256':len(rows)-len(sha_seen),
        'source_groups_crossing_splits':cross_source,
        'speakers_crossing_splits':cross_speaker,
        'human_review_completed':len(rows)-len(incomplete)-len(invalid),
        'human_review_incomplete':len(incomplete),'human_review_invalid':len(invalid),
        'metadata_gate':'FAIL' if errors else 'PASS',
        'human_review_gate':'PASS' if all_reviewed else 'BLOCKED',
        'test_unsealing_authorized': False,
        'errors':errors,
        'limitations':['No detecta near-duplicates acústicos ni subsegmentos de una grabación',
                       'Un SHA único no demuestra independencia de fuente',
                       'Etiquetas de licencia no equivalen a aprobación jurídica de reutilización',
                       'Revisión humana y doble evaluación no se automatizan por este script',
                       'Se necesita aprobación del asesor y freeze nuevo antes del test independiente']
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    result=quality_gate(a.manifest)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('n','metadata_gate','human_review_gate','test_unsealing_authorized')},ensure_ascii=False))
    if result['metadata_gate']!='PASS' or result['human_review_gate']!='PASS':
        raise SystemExit(2)

if __name__=='__main__':main()
