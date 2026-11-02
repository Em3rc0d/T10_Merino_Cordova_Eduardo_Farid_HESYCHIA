"""Experimental multilabel M2 candidate for OFFLINE mixtures, not streaming SED.

Whole-clip pooling is explicit. Alert decisions are estimated, never taken from
clean stems during integrated inference. Thresholds are calibrated on val only.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .common import canonical_hash, create_json, read_json, sha256, write_json
from .corpus import TARGETS, load_registry
from .model import features, frontend_contract, spectrum
from .scenes import build_scene, load_recipes

EVENTS = TARGETS + ("speech", "alert")


class EventCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.convs = nn.ModuleList([nn.Conv1d(257, 64, 3), nn.Conv1d(64, 64, 3, dilation=2),
                                    nn.Conv1d(64, 64, 3, dilation=4)])
        self.norms = nn.ModuleList([nn.LayerNorm(64) for _ in self.convs])
        self.head = nn.Linear(64, len(EVENTS))

    def forward(self, x):
        z = x.transpose(1, 2)
        for conv, norm, dilation in zip(self.convs, self.norms, (1, 2, 4)):
            z = F.silu(norm(conv(F.pad(z, (2 * dilation, 0))).transpose(1, 2))).transpose(1, 2)
        frame_logits = self.head(z.transpose(1, 2))
        # Multilabel logits, not softmax mutually exclusive event labels.
        return torch.logsumexp(frame_logits, dim=1) - math.log(frame_logits.shape[1])


def _cache(root, registry, split):
    recipes = load_recipes(root, split)
    xs, ys = [], []
    for recipe in recipes:
        mix, _ = build_scene(root, registry, recipe)
        with torch.no_grad():
            xs.append(features(spectrum(torch.from_numpy(mix)))[0])
        ys.append([float(cls in recipe["parts"]) for cls in EVENTS])
    return torch.stack(xs), torch.tensor(ys)


def classification_metrics(probabilities, labels, thresholds):
    predicted = probabilities >= np.asarray(thresholds)[None]
    labels = np.asarray(labels, dtype=bool)
    rows = []
    for k, cls in enumerate(EVENTS):
        tp = int(np.sum(predicted[:, k] & labels[:, k]))
        fp = int(np.sum(predicted[:, k] & ~labels[:, k]))
        fn = int(np.sum(~predicted[:, k] & labels[:, k]))
        precision, recall = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
        rows.append(dict(event=cls, tp=tp, fp=fp, fn=fn, precision=precision, recall=recall,
                         f1=2 * tp / max(2 * tp + fp + fn, 1)))
    return dict(macro_f1=float(np.mean([r["f1"] for r in rows])), per_class=rows)


def fit_events(root, out, *, seed=141, epochs=20, pilot_unreviewed=False):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(seed)
    torch.set_num_threads(3)
    torch.use_deterministic_algorithms(True)
    registry = load_registry(root, allow_unreviewed=pilot_unreviewed)
    contract = read_json(Path(root) / "scene_contract.json")
    if canonical_hash(registry) != contract["registry_sha256"]:
        raise ValueError("Registry and mixtures differ")
    xtrain, ytrain = _cache(root, registry, "train")
    xval, yval = _cache(root, registry, "val")
    model = EventCNN()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.0005, weight_decay=.005)
    positive_weight = (len(ytrain) - ytrain.sum(0)) / ytrain.sum(0).clamp_min(1)
    rng, history = np.random.default_rng(seed), []
    best, stale = float("inf"), 0
    for epoch in range(epochs):
        model.train()
        train_loss = []
        for ids in np.array_split(rng.permutation(len(ytrain)), math.ceil(len(ytrain) / 32)):
            logits = model(xtrain[ids])
            loss = F.binary_cross_entropy_with_logits(logits, ytrain[ids], pos_weight=positive_weight)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
            train_loss.append(float(loss.detach()))
        model.eval()
        with torch.no_grad():
            logits = torch.cat([model(x) for x in xval.split(32)])
            val = float(F.binary_cross_entropy_with_logits(logits, yval, pos_weight=positive_weight))
        history.append(dict(epoch=epoch + 1, train_loss=float(np.mean(train_loss)), val_loss=val))
        print(f"M2 epoch={epoch+1} val={val:.5f}", flush=True)
        if val < best - 1e-5:
            best, stale = val, 0
            torch.save(dict(state_dict=model.state_dict(), events=list(EVENTS),
                            frontend=frontend_contract(), corpus_sha256=canonical_hash(registry),
                            scene_contract_sha256=canonical_hash(contract), seed=seed,
                            epoch=epoch + 1), out / "events.pt")
        else:
            stale += 1
        if stale >= 5:
            break
    obj = torch.load(out / "events.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(obj["state_dict"])
    with torch.no_grad():
        probabilities = torch.sigmoid(torch.cat([model(x) for x in xval.split(32)])).numpy()
    labels = yval.numpy()
    thresholds = []
    for cls in range(len(EVENTS)):
        options = np.arange(.05, 1., .05)
        scores = []
        for t in options:
            pred = probabilities[:, cls] >= t
            tp, fp, fn = np.sum(pred & (labels[:, cls] == 1)), np.sum(pred & (labels[:, cls] == 0)), np.sum(~pred & (labels[:, cls] == 1))
            scores.append(2 * tp / max(2 * tp + fp + fn, 1))
        thresholds.append(float(options[int(np.argmax(scores))]))
    # Conservative alert threshold: preserve every validation alert; test recall may fall.
    positives = probabilities[labels[:, 3] == 1, 3]
    if not len(positives):
        raise ValueError("No alert positives in validation")
    thresholds[3] = min(thresholds[3], float(positives.min()) * .99)
    calibration = dict(events=list(EVENTS), thresholds=thresholds,
                       selection="target/speech maximum validation F1; alert additionally capped "
                                 "below minimum validation-positive score; no test tuning",
                       validation=classification_metrics(probabilities, labels, thresholds),
                       checkpoint_sha256=sha256(out / "events.pt"),
                       corpus_sha256=canonical_hash(registry), scene_contract_sha256=canonical_hash(contract),
                       test_audio_read=False, mode="experimental_offline_clip_multilabel",
                       streaming_compatible=False, automatic_safety_validated=False)
    create_json(out / "calibration.json", calibration)
    write_json(out / "history.json", history)
    return calibration


def load_events(path, calibration_path):
    calibration = read_json(calibration_path)
    if sha256(path) != calibration["checkpoint_sha256"]:
        raise ValueError("Event checkpoint/calibration mismatch")
    obj = torch.load(path, map_location="cpu", weights_only=True)
    if obj["frontend"] != frontend_contract() or obj["events"] != list(EVENTS):
        raise ValueError("Event frontend/taxonomy mismatch")
    model = EventCNN().eval()
    model.load_state_dict(obj["state_dict"])
    return model, calibration
