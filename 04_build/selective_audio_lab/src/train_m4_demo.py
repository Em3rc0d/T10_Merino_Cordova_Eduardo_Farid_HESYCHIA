"""Train a NEW drilling-only synthetic engineering checkpoint, never final M4."""
from __future__ import annotations

import argparse
import copy
import json
import platform
from pathlib import Path

import numpy as np
import torch

from audio_core import SR, N_FFT, HOP, EPS, stft_complex, synthesize_drilling
from m4_experimental import MODEL_ROOT, TARGET_ID, CONTRACT, CHECKPOINT, MANIFEST, build_model, file_sha


def train(out=MODEL_ROOT, *, epochs=8, train_scenes=24, val_scenes=8, seed=42):
    if epochs < 1 or train_scenes < 2 or val_scenes < 1:
        raise ValueError("Invalid training dimensions")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Refusing to overwrite an existing checkpoint; use a new directory")
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    train_seeds = list(range(100, 100 + train_scenes))
    val_seeds = list(range(100000, 100000 + val_scenes))
    if set(train_seeds) & set(val_seeds):
        raise ValueError("Overlapping procedural scene seeds")
    sources = []
    xs, ys = [], []
    for split, seeds in (("train", train_seeds), ("val", val_seeds)):
        for scene_seed in seeds:
            p, t, b = synthesize_drilling(scene_seed)
            raw = p + t + b
            scale = (np.max(np.abs(raw)) + EPS) / .95
            mix, target, rest = raw / scale, t / scale, (p + b) / scale
            xs.append(np.log1p(20 * np.abs(stft_complex(mix)).T).astype(np.float32))
            tm, rm = np.abs(stft_complex(target)), np.abs(stft_complex(rest))
            ys.append((tm / (tm + rm + EPS)).T.astype(np.float32))
            import hashlib
            sources.append({"split": split, "seed": scene_seed,
                            "mixture_float32_sha256": hashlib.sha256(mix.astype(np.float32).tobytes()).hexdigest()})
    x, y = torch.from_numpy(np.array(xs)), torch.from_numpy(np.array(ys))
    ids = torch.full((len(xs),), TARGET_ID, dtype=torch.long)
    model = build_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    loss_fn = torch.nn.MSELoss()
    before = [p.detach().clone() for p in model.parameters()]
    with torch.no_grad():
        initial = float(loss_fn(model(x[:train_scenes], ids[:train_scenes]), y[:train_scenes]))
    history, best_loss, best_state = [], float("inf"), None
    for epoch in range(epochs):
        model.train()
        for batch in torch.randperm(train_scenes).split(4):
            optimizer.zero_grad()
            loss = loss_fn(model(x[batch], ids[batch]), y[batch])
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            tr = float(loss_fn(model(x[:train_scenes], ids[:train_scenes]), y[:train_scenes]))
            va = float(loss_fn(model(x[train_scenes:], ids[train_scenes:]), y[train_scenes:]))
        history.append({"epoch": epoch + 1, "train_loss": tr, "val_loss": va})
        if va < best_loss:
            best_loss, best_state = va, copy.deepcopy(model.state_dict())
        print(json.dumps(history[-1]), flush=True)
    changed = any(not torch.equal(a, b) for a, b in zip(before, model.parameters()))
    if not changed or history[-1]["train_loss"] >= initial:
        raise ValueError("Gradient smoke did not pass")
    out.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, out / CHECKPOINT)
    (out / "training_history.json").write_text(json.dumps(history, indent=2) + "\n")
    (out / "training_sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    manifest = {
        "contract": CONTRACT, "model_id": "M4-DRILLING-EXPERIMENTAL-V1",
        "target_label": "drilling_synthetic", "target_id": TARGET_ID,
        "checkpoint_sha256": file_sha(out / CHECKPOINT), "format": "pytorch_state_dict",
        "parameters": sum(p.numel() for p in model.parameters()),
        "architecture": "Embedding 10x16; Conv1D causal 128 kernel3 dilation1/2/4; Dense257 sigmoid",
        "frontend": {"sr": SR, "n_fft": N_FFT, "hop": HOP,
                     "feature": "log1p(20*abs(STFT))", "mode": "offline_centered"},
        "seed": seed, "epochs": epochs, "train_scenes": train_scenes, "val_scenes": val_scenes,
        "loss": "mask_MSE_engineering_only_not_PI7_L0",
        "initial_train_loss": initial, "weights_changed": changed,
        "selected_epoch": min(history, key=lambda r: r["val_loss"])["epoch"],
        "selection": "minimum validation MSE; no scientific test used",
        "training_artifacts": {name: file_sha(out / name) for name in ("training_history.json", "training_sources.json")},
        "generator_sha256": file_sha(Path(__file__).with_name("audio_core.py")),
        "trainer_sha256": file_sha(Path(__file__)),
        "runtime_source_sha256": file_sha(Path(__file__).with_name("m4_experimental.py")),
        "environment": {"python": platform.python_version(), "torch": str(torch.__version__), "numpy": np.__version__, "device": "cpu"},
        "scientific_validation": "pending",
        "limitations": ["synthetic procedural drilling and tonal protected surrogate; no real speech",
                        "same generator for train/val/demo; seeds disjoint do not establish scientific independence",
                        "single trained target; no demonstrated multiclass conditioning",
                        "offline centered STFT and clip normalization; not streaming",
                        "new PyTorch weights; not a conversion of prior Keras checkpoints",
                        "MSE smoke loss; D0-D5, RNF-04, TFLite, hardware and clinical validation pending"],
    }
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(MODEL_ROOT))
    p.add_argument("--epochs", type=int, default=8)
    args = p.parse_args()
    print(json.dumps(train(args.out, epochs=args.epochs), indent=2))
