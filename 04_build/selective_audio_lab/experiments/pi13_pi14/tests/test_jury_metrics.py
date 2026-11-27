import csv
import importlib.util
from pathlib import Path

import pytest


ROOT=Path(__file__).resolve().parents[1]


def mod(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_supplemental_metric_means_do_not_change_primary_schema(tmp_path):
    a=mod('pi14_analysis_v2')
    rows=[]
    for scene,group in [('s1','g1'),('s2','g2'),('s3','g3')]:
        for method,at,ap,stoi,pesq in [
            ('CNN',4.0,0.4,0.94,3.7),
            ('DSP',3.0,0.5,0.92,3.5),
            ('ORACLE',7.0,0.2,0.97,4.0),
        ]:
            rows.append({
                'scene_id':scene,'source_group':group,'speaker_group':'speaker_'+group,
                'mix_sha256':('a' if scene=='s1' else 'b' if scene=='s2' else 'c')*64,
                'method':method,'a_target_db':at,'a_protected_db':ap,
                'si_sdri_protected_db':1.0,'snr_protected_vs_target_db':5.0,
                'snr_improvement_db':2.0,'stoi_protected':stoi,
                'pesq_wb_protected':pesq,
            })
    path=tmp_path/'confirmatory.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

    result=a.analyze(path,n_boot=200,seed=7,voice_margin_db=1.0)
    assert result['joint_decision']['target_superiority'] is True
    assert result['joint_decision']['voice_noninferiority'] is True
    assert result['method_means']['CNN']['stoi_protected_mean']==pytest.approx(0.94)
    assert result['method_means']['CNN']['pesq_wb_protected_mean']==pytest.approx(3.7)
    assert result['method_means']['CNN']['snr_improvement_db_mean']==pytest.approx(2.0)
    assert 'stoi_protected' not in result['estimands']


def test_optional_pesq_blank_is_ignored(tmp_path):
    a=mod('pi14_analysis_v2')
    rows=[{
        'scene_id':'s1','source_group':'g1','speaker_group':'sp1','mix_sha256':'d'*64,
        'method':'CNN','a_target_db':'1','a_protected_db':'0',
        'pesq_wb_protected':'','stoi_protected':'0.9'
    }]
    path=tmp_path/'one.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)
    metrics=a.optional_metric_means(path)
    assert 'pesq_wb_protected_mean' not in metrics['CNN']
    assert metrics['CNN']['stoi_protected_mean']==pytest.approx(0.9)
