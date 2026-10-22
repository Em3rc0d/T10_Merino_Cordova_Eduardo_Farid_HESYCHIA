"""Train PI7-shape M4 causal mask CNN using provenance-gated real audio.

Only train/validation; test split is not loaded by the trainer. Training cannot
start without a manifest of locally available sources passing m4_data_gate.
Loss denominator stability change is PROSPECTIVE (requires ADR before thesis run).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

import numpy as np

from m4_causal_bridge import frames, features, ideal_mask, loss_components
from m4_real_corpus import load_approved_sources, scene


def _torch():
    import torch
    return torch


def build_model():
    """PI7 architecture: same dimensions, causal dilations; new Torch weights."""
    torch = _torch()
    from torch import nn
    import torch.nn.functional as F

    class LeftCausalConv(nn.Module):
        def __init__(self, in_channels, out_channels, dilation):
            super().__init__()
            self.dilation = dilation
            self.conv = nn.Conv1d(in_channels, out_channels, 3, dilation=dilation)
        def forward(self, x):
            return self.conv(F.pad(x, (self.dilation * 2, 0)))

    class M4(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(10, 16)
            self.layers = nn.ModuleList([
                LeftCausalConv(273, 128, 1), LeftCausalConv(128, 128, 2),
                LeftCausalConv(128, 128, 4)])
            self.final = nn.Linear(128, 257)
        def forward(self, x, target_id):
            b,t,_ = x.shape
            emb = self.embedding(target_id.long()).unsqueeze(1).expand(-1,t,-1)
            out = torch.cat((x,emb),dim=-1).transpose(1,2)
            for layer in self.layers:
                out = torch.relu(layer(out))
            return torch.sigmoid(self.final(out.transpose(1,2)))

    return M4()


def training_arrays(batch, torch):
    inputs, iris, mixtures, targets, protected = [], [], [], [], []
    for example in batch:
        x, t, p, b = (example[k] for k in ("mixture","target","protected","background"))
        spec_x = frames(x)
        inputs.append(features(spec_x))
        iris.append(ideal_mask(t,p,b))
        mixtures.append(np.abs(spec_x))
        targets.append(np.abs(frames(t)))
        protected.append(np.abs(frames(p)))
    return [torch.as_tensor(np.stack(a),dtype=torch.float32) for a in
            (inputs,iris,mixtures,targets,protected)]


def fit(registry, out, *, seed=42, epochs=2, train_steps=2,
        val_steps=1, batch_size=2, duration=1.0,
        target_absent_ratio=.25, speech_weight=0.,
        experimental_pseudo=False):
    torch = _torch()
    torch.set_num_threads(min(2,torch.get_num_threads()))
    torch.manual_seed(seed)
    np.random.seed(seed)
    if any(v < 1 for v in (epochs,train_steps,val_steps,batch_size)):
        raise ValueError("need positive epochs/steps/batch")
    if not (0 <= target_absent_ratio < 1 and 0 <= speech_weight <= 1):
        raise ValueError("invalid ratio/weight")
    source_rows, gate = load_approved_sources(registry,experimental_pseudo=experimental_pseudo)
    rg_hash = hashlib.sha256(Path(registry).read_bytes()).hexdigest()
    model=build_model()
    opt=torch.optim.Adam(model.parameters(),lr=0.001)
    rng_train=np.random.default_rng(seed)
    # Deterministic and independent RNG streams for val / train.
    rng_val=np.random.default_rng(seed+10000)
    log=[]
    best_val=float("inf")
    best_state=None
    for epoch in range(epochs):
        model.train()
        losses=[]
        for _ in range(train_steps):
            batch=[scene(source_rows,split="train",rng=rng_train,seconds=duration,
                         target_present=bool(rng_train.random()>=target_absent_ratio),
                         target_snr_db=float(rng_train.choice([-5,0,5,10])))
                   for _ in range(batch_size)]
            xi, irm, xm, tg, pr=training_arrays(batch,torch)
            masks=model(xi,torch.full((len(batch),),8,dtype=torch.long))
            loss,_=loss_components(masks,irm,xm,tg,pr,speech_weight=speech_weight)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite loss")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
        model.eval()
        vals=[]
        with torch.no_grad():
            for _ in range(val_steps):
                batch=[scene(source_rows,split="val",rng=rng_val,seconds=duration,
                             target_present=bool(rng_val.random()>=target_absent_ratio),
                             target_snr_db=float(rng_val.choice([-5,0,5,10])))
                       for _ in range(batch_size)]
                xi,irm,xm,tg,pr=training_arrays(batch,torch)
                pred=model(xi,torch.full((len(batch),),8,dtype=torch.long))
                v,_=loss_components(pred,irm,xm,tg,pr,speech_weight=speech_weight)
                vals.append(float(v.item()))
        val=float(np.mean(vals))
        log.append(dict(epoch=epoch+1,train_loss=float(np.mean(losses)),val_loss=val))
        if val < best_val:
            best_val=val
            best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    assert best_state is not None
    output=Path(out)
    output.mkdir(parents=True,exist_ok=True)
    checkpoint=output/"m4_causal_preliminary.pt"
    torch.save(best_state,checkpoint)
    ck_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    summary=dict(status="engineering_experiment_not_thesis_evidence",
                 purpose="causal_data_to_CNN_end_to_end",
                 seed=seed,epochs=epochs,train_steps=train_steps,val_steps=val_steps,
                 batch_size=batch_size,duration_s=duration,train_val_only=True,
                 validation_selected_epoch=int(np.argmin([x['val_loss'] for x in log]))+1,
                 checkpoint_sha256=ck_hash,registry_sha256=rg_hash,
                 model_parameters=sum(x.numel() for x in model.parameters()),
                 loss="PI7 L0 denominator prospectively stabilized; not formally approved",
                 speech_weight=speech_weight,
                 reference_scope=gate['reference_scope'],training_history=log,
                 platform=platform.platform(),torch_version=torch.__version__,
                 limitations=["No test split read", "No real dataset verified by this script alone",
                              "Manifest may contain inaccurate isolated status",
                              "No TFLite export", "No latency measured", "No clinical claims"])
    (output/"run_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--epochs",type=int,default=2)
    p.add_argument("--train-steps",type=int,default=2)
    p.add_argument("--val-steps",type=int,default=1)
    p.add_argument("--batch-size",type=int,default=2)
    p.add_argument("--duration",type=float,default=1.0)
    p.add_argument("--speech-weight",type=float,default=0.)
    p.add_argument("--allow-pseudo-stems",action="store_true")
    a=p.parse_args()
    print(json.dumps(fit(a.registry,a.out,epochs=a.epochs,train_steps=a.train_steps,val_steps=a.val_steps,
                         batch_size=a.batch_size,duration=a.duration,speech_weight=a.speech_weight,
                         experimental_pseudo=a.allow_pseudo_stems),indent=2))
