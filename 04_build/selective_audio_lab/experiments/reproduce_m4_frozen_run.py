"""Reproduce the published frozen evaluation without training or model selection.

This is a replication of an ALREADY EXPOSED test, never a fresh held-out result.
The first run's temporary result files were lost when the execution environment
was replaced. Published checkpoints, recipes and evaluator remain immutable.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
from m4_scientific.common import create_json, read_json, sha256
from m4_scientific.corpus import prepare
from m4_scientific.reproduction import restore
from m4_scientific.evaluation import evaluate, evaluator_hash, runtime_versions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--tag", default="", help="Unique safe name for an additional replication")
    args = parser.parse_args()
    if args.tag and not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("--tag may contain only letters, digits, underscores and hyphens")
    suffix = "_" + args.tag if args.tag else ""
    args.root = args.root or LAB / ("data/m4_sci_replication" + suffix)
    args.out = args.out or LAB / ("outputs/m4_sci_replication" + suffix) / "test"
    evidence = LAB.parents[1] / "05_evidence/m4_sci_real_2026-10-27"
    replica_freeze = evidence / ("freeze_replication" + suffix + ".json")
    saved = evidence / ("test_replication" + suffix)
    receipt_path = evidence / ("replication_receipt" + suffix + ".json")
    if any(p.exists() for p in (replica_freeze, saved, receipt_path, args.out)):
        raise ValueError("Replication artifacts already exist; use a unique --tag, never overwrite them")
    original = evidence / "freeze_test.json"
    frozen = read_json(original)
    if frozen["evaluation_code_sha256"] != evaluator_hash() or frozen["runtime_versions"] != runtime_versions():
        raise ValueError("Published evaluator and runtime versions must match before replication")
    started = datetime.now(timezone.utc).isoformat()
    if (args.root / "registry.json").exists():
        raise ValueError("Use a fresh corpus directory; existing raw downloads may be reused")
    prepare(args.root)
    restoration = restore(args.root, evidence / "v2/registry.json", evidence / "pcm_containers.json")
    with replica_freeze.open("xb") as dest:
        dest.write(original.read_bytes())
    report = evaluate(args.root, replica_freeze, args.out)
    saved.mkdir(exist_ok=False)
    for path in args.out.iterdir():
        if path.is_file():
            shutil.copyfile(path, saved / path.name)
    receipt = dict(
        schema="m4-frozen-test-replication-v1", started_at_utc=started,
        completed_at_utc=datetime.now(timezone.utc).isoformat(),
        original_freeze_commit="0a47015426617cebbc2ce8ee24af0c77f9267745",
        freeze_sha256=sha256(original), replica_freeze_sha256=sha256(replica_freeze),
        evaluator_sha256=evaluator_hash(), runtime_versions=runtime_versions(),
        original_test_already_exposed=True, fresh_heldout_test=False,
        training_or_tuning_performed=False, model_selection_repeated=False,
        reason="Temporary first-run result files unavailable after execution environment replacement",
        original_raw_results_recovered=False,
        corpus_restoration=restoration,
        artifacts={p.name: sha256(p) for p in saved.iterdir() if p.is_file()},
        scientific_GO=report["scientific_GO"], status=report["status"])
    create_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
