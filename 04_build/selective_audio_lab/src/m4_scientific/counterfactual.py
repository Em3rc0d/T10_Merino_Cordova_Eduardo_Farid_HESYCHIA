"""Counterfactual class-selectivity on *validation only*, same mixture and sources.

For each eligible VAL recipe with BOTH target sound classes present, apply M4
twice to identical mixture STFT: intended label and swapped label. Score
waveform-reconstructed attenuation on true target and other target stem.

This diagnoses whether the neural estimator follows its requested class,
NOT whether either mask reaches the 6 dB / 1 dB scientific thresholds, nor a
final/test/clinical result. Sources are used only for evaluating each mask,
never as inputs to either forward pass. Never load recipes_test.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from m4_scientific.common import canonical_hash, sha256, write_json
from m4_scientific.corpus import TARGETS, load_registry
from m4_scientific.evaluation import attenuation, group_ci
from m4_scientific.model import features, load_checkpoint, spectrum, synthesize
from m4_scientific.scenes import build_scene, load_recipes


def summarize_counterfactual(rows):
    if not rows:
        raise ValueError("No informative both-target validation scenes")
    for row in rows:
        if row["correct_target_db"] is None or row["swapped_target_db"] is None:
            raise ValueError("Counterfactual target stem must be present")
        if row["correct_other_db"] is None or row["swapped_other_db"] is None:
            raise ValueError("Counterfactual other stem must be present")
    source_groups = defaultdict(list)
    for row in rows:
        source_groups[row["target_group"]].append(row)
    group_means = {k: {name: float(np.mean([float(r[name]) for r in v]))
                      for name in ("target_contrast_db", "other_contrast_db")}
                   for k, v in source_groups.items()}
    target_contrast = [r["target_contrast_db"] for r in rows]
    other_contrast = [r["other_contrast_db"] for r in rows]
    return {
        "scene_count":len(rows), "source_group_count":len(source_groups),
        "target_contrast_db_equal_group_mean":float(np.mean([v["target_contrast_db"] for v in group_means.values()])),
        "other_contrast_db_equal_group_mean":float(np.mean([v["other_contrast_db"] for v in group_means.values()])),
        "target_contrast_ci95_group_bootstrap":group_ci(rows,"target_contrast_db","target_group"),
        "other_contrast_ci95_group_bootstrap":group_ci(rows,"other_contrast_db","target_group"),
        "target_contrast_positive_scenes":sum(x>0 for x in target_contrast),
        "other_contrast_positive_scenes":sum(x>0 for x in other_contrast),
        "both_contrasts_positive_scenes":sum(a>0 and b>0 for a,b in zip(target_contrast, other_contrast)),
        "mean_mask_l1_difference":float(np.mean([r["mask_l1_difference"] for r in rows])),
        "interpretation":"Positive target_contrast means correct class suppresses intended target more than swapped; positive other_contrast means the swapped class suppresses the other class more than correct. Source stems used for metrics ONLY.",
    }


def evaluate_class_contrast(root, checkpoint, output):
    root, checkpoint, output = Path(root), Path(checkpoint), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    registry = load_registry(root, allow_unreviewed=True, splits=("val",))
    recipes = load_recipes(root, "val")
    model, metadata = load_checkpoint(checkpoint)
    if metadata["corpus_sha256"] != canonical_hash(registry):
        raise ValueError("Counterfactual checkpoint uses different corpus")
    if metadata["scene_contract_sha256"] != canonical_hash(json.loads(
        (root / "scene_contract.json").read_text(encoding="utf-8"))):
        raise ValueError("Counterfactual checkpoint uses different scene contract")
    if metadata["config"].get("conditioning", "class") != "class":
        raise ValueError("Cannot evaluate counterfactual of unconditioned model")
    torch.set_num_threads(2)
    rows=[]
    for recipe in recipes:
        # Protected alerts are blocked before inference. Both source classes
        # must exist so correct and swapped have physically measurable targets.
        if recipe["alert_present"] or not recipe["target_present"] or TARGETS[1-recipe["target_id"]] not in recipe["parts"]:
            continue
        mixture, stems = build_scene(root, registry, recipe)
        target = stems[TARGETS[recipe["target_id"]]]
        other = stems[TARGETS[1-recipe["target_id"]]]
        with torch.no_grad():
            spec = spectrum(torch.from_numpy(mixture))[0]
            f = features(spec)[None]
            correct = model.gain(model(f,torch.tensor([recipe["target_id"]])))[0]
            swapped = model.gain(model(f,torch.tensor([1-recipe["target_id"]])))[0]
            two_stems = spectrum(torch.from_numpy(np.stack([target,other])))
            correct_recon = synthesize(two_stems*correct[None],len(mixture)).numpy()
            swapped_recon = synthesize(two_stems*swapped[None],len(mixture)).numpy()
        ctarget, cother = attenuation(target,correct_recon[0]), attenuation(other,correct_recon[1])
        starget, sother = attenuation(target,swapped_recon[0]), attenuation(other,swapped_recon[1])
        if any(v is None for v in (ctarget,cother,starget,sother)):
            raise ValueError("Silent stem in eligible counterfactual "+recipe["scene_id"])
        rows.append(dict(
            scene_id=recipe["scene_id"],requested_class=TARGETS[recipe["target_id"]],
            target_group=recipe["parts"][TARGETS[recipe["target_id"]]]["source_group"],
            other_group=recipe["parts"][TARGETS[1-recipe["target_id"]]]["source_group"],
            mixture_sha256=hashlib.sha256(mixture.astype("<f4").tobytes()).hexdigest(),
            correct_target_db=ctarget, swapped_target_db=starget,
            correct_other_db=cother, swapped_other_db=sother,
            target_contrast_db=ctarget-starget,other_contrast_db=sother-cother,
            mask_l1_difference=float((correct-swapped).abs().mean())))
    report=dict(schema="m4-v3-class-counterfactual-validation-v1",
                split="validation_only",scientific_GO=False,independent_test=False,
                predictor_inputs="mixture STFT plus requested class, no stems at inference",
                checkpoint_sha256=sha256(checkpoint),corpus_sha256=canonical_hash(registry),
                summary=summarize_counterfactual(rows),
                class_labels=[*TARGETS],
                source_review="PENDING_HUMAN_ISOLATION_REVIEW",
                note="Only same-mixture positive-pair VAL scenes, no test access; group bootstrap descriptive, small clusters")
    write_json(output/"counterfactual_report.json",report)
    with (output/"counterfactual_per_scene.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    print(f"[counterfactual {checkpoint.parent.name}] eligible={len(rows)} groups={report['summary']['source_group_count']} "
          f"target_contrast={report['summary']['target_contrast_db_equal_group_mean']:.3f} "
          f"other_contrast={report['summary']['other_contrast_db_equal_group_mean']:.3f} "
          f"both_positive={report['summary']['both_contrasts_positive_scenes']}/{len(rows)}",flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True)
    parser.add_argument("--checkpoint",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    evaluate_class_contrast(args.root,args.checkpoint,args.out)


if __name__=="__main__":
    main()
