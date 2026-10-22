"""End-to-end engineering smoke with artificial WAV files; no real source evidence."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'experiments'))
from m4_training_checks import fixture
from train_m4_real import fit,build_model
from m4_real_corpus import load_approved_sources,scene
from m4_causal_bridge import reconstruct_stream,StreamingTorchGain


def main():
    out=ROOT/'artifacts'
    out.mkdir(parents=True,exist_ok=True)
    r=fixture(out)
    details=fit(r,out/'checkpoint',epochs=6,train_steps=4,val_steps=2,batch_size=4,
                duration=.5,target_absent_ratio=.25,speech_weight=0.0)
    source_rows,_=load_approved_sources(r)
    # Only a train scenario; DO NOT evaluate or access test audio in this smoke.
    ex=scene(source_rows,split='train',rng=np.random.default_rng(100),seconds=.5)
    model=build_model()
    model.load_state_dict(torch.load(out/'checkpoint/m4_causal_preliminary.pt',map_location='cpu',weights_only=True))
    y=reconstruct_stream(ex['mixture'],StreamingTorchGain(model))
    sf.write(out/'fixture_input.wav',ex['mixture'],16000)
    sf.write(out/'fixture_output.wav',y,16000)
    summary={'kind':'ARTIFICIAL_WAV_FIXTURE_ONLY',
             'result':'ENGINEERING_PIPELINE_PASS',
             'source_splits':'train/val/test fixture; trainer only loads train+val',
             'epochs':6,'checkpoint_sha256':details['checkpoint_sha256'],
             'validation_loss_last':details['training_history'][-1]['val_loss'],
             'trained_model_sha256':details['checkpoint_sha256'],
             'output_finite':bool(np.isfinite(y).all()),
             'audio_samples':len(y),
             'warning':'This synthetic 0.5s test is not real siren/voice training nor scientific evidence.'}
    (out/'fixture_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
