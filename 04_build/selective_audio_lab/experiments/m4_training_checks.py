from __future__ import annotations
import csv
import hashlib
import pathlib
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from m4_causal_bridge import loss_components, reconstruct_stream
from m4_real_corpus import load_approved_sources,scene
from train_m4_real import build_model,fit,training_arrays


def fixture(tmp):
    fields=['source_id','role','split','recording_id','speaker_id','path','sha256','license','reference_grade']
    rows=[]
    sr=16000
    t=np.arange(sr,dtype=np.float32)/sr
    for split_idx,split in enumerate(('train','val','test')):
        for role_idx,role in enumerate(('target','protected','background')):
            name=f'{split}_{role}'
            freq=(split_idx+1)*57+role_idx*150+210
            wave=(0.1*np.sin(2*np.pi*freq*t+0.02*split_idx)).astype(np.float32)
            file=pathlib.Path(tmp)/(name+'.wav')
            sf.write(file,wave,sr)
            rows.append(dict(source_id=name,role=role,split=split,recording_id=name,
                             speaker_id=f'speaker-{split}' if role=='protected' else '',path=file.name,
                             sha256=hashlib.sha256(file.read_bytes()).hexdigest(),license='FIXTURE_TEST_ONLY',
                             reference_grade='isolated' if role=='target' else 'speech' if role=='protected' else 'background'))
    manifest=pathlib.Path(tmp)/'registry.csv'
    with manifest.open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader();wr.writerows(rows)
    return manifest

class RealTrainingTests(unittest.TestCase):
    def test_manifest_and_target_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=fixture(tmp)
            rows,gate=load_approved_sources(manifest)
            self.assertEqual(gate['status'],'PASS')
            present=scene(rows,split='train',rng=np.random.default_rng(3),seconds=.1)
            absent=scene(rows,split='train',rng=np.random.default_rng(4),seconds=.1,target_present=False)
            self.assertTrue(np.any(present['target']!=0))
            self.assertTrue(np.all(absent['target']==0))
            self.assertTrue(np.isfinite(present['mixture']).all())
    def test_training_does_not_use_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=fixture(tmp)
            result=fit(manifest,pathlib.Path(tmp)/'out',epochs=2,train_steps=1,val_steps=1,
                       batch_size=2,duration=.1)
            self.assertTrue(result['train_val_only'])
            self.assertEqual(result['epochs'],2)
            self.assertTrue((pathlib.Path(tmp)/'out/m4_causal_preliminary.pt').is_file())
    def test_causal_model_prefix(self):
        import torch
        torch.manual_seed(12)
        model=build_model().eval()
        x=torch.rand(1,28,257)
        y=x.clone();y[:,22:]*=-10
        with torch.no_grad():
            a=model(x,torch.tensor([8]))
            b=model(y,torch.tensor([8]))
        torch.testing.assert_close(a[:,:22],b[:,:22],rtol=0,atol=0)
    def test_zero_target_loss_finite(self):
        import torch
        model=build_model()
        x=torch.rand(2,20,257)
        irm=torch.zeros_like(x)
        out=model(x,torch.tensor([8,8]))
        l,_=loss_components(out,irm,x,torch.zeros_like(x),x,speech_weight=0.1)
        self.assertTrue(bool(torch.isfinite(l)))
        l.backward()
        self.assertTrue(all(v.grad is None or torch.isfinite(v.grad).all() for v in model.parameters()))

if __name__=='__main__':unittest.main()

class StreamingNetworkTests(unittest.TestCase):
    def test_mask_stream_matches_full_causal_network(self):
        import torch
        from m4_causal_bridge import StreamingTorchGain, features, frames
        torch.manual_seed(7)
        model=build_model().eval()
        waveform=np.random.default_rng(81).normal(size=160*44).astype(np.float32)*.05
        f=features(frames(waveform))
        stream=StreamingTorchGain(model)
        gains=np.stack([stream(v) for v in f])
        with torch.no_grad():
            full=model(torch.as_tensor(f[None]),torch.tensor([8]))[0].numpy()
        expected=np.maximum(1-full,10**(-12/20))
        np.testing.assert_allclose(gains,expected,atol=1e-6)
        y=reconstruct_stream(waveform,StreamingTorchGain(model))
        self.assertTrue(np.isfinite(y).all())
        self.assertEqual(y.shape,waveform.shape)
