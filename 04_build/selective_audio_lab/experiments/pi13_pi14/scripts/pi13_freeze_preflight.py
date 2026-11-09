#!/usr/bin/env python3
"""Preflight fail-closed para congelar un test INDEPENDIENTE de PI13.

Sólo comprueba metadatos y existencia/hash de artefactos. Nunca certifica
la validez real de la firma del asesor, licencias, independencia perceptual
ni autoriza por sí mismo abrir el test. NO ejecutar con el test V1 expuesto.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path

REQUIRED_ARTIFACTS=('test_scenes','corpus_review_report','checkpoint','evaluation_code','metric_protocol')
APPROVALS=('objectives','metric_rule','sample_design')
REQUIRED_TEST=('scene_id','source_group','speaker_group','split','mix_sha256')
SHA_RE=re.compile(r'^[0-9a-f]{64}$',re.I)

def check(config:Path):
    plan=json.loads(config.read_text(encoding='utf-8'))
    blockers=[];audit=[];hashes={};art=plan.get('artifacts') or {}
    if not plan.get('protocol_id'): blockers.append('protocol_id ausente')
    if plan.get('dataset_status')!='new_independent_test':blockers.append('test no declarado como nuevo e independiente')
    if not plan.get('test_not_inspected_attestation'):blockers.append('falta declaración test no inspeccionado')
    for name in APPROVALS:
        a=(plan.get('advisor_decisions') or {}).get(name) or {}
        if not a.get('approved') or not a.get('date') or not a.get('evidence_ref'):
            blockers.append('decisión del asesor pendiente: '+name)
    for name in REQUIRED_ARTIFACTS:
        path=art.get(name)
        if not path or not Path(path).is_file():
            blockers.append('artefacto no disponible: '+name)
        else:
            hashes[name]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if 'corpus_review_report' in hashes:
        try:
            rev=json.loads(Path(art['corpus_review_report']).read_text(encoding='utf-8'))
            if rev.get('human_review_gate')!='PASS' or rev.get('metadata_gate')!='PASS':
                blockers.append('auditoría corpus humana/metadatos sin PASS')
        except (ValueError,OSError) as ex:blockers.append('auditoría inválida: '+str(ex))
    stats={}
    if 'test_scenes' in hashes:
        try:
            with Path(art['test_scenes']).open(newline='',encoding='utf-8-sig') as f:
                r=csv.DictReader(f)
                if not r.fieldnames or not set(REQUIRED_TEST).issubset(r.fieldnames):
                    raise ValueError('columnas test_scenes insuficientes')
                rows=list(r)
            ids=[a['scene_id'] for a in rows]
            if len(ids)!=len(set(ids)) or any(not i for i in ids):blockers.append('scene_id repetido/vacío')
            if any(a['split']!='test' for a in rows):blockers.append('test_scenes contiene split no test')
            if any(not SHA_RE.fullmatch(a['mix_sha256']) for a in rows):blockers.append('hash de mezcla inválido')
            src={a['source_group'] for a in rows};spk={a['speaker_group'] for a in rows}
            if '' in src or '' in spk:blockers.append('grupos sin ID')
            stats={'scenes':len(rows),'source_groups':len(src),'speaker_groups':len(spk)}
            min_scenes=int(plan.get('min_test_scenes') or 30)
            min_sources=int(plan.get('min_source_groups') or 2)
            min_speakers=int(plan.get('min_speaker_groups') or 2)
            if min_scenes<30:blockers.append('cuota escenas inferior a 30')
            if len(rows)<min_scenes:blockers.append('insuficientes escenas nuevas')
            if len(src)<min_sources:blockers.append('insuficientes grupos fuente')
            if len(spk)<min_speakers:blockers.append('insuficientes grupos hablante')
        except (OSError,ValueError,KeyError) as ex:blockers.append('escenas de test inválidas: '+str(ex))
    if not plan.get('source_speaker_leakage_report_pass'):
        blockers.append('control independiente de fuga fuente/hablante no declarado PASS')
    if not plan.get('inter_rater_review_report_ref'):
        blockers.append('concordancia entre revisores no documentada')
    audit.append('No se ha verificado autenticidad de firmas, permisos de audio o datos no vistos')
    return {'schema':'hesychia.pi13-freeze-preflight.v1','plan_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
      'status':'BLOCKED' if blockers else 'READY_FOR_HUMAN_VERIFICATION',
      'human_authorization_to_unseal':False,'checks':stats,'artifact_sha256':hashes,'blockers':blockers,
      'disclaimers':audit}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();res=check(a.config)
    a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':res['status'],'blockers':len(res['blockers'])},ensure_ascii=False))
    if res['status']=='BLOCKED':raise SystemExit(2)
if __name__=='__main__':main()
