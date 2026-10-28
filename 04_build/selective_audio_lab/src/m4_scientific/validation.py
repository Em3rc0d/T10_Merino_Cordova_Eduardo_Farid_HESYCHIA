"""Common acoustic validation across loss functions; never compare unlike loss scales."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import torch

from .common import canonical_hash, sha256, write_json
from .corpus import load_registry
from .evaluation import _row, group_ci
from .model import features, load_checkpoint, spectrum
from .scenes import build_scene, load_recipes


def validate_candidates(root, checkpoints, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    reg = load_registry(root, allow_unreviewed=True, splits=("val",))
    recipes = load_recipes(root, "val")
    torch.set_num_threads(3)
    all_rows, summaries = [], []
    for path in checkpoints:
        path = Path(path)
        model, obj = load_checkpoint(path)
        if obj["corpus_sha256"] != canonical_hash(reg):
            raise ValueError("Validation corpus differs from training")
        rows = []
        for recipe in recipes:
            mix, stems = build_scene(root, reg, recipe)
            with torch.no_grad():
                spec = spectrum(torch.from_numpy(mix))[0]
                label = 0 if obj["config"].get("conditioning") == "none" else recipe["target_id"]
                gain = torch.ones_like(spec.real) if recipe["alert_present"] else model.gain(
                    model(features(spec)[None], torch.tensor([label])))[0]
            row, _ = _row(path.parent.name, obj["config"]["seed"], recipe, mix, stems, spec, gain,
                          mode="validation_assisted")
            rows.append(row)
        active = [r for r in rows if r["decision"] == "ALLOW"]
        eligible = [r for r in rows if r["both_ok"] is not None]
        at = [r["A_target_db"] for r in active if r["A_target_db"] is not None]
        ap = [r["A_protected_db"] for r in active if r["A_protected_db"] is not None]
        score = dict(run=path.parent.name, checkpoint=str(path.resolve()),
                     checkpoint_sha256=sha256(path), seed=obj["config"]["seed"],
                     configuration=obj["config"], joint_pass=sum(r["both_ok"] for r in eligible),
                     joint_eligible=len(eligible),
                     joint_pass_rate=float(np.mean([r["both_ok"] for r in eligible])),
                     mean_A_target_db=float(np.mean(at)), mean_A_protected_db=float(np.mean(ap)),
                     A_target_db=group_ci(active, "A_target_db", "target_group"),
                     A_protected_db=group_ci(active, "A_protected_db", "speaker_group"),
                     STOI_delta=group_ci(active, "STOI_delta", "speaker_group"))
        summaries.append(score)
        all_rows.extend(rows)
        print(f"validation {path.parent.name}: joint={score['joint_pass']}/{len(eligible)} "
              f"A_target={score['mean_A_target_db']:.2f} voice_loss={score['mean_A_protected_db']:.2f}", flush=True)
    # Predeclared selection ordering. Never compare MSE loss with composite loss numerically.
    ranked = sorted(summaries, key=lambda r: (r["joint_pass_rate"],
                    -max(0., r["mean_A_protected_db"] - 1.), r["mean_A_target_db"]), reverse=True)
    report = dict(split="validation_only", test_audio_read=False,
                  selection="highest joint success fraction; ties prefer smaller violation "
                            "of protected<=1 dB, then higher target attenuation",
                  best_checkpoint=ranked[0]["checkpoint"], best_run=ranked[0]["run"],
                  summaries=summaries, scientific_GO=False)
    write_json(output / "validation_report.json", report)
    with (output / "per_scene.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    return report
