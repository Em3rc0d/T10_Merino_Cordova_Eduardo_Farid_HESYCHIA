"""M4 V3 exploratory spectral CNN on restored real recordings; TRAIN+VAL ONLY.

This is an architecture ablation, not a GO and not a parameter-matched
causal-temporal comparison. Sources are 352 archived ESC-50/SLR31 recordings
with human review still pending. Old test is exposed and NEVER opened for
training, validation selection, counterfactual or scientific confirmation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

LAB=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(LAB/"src"))

from m4_scientific.common import canonical_hash, create_json, read_json, sha256
from m4_scientific.corpus import prepare, load_registry
from m4_scientific.reproduction import restore
from m4_scientific.scenes import save_recipes
from m4_scientific.model import load_checkpoint
from m4_scientific.training import fit
from m4_scientific.validation import validate_candidates
from m4_scientific.counterfactual import evaluate_class_contrast
from compare_m4_validation_only import compare

EVIDENCE=LAB.parents[1]/"05_evidence/m4_sci_real_2026-10-27"
V1=LAB/"models/m4_sci_real_candidate_v1/selected/candidate.pt"
CONFIG=LAB/"configs/m4_sci_v3_spectral_pilot.json"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default=str(LAB/"data/m4_v3_spectral_pilot"))
    parser.add_argument("--out",default=str(LAB/"runs/m4-v3-spectral-pilot"))
    args=parser.parse_args()
    root,out=Path(args.root).resolve(),Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    baseline,checkpoint=load_checkpoint(V1)
    del baseline
    archived_registry=read_json(EVIDENCE/"v2/registry.json")
    archived_scene=read_json(EVIDENCE/"v2/scene_contract.json")
    if checkpoint["corpus_sha256"] != canonical_hash(archived_registry) or checkpoint["scene_contract_sha256"] != canonical_hash(archived_scene):
        raise ValueError("V1 checkpoint does not match archive")
    cfg=read_json(CONFIG)
    if cfg["architecture"] != "spectral" or cfg["loss"] != "selective_v2":
        raise ValueError("Exploratory pilot must use spectral CNN and V2 objective")
    create_json(out/"intent.json",dict(schema="m4-spectral-exploration-v1",
          started_utc=datetime.now(timezone.utc).isoformat(),
          scientific_GO=False,architecture_ablation_not_parameter_matched=True,
          splits_used=["train","val"], old_test_status="EXPOSED_AND_NOT_ACCESSED",
          baseline=sha256(V1),seed=cfg["seed"],planned_epochs=cfg["epochs"],
          human_isolation_review="PENDING",analysis_purpose="representational selectivity not clinical"))
    print("[M4 V3] Acquire 352 pinned real audio sources and restore exact hashes",flush=True)
    prepare(root)
    registry=load_registry(root,allow_unreviewed=True,splits=("train","val"))
    save_recipes(root,registry,counts=(1600,160,160),seconds=2.,seed=2710,
                 condition_version="full-factorial-v2")
    restored=restore(root,EVIDENCE/"v2/registry.json",EVIDENCE/"pcm_containers.json")
    if restored["status"] != "PASS_BYTE_EXACT_RESTORATION" or restored["files"] != 352:
        raise ValueError("Failed exact corpus restoration")
    registry=load_registry(root,allow_unreviewed=True,splits=("train","val"))
    if canonical_hash(registry) != checkpoint["corpus_sha256"]:
        raise ValueError("Restored V1 corpus mismatch")
    if canonical_hash(read_json(root/"scene_contract.json")) != checkpoint["scene_contract_sha256"]:
        raise ValueError("Restored V1 scene contract mismatch")
    print("[M4 V3] Exact corpus verified; training spectral CNN with backprop",flush=True)
    trained=fit(root,out/"spectral_seed81",cfg,pilot_unreviewed=True)
    validation=validate_candidates(root,[V1,out/"spectral_seed81"/"candidate.pt"],
                                   out/"validation",candidate_runs=["spectral_seed81"])
    paired=compare(out/"validation","selected","spectral_seed81")
    contrast_old=evaluate_class_contrast(root,V1,out/"counterfactual_v1")
    contrast_new=evaluate_class_contrast(root,out/"spectral_seed81"/"candidate.pt",
                                        out/"counterfactual_spectral")
    result=dict(schema="m4-v3-real-audio-causal-spectral-pilot-v1",
        status="TRAIN_VAL_SPECTRAL_EXPLORATION_COMPLETE",
        scientific_GO=False,streaming_GO=False,
        selected_for_test=False,independent_test=False,human_review="PENDING",
        source_groups_not_independent_scenes=True,
        archived_test_exposed_and_excluded=True,
        real_sources=352,
        corpus_sha256=canonical_hash(registry),
        scene_contract_sha256=canonical_hash(read_json(root/"scene_contract.json")),
        restored_status=restored["status"],
        training=trained,architecture="spectral",
        architecture_ablation_not_parameter_matched=True,
        baseline_v1=next(r for r in validation["summaries"] if r["run"]=="selected"),
        spectral_candidate=next(r for r in validation["summaries"] if r["run"]=="spectral_seed81"),
        paired_validation=paired,
        counterfactual_v1=contrast_old["summary"],
        counterfactual_spectral=contrast_new["summary"],
        remaining_gates=["Human listening/source isolation review",
                         "New genuinely independent sources for sealed test",
                         "Other-class / absence / alert checks and end-to-end M2 validation",
                         "More training seeds if architecture shows promise",
                         "Academic evaluation of scope; no streaming or clinical claims"])
    create_json(out/"pilot_result.json",result)
    print(json.dumps({k:result[k] for k in (
        "status","scientific_GO","spectral_candidate","paired_validation",
        "counterfactual_v1","counterfactual_spectral")},ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()
