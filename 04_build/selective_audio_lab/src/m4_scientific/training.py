"""Reproducible train/validation-only scientific candidate trainer."""
from __future__ import annotations

import contextlib
import csv
import os
import platform
import random
import shutil
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from .common import canonical_hash, create_json, read_json, sha256, write_json
from .corpus import TARGETS, load_registry
from .model import build_model, ModelConfig, features, frontend_contract, spectrum
from .scenes import build_scene, load_recipes


def code_hash():
    return canonical_hash({p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))})


def cache_scenes(root, registry, split):
    """Precompute selected split only. This function never requests test for training."""
    recipes = load_recipes(root, split)
    cache_key = canonical_hash(dict(cache_schema="v2_stems_nontarget_alertgate", frontend=frontend_contract(),
                                    corpus=canonical_hash(registry), recipes=canonical_hash(recipes)))
    cached = Path(root) / "cache" / f"{split}-{cache_key}.pt"
    if cached.exists():
        obj = torch.load(cached, map_location="cpu", weights_only=True, mmap=True)
        return obj, recipes
    size = len(recipes)
    arrays = None
    for i, recipe in enumerate(recipes):
        mix, stems = build_scene(root, registry, recipe)
        waves = np.stack([mix, stems[TARGETS[recipe["target_id"]]], stems["speech"],
                          stems[TARGETS[1 - recipe["target_id"]]]])
        with torch.no_grad():
            specs = spectrum(torch.from_numpy(waves))
            x, target, speech, nontarget = specs
            rest = x - target
            ideal = target.abs() / (target.abs() + rest.abs() + 1e-8)
            values = dict(features=features(x), ideal=ideal, mixture=x,
                          target=target, protected=speech.abs(), nontarget=nontarget,
                          alert_flag=torch.tensor(float(recipe["alert_present"]), dtype=torch.float32))
        if arrays is None:
            arrays = {k: np.empty((size,) + tuple(v.shape), dtype=v.numpy().dtype)
                      for k, v in values.items()}
        for key, value in values.items():
            arrays[key][i] = value.numpy()
        if (i + 1) % 400 == 0:
            print(f"cache {split}: {i + 1}/{size}", flush=True)
    tensors = {k: torch.from_numpy(v) for k, v in arrays.items()}
    cached.parent.mkdir(exist_ok=True)
    temp = cached.with_suffix(f".{os.getpid()}.tmp")
    torch.save(tensors, temp)
    os.replace(temp, cached)
    # File-backed tensors can be shared across independent training processes.
    del tensors, arrays
    return torch.load(cached, map_location="cpu", weights_only=True, mmap=True), recipes


def losses(model, prediction, batch, cfg, *, swapped_prediction=None):
    if cfg["loss"] == "selective_v2":
        from .v2_objective import constrained_selective_loss
        return constrained_selective_loss(model, prediction, batch, cfg,
                                          swapped_prediction=swapped_prediction)
    gain = model.gain(prediction)
    floor = 10 ** (-model.config.cap_db / 20)
    mse = (prediction - batch["ideal"]).square().mean()
    if cfg["loss"] == "mask_mse":
        return mse, {"mask_mse": mse}
    # Desired complex output preserves all non-target sources and leaves cap_db residual.
    desired = batch["mixture"] - (1. - floor) * batch["target"]
    residual = (gain * batch["mixture"] - desired).abs().mean(dim=(1, 2))
    reconstruction = (residual / batch["mixture"].abs().mean(dim=(1, 2)).clamp_min(1e-4)).mean()
    # Frozen mixture-estimated gain on known protected stem. It is never a predictor input.
    speech_power = batch["protected"].square()
    removed = ((1. - gain).square() * speech_power).sum(dim=(1, 2))
    protection = (removed / speech_power.sum(dim=(1, 2)).clamp_min(1e-6)).mean()
    total = mse + cfg["reconstruction_weight"] * reconstruction + cfg["speech_weight"] * protection
    return total, dict(mask_mse=mse, reconstruction=reconstruction, protection=protection)


def batches(cache, recipes, batch_size, order):
    for start in range(0, len(order), batch_size):
        ids = torch.as_tensor(order[start:start + batch_size], dtype=torch.long)
        yield {k: v[ids] for k, v in cache.items()}, torch.tensor(
            [recipes[int(i)]["target_id"] for i in ids], dtype=torch.long)


def fit(root, output, cfg, *, pilot_unreviewed=False):
    cfg = dict(cfg)
    seed = int(cfg["seed"])
    if cfg["loss"] not in ("composite", "mask_mse", "selective_v2") or cfg["epochs"] < 1 or cfg["batch_size"] < 1:
        raise ValueError("Invalid training configuration")
    if cfg["loss"] == "selective_v2" and cfg.get("conditioning", "class") != "class":
        raise ValueError("V2 class-contrast training requires class conditioning")
    if any(float(cfg.get(k, 0.)) < 0 for k in ("reconstruction_weight", "speech_weight")):
        raise ValueError("Negative loss weight")
    output = Path(output)
    # Never reuse a run directory, even after interruption.
    output.mkdir(parents=True, exist_ok=False)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(cfg.get("threads", 4)))
    torch.use_deterministic_algorithms(True)
    registry = load_registry(root, allow_unreviewed=pilot_unreviewed, splits=("train", "val"))
    scene_contract = read_json(Path(root) / "scene_contract.json")
    if canonical_hash(registry) != scene_contract["registry_sha256"]:
        raise ValueError("Registry differs from scene contract")
    manifest = dict(schema="m4-sci-training-v1", config=cfg,
                    registry_sha256=canonical_hash(registry),
                    scene_contract_sha256=canonical_hash(scene_contract),
                    code_sha256=code_hash(), frontend=frontend_contract(),
                    corpus_review=registry["review_status"],
                    pilot_unreviewed=pilot_unreviewed, test_audio_read=False,
                    selection="minimum fixed-validation loss; no test selection",
                    targets=list(TARGETS), torch_version=str(torch.__version__),
                    numpy_version=np.__version__, platform=platform.platform(),
                    cpu_threads=torch.get_num_threads(), deterministic_algorithms=True)
    create_json(output / "training_manifest.json", manifest)
    snapshots = output / "source_snapshot"
    snapshots.mkdir()
    for source in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(source, snapshots / source.name)
    train, train_recipes = cache_scenes(root, registry, "train")
    val, val_recipes = cache_scenes(root, registry, "val")
    model = build_model(ModelConfig(channels=int(cfg.get("channels", 96)),
                                    architecture=cfg.get("architecture", "temporal")))
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], weight_decay=cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=2, factor=.5)
    history, best, stale, best_epoch = [], float("inf"), 0, 0
    rng = np.random.default_rng(seed)
    start_time = time.monotonic()
    for epoch in range(1, cfg["epochs"] + 1):
        epoch_time = time.monotonic()
        model.train()
        train_losses = []
        for batch, labels in batches(train, train_recipes, cfg["batch_size"], rng.permutation(len(train_recipes))):
            frames_limit = int(cfg.get("training_frames", 0))
            warmup = int(cfg.get("warmup_frames", 0))
            if frames_limit:
                if frames_limit <= warmup or warmup < model.receptive_frames - 1:
                    raise ValueError("Training crop needs full causal receptive-field warmup")
                total_frames = batch["features"].shape[1]
                left = int(rng.integers(max(1, total_frames - frames_limit + 1)))
                batch = {k: v[:, left:left + frames_limit] for k, v in batch.items()}
            if cfg.get("conditioning", "class") == "none":
                labels = torch.zeros_like(labels)
            prediction = model(batch["features"], labels)
            swapped = (model(batch["features"], 1 - labels)
                       if cfg["loss"] == "selective_v2" and cfg.get("class_weight", 1.) else None)
            if frames_limit:
                prediction = prediction[:, warmup:]
                if swapped is not None:
                    swapped = swapped[:, warmup:]
                batch = {k: v[:, warmup:] for k, v in batch.items()}
            loss, _ = losses(model, prediction, batch, cfg, swapped_prediction=swapped)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
            train_losses.append((len(labels), float(loss.detach())))
        model.eval()
        val_losses = []
        with torch.no_grad():
            for batch, labels in batches(val, val_recipes, cfg["batch_size"], np.arange(len(val_recipes))):
                if cfg.get("conditioning", "class") == "none":
                    labels = torch.zeros_like(labels)
                prediction = model(batch["features"], labels)
                swapped = (model(batch["features"], 1 - labels)
                           if cfg["loss"] == "selective_v2" and cfg.get("class_weight", 1.) else None)
                loss, _ = losses(model, prediction, batch, cfg, swapped_prediction=swapped)
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite validation loss")
                val_losses.append((len(labels), float(loss)))
        mean = lambda values: sum(n * v for n, v in values) / sum(n for n, _ in values)
        score = mean(val_losses)
        scheduler.step(score)
        row = dict(epoch=epoch, train_loss=mean(train_losses), val_loss=score,
                   learning_rate=optimizer.param_groups[0]["lr"],
                   seconds=time.monotonic() - epoch_time)
        history.append(row)
        write_json(output / "history.json", history)
        print(f"seed={seed} epoch={epoch} train={row['train_loss']:.5f} val={score:.5f} sec={row['seconds']:.1f}", flush=True)
        if score < best - 1e-5:
            best, stale, best_epoch = score, 0, epoch
            checkpoint = dict(state_dict={k: v.detach().cpu() for k, v in model.state_dict().items()},
                              model_config=asdict(model.config), frontend=frontend_contract(),
                              targets=list(TARGETS), config=cfg,
                              training_manifest_sha256=sha256(output / "training_manifest.json"),
                              corpus_sha256=canonical_hash(registry),
                              scene_contract_sha256=canonical_hash(scene_contract),
                              epoch=epoch, validation_loss=score)
            torch.save(checkpoint, output / "candidate.pt.tmp")
            os.replace(output / "candidate.pt.tmp", output / "candidate.pt")
        else:
            stale += 1
        if stale >= cfg["patience"]:
            break
    summary = dict(status="TRAINED_CANDIDATE_NOT_SCIENTIFIC_GO", best_epoch=best_epoch,
                   best_validation_loss=best, epochs_run=len(history),
                   parameter_count=sum(p.numel() for p in model.parameters()),
                   receptive_frames=model.receptive_frames,
                   elapsed_seconds=time.monotonic() - start_time,
                   checkpoint_sha256=sha256(output / "candidate.pt"),
                   seed=seed, test_audio_read=False, corpus_review=registry["review_status"])
    create_json(output / "summary.json", summary)
    return summary
