import csv,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
import pytest
from scipy.io import wavfile

ROOT=Path(__file__).resolve().parents[1]
def mod(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def build_review_fixture(tmp):
    a=tmp/'audio';a.mkdir();out=tmp/'out';out.mkdir()
    rows=[]
    for i in range(3):
        aid=f'esc50_{i}'
        wavfile.write(a/f'{aid}.wav',16000,np.ones(16000,dtype=np.float32)*(.01+i*.01))
        h=hashlib.sha256((a/f'{aid}.wav').read_bytes()).hexdigest()
        rows.append({'asset_id':aid,'pcm_sha256':h,'acoustic_class':'siren','split':'train','source_group':str(i),
                     'speaker_id':'','reviewer_id':'','review_date_utc':'','purity_judgement':'','review_decision':''})
    mf=tmp/'source_manifest.csv'
    with mf.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return a,out,mf,rows

def payload(wb,aid,decision='eligible',purity='isolated'):
    return {'asset_id':aid,'manifest_sha256':wb.manifest_sha256,'review_decision':decision,
            'purity_judgement':purity,'main_event_audible':'yes', 'speech_present':'no',
            'alarm_present':'yes','secondary_events':'', 'review_notes':'listened'}

def test_review_save_export_and_double_kappa(tmp_path):
    r=mod('pi13_review_workbench');a,out,mf,rows=build_review_fixture(tmp_path)
    w1=r.Workbench(mf,a,out,'reviewer_a');w2=r.Workbench(mf,a,out,'reviewer_b')
    for rec in rows:
        aid=rec['asset_id'];w1.save(payload(w1,aid))
        w2.save(payload(w2,aid,'restricted','minor_contamination') if aid==rows[0]['asset_id'] else payload(w2,aid))
    assert len(w1.reviews)==3
    merged=tmp_path/'merged.csv'
    assert r.merge_primary_manifest(mf,w1.output,'reviewer_a',merged)==(3,3)
    with merged.open() as f: assert all(v['review_decision']=='eligible' for v in csv.DictReader(f))
    double=tmp_path/'double.csv'
    response=r.combine_double_reviews([w1.output,w2.output],double)
    assert response['paired_assets']==3
    a=mod('pi13_agreement')
    assert a.calculate(double)['pairs']==3

def test_review_no_fake_eligibility_or_audio_mismatch(tmp_path):
    r=mod('pi13_review_workbench');a,out,mf,rows=build_review_fixture(tmp_path)
    w=r.Workbench(mf,a,out,'reviewer_a');aid=rows[0]['asset_id']
    with pytest.raises(ValueError):w.save(payload(w,aid,'eligible','mixed'))
    (a/f'{aid}.wav').write_bytes(b'not expected')
    with pytest.raises(ValueError):w.save(payload(w,aid))
    assert not w.output.exists()

def test_review_reject_path_traversal_and_manifest_change(tmp_path):
    r=mod('pi13_review_workbench');a,out,mf,rows=build_review_fixture(tmp_path)
    w=r.Workbench(mf,a,out,'reviewer_a')
    with pytest.raises(ValueError):w.save({**payload(w,rows[0]['asset_id']),'manifest_sha256':'0'*64})
    txt=mf.read_text().replace('esc50_0','../../evil')
    mf.write_text(txt)
    with pytest.raises(ValueError):r.Workbench(mf,a,out,'reviewer_a')

def test_model_forward_bench_with_true_checkpoint_contract(tmp_path):
    import torch
    b=mod('pi14_m4_forward_benchmark')
    src=tmp_path/'src'/'m4_scientific';src.mkdir(parents=True)
    (src/'__init__.py').write_text('')
    (src/'model.py').write_text('''\nimport torch\nfrom torch import nn\nSR=16000\nHOP=160\nclass Model(nn.Module):\n @property\n def receptive_frames(self):return 7\n def forward(self,x,labels):return torch.sigmoid(x[:,:,0:1])\n def gain(self,mask):return (1-mask).clamp_min(.1)\ndef features(x):return x.abs()\ndef spectrum(wave):\n x=wave.unfold(0,512,160)\n return torch.fft.rfft(x,dim=-1)[None]\ndef frontend_contract():return {'n_fft':512, 'sr':SR, 'hop':HOP}\ndef load_checkpoint(path):\n obj=torch.load(path,map_location='cpu',weights_only=True)\n if obj['frontend']!=frontend_contract():raise ValueError('bad frontend')\n return Model().eval(),obj\n''')
    checkpoint=tmp_path/'m4.pt';torch.save({'frontend':{'n_fft':512,'sr':16000,'hop':160}},checkpoint)
    result=b.benchmark(checkpoint,src.parent,tmp_path/'result',runs=5,warmup=1,hops=8,seconds=.20,threads=2)
    assert result['samples']>=5
    assert result['checkpoint_sha256']==hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert result['measurement_scope'].startswith('M4 forward+gain')
    assert (tmp_path/'result'/'m4_forward_samples.csv').exists()

def test_double_sample_reproducible_and_manifest_subset(tmp_path):
    r=mod('pi13_review_workbench');s=mod('pi13_double_sample')
    a,out,mf,rows=build_review_fixture(tmp_path)
    sample=tmp_path/'sample.csv';report=tmp_path/'sample.json'
    v=s.choose(mf,sample,report,rate=.4,seed=42,minimum=1)
    old_sha=v['selection_manifest_sha256']
    v2=s.choose(mf,sample,report,rate=.4,seed=42,minimum=1)
    assert old_sha==v2['selection_manifest_sha256']
    wb=r.Workbench(mf,a,out,'reviewer_b',sample_manifest=sample)
    assert len(wb.rows)==v['selected_items']
    assert all(aid in {x['asset_id'] for x in rows} for aid in wb.index)

def test_review_http_roundtrip(tmp_path):
    import subprocess,time,urllib.request,socket
    r=mod('pi13_review_workbench')
    a,out,mf,rows=build_review_fixture(tmp_path)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,str(ROOT/'scripts'/'pi13_review_workbench.py'),'serve',
        '--manifest',str(mf),'--audio-root',str(a),'--out-dir',str(out),
        '--reviewer','reviewer_a','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as response:
                    assert b'HESYCHIA' in response.read();break
            except OSError:time.sleep(.05)
        else:raise AssertionError('Workbench HTTP unavailable')
        aid=rows[0]['asset_id']
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/audio/{aid}',timeout=2) as response:
            assert response.headers['Content-Type']=='audio/wav'
            assert response.read()==(a/f'{aid}.wav').read_bytes()
        wb=r.Workbench(mf,a,out,'reviewer_a')
        post=json.dumps(payload(wb,aid)).encode()
        req=urllib.request.Request(f'http://127.0.0.1:{port}/save',data=post,
                headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=3) as response:
            assert json.load(response)['status']=='saved'
        assert r.Workbench(mf,a,out,'reviewer_a').reviews[aid]['review_decision']=='eligible'
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()
