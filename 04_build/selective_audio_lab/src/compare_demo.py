"""Paired engineering comparison; never a replacement for the scientific test."""
from __future__ import annotations

import json
from pathlib import Path

from run_demo import run_demo, sha256
from validate_artifacts import validate_run, EvidenceValidationError


def run_comparison(output_root, comparison_id, *, model_root=None, **params):
    root = Path(output_root)
    rows = {}
    for engine, suffix in (("oracle", "ORACLE"), ("cnn_experimental", "CNN")):
        run_id = f"{comparison_id}-{suffix}"
        summary = run_demo(root / run_id, run_id=run_id, engine=engine,
                           model_root=model_root, **params)
        validate_run(root / run_id, run_id)
        rows[engine] = {"run_id": run_id, "metrics": summary["metrics"],
                        "executed_engine": summary["config"]["executed_engine"],
                        "model": summary["config"]["model"],
                        "mixture_sha256": sha256(root / run_id / "mixture.wav")}
    if rows["oracle"]["mixture_sha256"] != rows["cnn_experimental"]["mixture_sha256"]:
        raise ValueError("Comparison rejected: different input mixtures")
    result = {"comparison_id": comparison_id, "same_scene_verified": True,
              "scope": "paired_synthetic_engineering_demo_not_scientific_test",
              "runs": rows}
    out = root / comparison_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def validate_comparison(root, comparison_id):
    root = Path(root)
    pair = json.loads((root / comparison_id / "comparison.json").read_text())
    for engine, suffix in (("oracle", "ORACLE"), ("cnn_experimental", "CNN")):
        row = pair["runs"][engine]
        run_id = f"{comparison_id}-{suffix}"
        if row["run_id"] != run_id:
            raise EvidenceValidationError("Comparison run identity mismatch")
        validate_run(root / run_id, run_id)
        summary = json.loads((root / run_id / "demo_summary.json").read_text())
        if summary["metrics"] != row["metrics"] or summary["config"]["requested_engine"] != engine:
            raise EvidenceValidationError("Comparison metrics/engine mismatch")
        if row["model"] != summary["config"]["model"] or row["executed_engine"] != summary["config"]["executed_engine"]:
            raise EvidenceValidationError("Comparison model/execution mismatch")
        if sha256(root / run_id / "mixture.wav") != row["mixture_sha256"]:
            raise EvidenceValidationError("Comparison input hash mismatch")
    if pair["runs"]["oracle"]["mixture_sha256"] != pair["runs"]["cnn_experimental"]["mixture_sha256"]:
        raise EvidenceValidationError("Comparison scene mismatch")
    return {"validated": True, "comparison_id": comparison_id, "same_scene_verified": True}
