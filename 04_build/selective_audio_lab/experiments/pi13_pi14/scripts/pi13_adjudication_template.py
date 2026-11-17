#!/usr/bin/env python3
"""Build a separate adjudication template from two human review CSVs.

Original reviewer files are never modified. Only disagreements in decision or
purity are emitted for later human adjudication.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

OUT_FIELDS = [
    "asset_id",
    "reviewer_a_id", "reviewer_a_decision", "reviewer_a_purity",
    "reviewer_b_id", "reviewer_b_decision", "reviewer_b_purity",
    "adjudicated_decision", "adjudicated_purity",
    "adjudicator_id", "adjudication_date_utc", "adjudication_notes",
]


def load(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        required = {"asset_id", "reviewer_id", "review_decision", "purity_judgement"}
        if not r.fieldnames or not required.issubset(r.fieldnames):
            raise ValueError(f"{path} missing review columns")
        rows = list(r)
    by = {}
    reviewers = set()
    for row in rows:
        aid = row["asset_id"].strip()
        rid = row["reviewer_id"].strip()
        if not aid or not rid or aid in by:
            raise ValueError(f"invalid/duplicate review row in {path}: {aid}")
        by[aid] = row
        reviewers.add(rid)
    if len(reviewers) != 1:
        raise ValueError(f"{path} must contain exactly one reviewer_id")
    return by, next(iter(reviewers))


def build(first: Path, second: Path, out: Path):
    a, ra = load(first)
    b, rb = load(second)
    if ra == rb:
        raise ValueError("reviewers must be distinct")
    common = sorted(set(a) & set(b))
    if not common:
        raise ValueError("no common assets")
    disagreements = []
    for aid in common:
        x, y = a[aid], b[aid]
        if (
            x["review_decision"].strip().lower() != y["review_decision"].strip().lower()
            or x["purity_judgement"].strip().lower() != y["purity_judgement"].strip().lower()
        ):
            disagreements.append({
                "asset_id": aid,
                "reviewer_a_id": ra,
                "reviewer_a_decision": x["review_decision"],
                "reviewer_a_purity": x["purity_judgement"],
                "reviewer_b_id": rb,
                "reviewer_b_decision": y["review_decision"],
                "reviewer_b_purity": y["purity_judgement"],
                "adjudicated_decision": "",
                "adjudicated_purity": "",
                "adjudicator_id": "",
                "adjudication_date_utc": "",
                "adjudication_notes": "",
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(disagreements)
    return {"paired_assets": len(common), "disagreements": len(disagreements), "reviewers": [ra, rb]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--first", type=Path, required=True)
    p.add_argument("--second", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.first, a.second, a.out), ensure_ascii=False))


if __name__ == "__main__":
    main()
