"""Run *development-only* M4 V2 on the archived V1 train/validation population.

IMPORTANT: Reusing the published V1 test (even under a new folder/name) is NOT
an independent test. The command restores archived corpus hashes and V2 recipes,
then trains solely with train and selects/checks solely with val. It never calls
evaluate(). No test acoustic score is computed. This is an unreviewed pilot:
scientific_GO is always false, irrespective of achieved validation metrics.

Reference corpus comes from pinned ESC-50 and OpenSLR31; it remains subject
to listening/isolated-source review and CC-BY-NC research-only restrictions.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import torch

from m4_scientific.common import canonical_hash, create_json, read_json, sha256
from m4_scientific.corpus import load_registry, prepare
from m4_scientific.model import load_checkpoint
from m4_scientific.reproduction import restore
from m4_scientific.scenes import save_recipes
from m4_scientific.training import fit
from m4_scientific.validation import validate_candidates

from compare_m4_validation_only import compare

REPO_LAB = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_LAB.parents[1] / "05_evidence/m4_sci_real_2026-10-27"
ORIGINAL_SELECTED = REPO_LAB / "models/m4_sci_real_candidate_v1/selected/candidate.pt"
V2_CONFIG = REPO_LAB / "configs/m4_sci_v2_selective.json"
SEEDS = (71, 72, 73)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO_LAB / "data/m4_sci_v2_pilot"))
    ap.add_argument("--output", default=str(REPO_LAB / "runs/m4-v2-pilot"))
    ap.add_argument("--epochs", type=int, default=30)
    args = ap.parse_args()
    if args.epochs < 1 or args.epochs > 30:
        raise ValueError("Pilot epochs must be in [1,30]")
    root, out = Path(args.root).resolve(), Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start_utc = datetime.now(timezone.utc).isoformat()
    expected_v2 = read_json(EVIDENCE / "v2/registry.json")
    expected_contract = read_json(EVIDENCE / "v2/scene_contract.json")
    if expected_v2["review_status"] == "APPROVED":
        raise ValueError("This workflow must not silently claim reviewed audio")
    baseline_model, baseline_obj = load_checkpoint(ORIGINAL_SELECTED)
    if baseline_obj["corpus_sha256"] != canonical_hash(expected_v2):
        raise ValueError("Archived registry and baseline model disagree")
    if baseline_obj["scene_contract_sha256"] != canonical_hash(expected_contract):
        raise ValueError("Archived V2 recipe contract and baseline model disagree")
    del baseline_model

    create_json(out / "intent.json", dict(
        schema="m4-v2-pilot-intent-v1", started_utc=start_utc,
        permitted_splits=["train","val"], forbidden=["training_on_test","model_selection_on_test",
                                                      "scientific_GO","streaming_claim"],
        baseline_checkpoint_sha256=sha256(ORIGINAL_SELECTED),
        historical_test_already_exposed=True, original_test_not_reused_for_scoring=True,
        human_audio_review="PENDING", pilot_unreviewed=True,
        seeds=list(SEEDS), epochs=args.epochs))

    print("[m4-v2] Acquire pinned real recordings and speech, NO model selection from test", flush=True)
    prepare(root)
    reg = load_registry(root, allow_unreviewed=True, splits=("train", "val"))
    save_recipes(root, reg, counts=(1600, 160, 160), seconds=2.,
                 seed=2710, condition_version="full-factorial-v2")
    # The V1 WAV headers had timestamps; reconstruct byte-exact frozen headers
    # and restore archived V2 recipes to enable a valid *paired validation*.
    restored = restore(root, EVIDENCE / "v2/registry.json", EVIDENCE / "pcm_containers.json")
    if restored["status"] != "PASS_BYTE_EXACT_RESTORATION" or restored["files"] != 352:
        raise ValueError("Unexpected corpus restore status/count")
    reg = load_registry(root, allow_unreviewed=True, splits=("train","val"))
    if canonical_hash(reg) != baseline_obj["corpus_sha256"]:
        raise ValueError("Restored corpus is not paired with V1")
    if canonical_hash(read_json(root / "scene_contract.json")) != baseline_obj["scene_contract_sha256"]:
        raise ValueError("Restored scene contract is not paired with V1")
    print("[m4-v2] Corpus verified against V1; archive's TEST is EXPOSED, never selected", flush=True)

    cfg = read_json(V2_CONFIG)
    checkpoints = [ORIGINAL_SELECTED]
    summaries = []
    for seed in SEEDS:
        # Freeze a separate config and an immutable output directory per run.
        candidate = dict(cfg, seed=seed, epochs=args.epochs)
        label = f"seed{seed}"
        result = fit(root, out / label, candidate, pilot_unreviewed=True)
        checkpoints.append(out / label / "candidate.pt")
        summaries.append(dict(run=label, **result))
    validation = validate_candidates(root, checkpoints, out / "validation",
                                     candidate_runs=[f"seed{s}" for s in SEEDS])
    pairings = {}
    for seed in SEEDS:
        name = f"seed{seed}"
        pairings[name] = compare(out / "validation", "selected", name)
    winner = validation["best_run"]
    winner_comparison = pairings[winner]
    report = dict(schema="m4-v2-real-audio-pilot-v1", finished_utc=datetime.now(timezone.utc).isoformat(),
                  status="TRAIN_VAL_PILOT_COMPLETE_NOT_INDEPENDENT_TEST",
                  scientific_GO=False, streaming_GO=False, test_used_for_training_or_selection=False,
                  historical_V1_test_already_exposed=True,
                  corpus="ESC-50 fixed revision + Mini LibriSpeech train-clean-5, archives rebuilt",
                  source_audio_review_status=reg["review_status"],
                  license_scope="academic research; ESC-50 CC BY-NC; public audio not re-distributed",
                  corpus_sha256=canonical_hash(reg),
                  v2_scene_contract_sha256=canonical_hash(read_json(root / "scene_contract.json")),
                  archived_container_restoration=restored["status"],
                  baseline=ORIGINAL_SELECTED.name,
                  baseline_run="selected",
                  seeds=list(SEEDS), training=summaries, validation_winner=winner,
                  validation_selection_rule=validation["selection"],
                  validation_candidates=validation["summaries"],
                  paired_comparisons=pairings, selected_pairing=winner_comparison,
                  remaining=["Human inspection of each pseudo-stem",
                             "Perceptual near-duplicate audit",
                             "Independent unseen field-domain sources for a NEW test",
                             "M2 false-alert corrections and integrated evaluation",
                             "Academic approval; no clinical or streaming inference"])
    create_json(out / "pilot_result.json", report)
    print(json.dumps({k:report[k] for k in ("status","scientific_GO","validation_winner",
                "selected_pairing","remaining")}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
