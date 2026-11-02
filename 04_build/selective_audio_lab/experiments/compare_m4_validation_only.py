"""Paired V1-vs-V2 comparison on VALIDATION. NEVER read held-out test artefacts.

Usage:
  python experiments/compare_m4_validation_only.py \
    --validation runs/validation-v2 --baseline selected --candidate v2-seed71 \
    --out runs/validation-v2/comparison.json

First create runs/validation-v2 with:
  python src/m4_science.py validate --root data/m4_sci_v2 \
    --checkpoints path/to/V1/selected/candidate.pt runs/v2-seed71/candidate.pt \
    --out runs/validation-v2

V2 and V1 must use the SAME corpus registry, splits, frontend, labels and
mixture hashes. This compares the engineering hypothesis, not scientific GO.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def parsed_float(row, key):
    value = row.get(key, "")
    return None if value in ("", "None", "null") else float(value)


def parsed_bool(row, key):
    value = str(row.get(key, ""))
    if value in ("True", "true", "1"):
        return True
    if value in ("False", "false", "0"):
        return False
    if value in ("None", "null", ""):
        return None
    raise ValueError("Unexpected Boolean serialization for " + key + ": " + value)


def compare(report_path, baseline, candidate):
    folder = Path(report_path)
    report = json.loads((folder / "validation_report.json").read_text())
    if report.get("split") != "validation_only" or report.get("test_audio_read") is not False:
        raise ValueError("Not a validation-only report. Refusing comparison.")
    if baseline == candidate:
        raise ValueError("Distinct baseline and candidate required")
    candidates = {x["run"]: x for x in report["summaries"]}
    if baseline not in candidates or candidate not in candidates:
        raise ValueError("Missing run from validation report")
    rows = defaultdict(dict)
    with (folder / "per_scene.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            method = r["method"]
            if method not in (baseline, candidate):
                continue
            scene = r["scene_id"]
            if scene in rows[method]:
                raise ValueError(f"Duplicate {method}/{scene}")
            rows[method][scene] = r
    a, b = rows[baseline], rows[candidate]
    if not a or a.keys() != b.keys():
        raise ValueError("Not the same validation scenes")
    pairs = []
    for scene in sorted(a):
        before, after = a[scene], b[scene]
        for name in ("mixture_pcm_sha256", "target_class", "target_present",
                     "speech_present", "alert_present", "target_group", "speaker_group"):
            if before[name] != after[name]:
                raise ValueError(f"Unpaired source or condition: {scene}/{name}")
        if parsed_bool(before, "both_ok") is None:
            continue
        if parsed_bool(after, "both_ok") is None:
            raise ValueError(f"Eligible population mismatch: {scene}")
        x0, x1 = parsed_float(before, "A_target_db"), parsed_float(after, "A_target_db")
        y0, y1 = parsed_float(before, "A_protected_db"), parsed_float(after, "A_protected_db")
        if None in (x0, x1, y0, y1):
            raise ValueError("Missing acoustic metric in eligible scene: " + scene)
        pairs.append(dict(scene=scene, target_group=before["target_group"],
                          speaker_group=before["speaker_group"], target_delta_db=x1-x0,
                          protected_delta_db=y1-y0, baseline_joint=parsed_bool(before,"both_ok"),
                          candidate_joint=parsed_bool(after,"both_ok")))
    if not pairs:
        raise ValueError("No eligible target+speech validation pairs")
    def by_group(key, measure):
        grouped = defaultdict(list)
        for p in pairs:
            grouped[p[key]].append(p[measure])
        return dict(groups=len(grouped), mean_equal_group=float(mean(mean(v) for v in grouped.values())))
    return dict(schema="m4-v2-validation-paired-v1", split="validation_only",
                scientific_GO=False, test_used=False,
                baseline=baseline, candidate=candidate, eligible_pairs=len(pairs),
                baseline_joint_pass=sum(p["baseline_joint"] for p in pairs),
                candidate_joint_pass=sum(p["candidate_joint"] for p in pairs),
                target_delta_db=by_group("target_group", "target_delta_db"),
                protected_delta_db=by_group("speaker_group", "protected_delta_db"),
                interpretation="Positive target delta and nonpositive voice delta desirable; "
                               "independent external test still required.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    opts = parser.parse_args()
    result = compare(opts.validation, opts.baseline, opts.candidate)
    path = Path(opts.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
