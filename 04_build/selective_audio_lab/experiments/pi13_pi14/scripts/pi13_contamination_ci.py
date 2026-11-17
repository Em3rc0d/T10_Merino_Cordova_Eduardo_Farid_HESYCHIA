#!/usr/bin/env python3
"""Estimate non-isolated/contaminated proportion with a Wilson 95% CI.

Input must represent the final review state used for corpus exclusions. The
script does not adjudicate disagreements and does not infer human decisions.
A record is considered non-isolated when purity_judgement != "isolated" or
review_decision != "eligible".
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

VALID_PURITY = {"isolated", "minor_contamination", "mixed", "undetermined"}
VALID_DECISIONS = {"eligible", "restricted", "reject"}


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n <= 0:
        raise ValueError("n must be >0")
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / den
    return max(0.0, center - half), min(1.0, center + half)


def summarize(path: Path, expected_n: int | None = None):
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        required = {"asset_id", "purity_judgement", "review_decision"}
        if not r.fieldnames or not required.issubset(r.fieldnames):
            raise ValueError("CSV requires asset_id,purity_judgement,review_decision")
        rows = list(r)
    if not rows:
        raise ValueError("empty review CSV")
    if expected_n is not None and len(rows) != expected_n:
        raise ValueError(f"expected {expected_n} rows, got {len(rows)}")
    ids = [x["asset_id"].strip() for x in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("asset_id empty or duplicated")

    contaminated = []
    purity_counts = Counter()
    decision_counts = Counter()
    for row in rows:
        purity = row["purity_judgement"].strip().lower()
        decision = row["review_decision"].strip().lower()
        if purity not in VALID_PURITY:
            raise ValueError(f"invalid purity_judgement for {row['asset_id']}: {purity}")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid review_decision for {row['asset_id']}: {decision}")
        purity_counts[purity] += 1
        decision_counts[decision] += 1
        contaminated.append(purity != "isolated" or decision != "eligible")

    k = int(sum(contaminated))
    n = len(rows)
    lo, hi = wilson(k, n)
    return {
        "schema": "hesychia.pi15-contamination.v1",
        "definition": "non_isolated := purity_judgement != isolated OR review_decision != eligible",
        "n": n,
        "non_isolated": k,
        "isolated_eligible": n - k,
        "proportion": k / n,
        "ci95_method": "Wilson score",
        "ci95": [lo, hi],
        "purity_counts": dict(purity_counts),
        "decision_counts": dict(decision_counts),
        "note": "This report summarizes supplied final human decisions; it does not perform or replace listening/adjudication.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reviewed-csv", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-n", type=int)
    a = p.parse_args()
    result = summarize(a.reviewed_csv, a.expected_n)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": result["n"], "non_isolated": result["non_isolated"], "proportion": result["proportion"], "ci95": result["ci95"]}))


if __name__ == "__main__":
    main()
