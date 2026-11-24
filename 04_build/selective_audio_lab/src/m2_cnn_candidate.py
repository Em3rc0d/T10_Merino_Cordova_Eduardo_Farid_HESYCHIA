"""M2 learned UrbanSound8K development; fold 10 is never decoded here."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import f1_score, recall_score, precision_score, accuracy_score, confusion_matrix

from semantic_features import load_audio, SR, N_FFT, HOP, N_MELS
from urbansound8k import (EXPECTED_CLASSES, load_metadata, metadata_path, audio_path,
                         validate_contract, split_metadata, assert_no_leakage)

SEEDS = (42, 43, 44)
LABELS = sorted(EXPECTED_CLASSES)
TARGET = 0.85
METADATA_SHA = "b207f7a53f9e5eb02a5dd71d58fb8b66c88c24c0637b926dc72d9d400a6a2354"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def features(path):
    y = load_audio(path)
    mel = librosa.feature.melspectrogram(y=y, sr=SR, n_fft=N_FFT,
                                        hop_length=HOP, n_mels=N_MELS, power=2)
    x = librosa.power_to_db(mel + 1e-12, ref=np.max)
    x = np.clip((x + 80.0) / 80.0, 0, 1).astype(np.float32)
    if not np.isfinite(x).all():
        raise ValueError(f"nonfinite audio feature: {path}")
    return x[None]


def build_data(root, frame, allowed):
    if not set(frame.fold.unique()).issubset(allowed):
        raise ValueError("forbidden fold access")
    xs, ys, names, hashes = [], [], [], []
    for row in frame.sort_values(["fold", "slice_file_name"]).itertuples():
        path = audio_path(root, int(row.fold), row.slice_file_name)
        xs.append(features(path))
        ys.append(int(row.classID))
        names.append(row.slice_file_name)
        hashes.append(sha(path))
    return TensorDataset(torch.from_numpy(np.stack(xs)), torch.tensor(ys)), names, hashes


class AcousticCNN(nn.Module):
    def __init__(self):
        super().__init__()
        blocks = []
        channels = (1, 32, 64, 128)
        for a, b in zip(channels, channels[1:]):
            blocks += [nn.Conv2d(a, b, 3, padding=1, bias=False), nn.BatchNorm2d(b),
                       nn.ReLU(), nn.Conv2d(b, b, 3, padding=1, bias=False),
                       nn.BatchNorm2d(b), nn.ReLU(), nn.MaxPool2d(2)]
        self.encoder = nn.Sequential(*blocks, nn.AdaptiveAvgPool2d((4, 4)))
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(128 * 4 * 4, 128),
                                  nn.ReLU(), nn.Dropout(0.3), nn.Linear(128, 10))

    def forward(self, x):
        return self.head(self.encoder(x))


def augment(x):
    # Train-only SpecAugment; never transform validation/test samples.
    x = x.clone()
    for sample in x:
        for axis, max_width in ((1, 8), (2, 30)):
            width = int(torch.randint(0, max_width + 1, (1,)).item())
            start = int(torch.randint(0, sample.shape[axis] - width + 1, (1,)).item())
            if axis == 1:
                sample[:, start:start + width, :] = 0
            else:
                sample[:, :, start:start + width] = 0
    return x


def metrics(y, p):
    return {"macro_f1": float(f1_score(y, p, labels=LABELS, average="macro", zero_division=0)),
            "macro_recall": float(recall_score(y, p, labels=LABELS, average="macro", zero_division=0)),
            "macro_precision": float(precision_score(y, p, labels=LABELS, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y, p))}


@torch.no_grad()
def predict(model, data, device):
    model.eval()
    y, p = [], []
    for x, labels in DataLoader(data, batch_size=32, shuffle=False):
        p.extend(model(x.to(device)).argmax(1).cpu().tolist())
        y.extend(labels.tolist())
    return y, p


def partitions(root):
    report = validate_contract(root, require_official_shape=True, verify_audio=False)
    if not report.filename_metadata_consistency_ok or not report.occurrence_fold_consistency_ok:
        raise ValueError("invalid dataset identity or occurrence leakage")
    if sha(metadata_path(root)) != METADATA_SHA:
        raise ValueError("metadata differs from historical official dataset")
    train, val, test = split_metadata(load_metadata(root))
    assert_no_leakage(train, val, test)
    return train, val, test


def source_hashes():
    root = Path(__file__).resolve().parent
    return {name: sha(root / name) for name in
            ("m2_cnn_candidate.py", "semantic_features.py", "urbansound8k.py")}


def run_development(root, out, device):
    train, val, _ = partitions(root)
    out.mkdir(parents=True, exist_ok=False)
    tr, _, th = build_data(root, train, set(range(1, 9)))
    va, names, vh = build_data(root, val, {9})
    if set(th) & set(vh):
        raise ValueError("exact audio hash overlap between development splits")
    counts = torch.bincount(tr.tensors[1], minlength=10).float()
    if (counts == 0).any():
        raise ValueError("missing training class")
    weights = (counts.mean() / counts).sqrt().to(device)
    candidates = []
    for seed in SEEDS:
        seed_all(seed)
        model = AcousticCNN().to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
        loss_fn = nn.CrossEntropyLoss(weight=weights)
        loader = DataLoader(tr, batch_size=32, shuffle=True,
                            generator=torch.Generator().manual_seed(seed))
        best, stale, history = None, 0, []
        checkpoint = out / f"seed{seed}.pt"
        for epoch in range(1, 51):
            model.train()
            total = 0.0
            for x, y in loader:
                opt.zero_grad(set_to_none=True)
                loss = loss_fn(model(augment(x).to(device)), y.to(device))
                loss.backward()
                opt.step()
                total += float(loss.detach()) * len(y)
            y, p = predict(model, va, device)
            m = metrics(y, p)
            score = (m["macro_f1"], m["macro_recall"])
            history.append({"epoch": epoch, "train_loss": total / len(tr), **m})
            if best is None or score > best:
                best, stale = score, 0
                torch.save(model.state_dict(), checkpoint)
                selected = {"seed": seed, "epoch": epoch, **m,
                            "checkpoint": checkpoint.name, "predictions": p}
            else:
                stale += 1
            if stale >= 8:
                break
        write_json(out / f"history_seed{seed}.json", history)
        candidates.append(selected)
    winner = max(candidates, key=lambda c: (c["macro_f1"], c["macro_recall"], -c["seed"]))
    pd.DataFrame({"slice_file_name": names, "fold": 9, "y_true": va.tensors[1].tolist(),
                  "y_pred": winner["predictions"]}).to_csv(out / "validation_predictions.csv", index=False)
    pd.DataFrame(confusion_matrix(va.tensors[1].numpy(), winner["predictions"], labels=LABELS),
                 index=[EXPECTED_CLASSES[i] for i in LABELS],
                 columns=[EXPECTED_CLASSES[i] for i in LABELS]).to_csv(out / "validation_confusion.csv")
    write_json(out / "development_audio_hashes.json", {"train": th, "validation": vh})
    manifest = {"schema": "hesychia.m2-cnn-freeze.v1", "status": "DEVELOPMENT_ONLY",
                "fold10_audio_read": False, "fold10_previously_observed_baseline": True,
                "train_folds": list(range(1, 9)), "validation_folds": [9],
                "test_folds": [10], "metadata_sha256": METADATA_SHA,
                "sources": source_hashes(), "seeds": list(SEEDS), "target_macro_f1": TARGET,
                "selection": "max fold9 macro-f1 then macro-recall then lowest seed",
                "candidates": [{k:v for k,v in c.items() if k != "predictions"} for c in candidates],
                "selected": {k:v for k,v in winner.items() if k != "predictions"},
                "artifacts": {p.name: sha(p) for p in out.iterdir() if p.is_file()},
                "environment": {"python": platform.python_version(), "torch": str(torch.__version__),
                                "librosa": librosa.__version__, "numpy": np.__version__, "device": str(device)}}
    write_json(out / "freeze.json", manifest)
    return manifest


def run_test(root, out, freeze_sha, device):
    freeze = out / "freeze.json"
    if sha(freeze) != freeze_sha:
        raise ValueError("freeze SHA mismatch; publish freeze before test")
    manifest = json.loads(freeze.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "hesychia.m2-cnn-freeze.v1" or
            manifest.get("status") != "DEVELOPMENT_ONLY" or
            manifest.get("fold10_audio_read") is not False or
            manifest.get("sources") != source_hashes() or
            manifest.get("target_macro_f1") != TARGET):
        raise ValueError("invalid freeze or changed evaluator")
    for name, digest in manifest["artifacts"].items():
        if Path(name).name != name or sha(out / name) != digest:
            raise ValueError("artifact identity mismatch")
    _, _, test = partitions(root)
    selected = manifest["selected"]["checkpoint"]
    if selected not in manifest["artifacts"]:
        raise ValueError("unfrozen checkpoint")
    model = AcousticCNN().to(device)
    model.load_state_dict(torch.load(out / selected, map_location=device, weights_only=True))
    # Exclusive receipt precedes any test audio access; no silent retries.
    write_json(out / "test_attempt.json", {"freeze_sha256": freeze_sha, "status": "ATTEMPT_STARTED"})
    te, names, hashes = build_data(root, test, {10})
    development = json.loads((out / "development_audio_hashes.json").read_text())
    if set(hashes) & (set(development["train"]) | set(development["validation"])):
        raise ValueError("exact audio hash overlap with development")
    y, p = predict(model, te, device)
    result = metrics(y, p)
    pd.DataFrame({"slice_file_name": names, "fold": 10, "y_true": y, "y_pred": p}).to_csv(
        out / "test_predictions.csv", index=False)
    pd.DataFrame(confusion_matrix(y, p, labels=LABELS),
                 index=[EXPECTED_CLASSES[i] for i in LABELS],
                 columns=[EXPECTED_CLASSES[i] for i in LABELS]).to_csv(out / "test_confusion.csv")
    report = {"schema": "hesychia.m2-cnn-test.v1", "freeze_sha256": freeze_sha,
              "previously_observed_baseline": True, "independent_confirmation": False,
              "metrics": result, "rnf03_threshold_met_on_historical_fold": result["macro_f1"] >= TARGET,
              "artifacts": {n: sha(out / n) for n in ("test_predictions.csv", "test_confusion.csv")}}
    write_json(out / "test_report.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("develop", "test"))
    p.add_argument("--dataset-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--device", default="cpu")
    p.add_argument("--freeze-sha")
    p.add_argument("--ack-historical-test", action="store_true")
    a = p.parse_args()
    if a.mode == "test" and (not a.freeze_sha or not a.ack_historical_test):
        p.error("test requires published freeze SHA and explicit historical test acknowledgement")
    result = (run_development(a.dataset_root, a.out, torch.device(a.device))
              if a.mode == "develop" else
              run_test(a.dataset_root, a.out, a.freeze_sha, torch.device(a.device)))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
