import csv
import importlib.util
from pathlib import Path
import pytest

BASE=Path(__file__).parents[1]/'scripts'
def mod(name):
    spec=importlib.util.spec_from_file_location(name, BASE/(name+'.py'))
    x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x

def write(path,fields,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def test_manifest_does_not_admit_unreviewed(tmp_path):
    x=mod('pi13_corpus_gate');p=tmp_path/'m.csv';h='0'*64
    fields=['asset_id','split','source_group','pcm_sha256','reviewer_id','review_date_utc','purity_judgement','review_decision']
    write(p,fields,[dict(zip(fields,['A','train','g1',h,'','','',''])),
                   dict(zip(fields,['B','test','g2','f'*64,'','','','']))])
    r=x.quality_gate(p)
    assert r['metadata_gate']=='PASS' and r['human_review_gate']=='BLOCKED'
    assert not r['test_unsealing_authorized']

def test_cross_split_group_blocks(tmp_path):
    x=mod('pi13_corpus_gate');p=tmp_path/'m.csv'
    fields=['asset_id','split','source_group','pcm_sha256','reviewer_id','review_date_utc','purity_judgement','review_decision']
    rows=[dict(zip(fields,[f'a{i}',s,'same',f'{i:064x}','rev','2026-11-08','isolated','eligible'])) for i,s in enumerate(('train','test'),1)]
    write(p,fields,rows)
    assert x.quality_gate(p)['metadata_gate']=='FAIL'

def test_analysis_symmetric_arms_and_deterministic(tmp_path):
    x=mod('pi14_analysis');p=tmp_path/'r.csv'
    fields=['scene_id','source_group','speaker_group','mix_sha256','method','a_target_db','a_protected_db'];rows=[]
    for i in range(12):
        for m,a,b in [('DSP',3,0.4),('CNN',5,0.6),('ORACLE',8,0.2)]:
            rows.append(dict(zip(fields,[str(i),f'G{i//2}',f'S{i//3}',f'{i+1:064x}',m,str(a),str(b)])))
    write(p,fields,rows)
    a=x.analyze(p,n_boot=200);b=x.analyze(p,n_boot=200)
    assert a['estimands']==b['estimands']
    assert a['estimands']['cnn_minus_dsp_target_db']['mean']==2
    assert a['historical_both_ok']['CNN']['n']==0
    assert a['oracle_gap_target_db']['gap_closure_fraction']==pytest.approx(0.4)

def test_analysis_rejects_missing_method(tmp_path):
    x=mod('pi14_analysis');p=tmp_path/'r.csv'
    fields=['scene_id','source_group','speaker_group','mix_sha256','method','a_target_db','a_protected_db']
    write(p,fields,[dict(zip(fields,['1','g','s','f'*64,'CNN','1','0.2']))])
    with pytest.raises(ValueError):x.read_pairs(p)

def test_kappa_valid_and_degenerate(tmp_path):
    x=mod('pi13_agreement');p=tmp_path/'r.csv'
    columns=['asset_id','reviewer_id','review_decision']
    rows=[{'asset_id':str(i),'reviewer_id':rid,'review_decision':val}
          for i,vals in enumerate((('eligible','eligible'),('eligible','reject'),('reject','reject'),('restricted','restricted')))
          for rid,val in zip(('blind1','blind2'),vals)]
    write(p,columns,rows)
    r=x.calculate(p)
    assert r['pairs']==4 and r['cohen_kappa'] is not None and r['observed_agreement']==0.75
    rows=[{'asset_id':'X','reviewer_id':rid,'review_decision':'eligible'} for rid in ('blind1','blind2')]
    write(p,columns,rows)
    assert x.calculate(p)['cohen_kappa'] is None


def test_kappa_stable_under_row_permutation(tmp_path):
    x=mod('pi13_agreement')
    columns=['asset_id','reviewer_id','review_decision']
    rows=[{'asset_id':a,'reviewer_id':rid,'review_decision':dec}
          for a, ds in [('a',('eligible','reject')),('b',('reject','eligible'))]
          for rid,dec in zip(('reviewer_a','reviewer_b'),ds)]
    p=tmp_path/'review.csv'
    write(p,columns,rows)
    expected=x.calculate(p)
    assert expected['cohen_kappa'] == -1.0
    # Al alterar el orden de ingreso, la concordancia no debe cambiar.
    write(p,columns,[rows[1],rows[0],rows[2],rows[3]])
    actual=x.calculate(p)
    assert actual['cohen_kappa']==expected['cohen_kappa']
    assert actual['reviewer_column_order']==['reviewer_a','reviewer_b']


def test_kappa_rejects_mismatched_reviewer_pairs(tmp_path):
    x=mod('pi13_agreement')
    columns=['asset_id','reviewer_id','review_decision']
    rows=[{'asset_id':'a','reviewer_id':'A','review_decision':'eligible'},
          {'asset_id':'a','reviewer_id':'B','review_decision':'eligible'},
          {'asset_id':'b','reviewer_id':'A','review_decision':'reject'},
          {'asset_id':'b','reviewer_id':'C','review_decision':'reject'}]
    p=tmp_path/'review.csv'
    write(p,columns,rows)
    with pytest.raises(ValueError, match='mismos dos'):
        x.calculate(p)


def test_offline_benchmark_hops_and_warmup(tmp_path):
    x=mod('pi14_benchmark_summary');p=tmp_path/'latency.csv'
    fields=['run_id','hop_index','stft_ms','m4_ms','istft_ms','total_ms','chunk_duration_ms','peak_rss_mb']
    rows=[dict(zip(fields,['r1',str(i),'0.1','1.2','0.2','2.0','10','120'])) for i in range(60)]
    write(p,fields,rows)
    res=x.summarize(p,warmup_hops=10)
    assert res['run_count']==1 and res['samples_after_warmup']==50
    assert res['latency_ms']['total_ms']['p95_ms']==2.0
    assert res['real_time_factor_total']==pytest.approx(0.2)
    assert res['peak_rss_mb_max']==120


def test_offline_benchmark_rejects_duplicate_index(tmp_path):
    x=mod('pi14_benchmark_summary');p=tmp_path/'latency.csv'
    fields=['run_id','hop_index','stft_ms','m4_ms','istft_ms','total_ms','chunk_duration_ms']
    rows=[dict(zip(fields,['r1','1','0.1','1.2','0.2','2.0','10'])) for i in range(60)]
    write(p,fields,rows)
    with pytest.raises(ValueError,match='repetido'):
        x.summarize(p)


def test_freeze_preflight_blocks_pending_approval(tmp_path):
    x=mod('pi13_freeze_preflight')
    sample=Path(__file__).parents[1]/'fixtures'/'PI13_FREEZE_CONFIG_TEMPLATE.json'
    res=x.check(sample)
    assert res['status']=='BLOCKED' and res['human_authorization_to_unseal'] is False
    assert len(res['blockers'])>=5


def test_freeze_preflight_blocks_exposed_dataset_even_if_flagged(tmp_path):
    x=mod('pi13_freeze_preflight')
    p=tmp_path/'plan.json';p.write_text('{"protocol_id":"p1","dataset_status":"exposed_v1","advisor_decisions":{}}')
    res=x.check(p)
    assert 'test no declarado como nuevo e independiente' in res['blockers']


def test_analysis_rejects_different_mixture_hash_for_same_scene(tmp_path):
    x=mod('pi14_analysis');p=tmp_path/'results.csv'
    fields=['scene_id','source_group','speaker_group','mix_sha256','method','a_target_db','a_protected_db']
    rows=[dict(zip(fields,['s1','g1','h1',f'{i:064x}',method,'3.2','0.5']))
          for i,method in enumerate(('CNN','DSP','ORACLE'),1)]
    write(p,fields,rows)
    with pytest.raises(ValueError,match='Mezcla distinta'):
        x.read_pairs(p)
