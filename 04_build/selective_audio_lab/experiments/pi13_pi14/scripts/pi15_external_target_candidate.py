#!/usr/bin/env python3
"""Prepare a metadata-only external target cohort candidate for HESYCHIA PI15.

No audio bytes are downloaded or decoded. Candidate clips are drawn from the
FSD50K collection annotations (raw human annotations retained for small classes)
and cross-referenced with the released FSD50K ground-truth partitions and
per-clip metadata.

The selector excludes every Freesound ID already present in HESYCHIA V1,
requires distinct uploader groups across the complete candidate set, and selects
10 Chainsaw + 10 Vacuum_cleaner groups. The result is NOT a frozen test: every
selected clip still requires acquisition, hashing and human listening after OE1.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from collections import Counter
from pathlib import Path

TARGETS = ("Chainsaw", "Vacuum_cleaner")
SEED = 20261117
BASE = "https://huggingface.co/datasets/Fhrozen/FSD50k/resolve/main"

URLS = {
    "eval_ground_truth": f"{BASE}/labels/eval.csv",
    "eval_collection": f"{BASE}/metadata/collection/collection_eval.csv",
    "eval_metadata": f"{BASE}/metadata/eval_clips_info_FSD50K.json",
    "dev_ground_truth": f"{BASE}/labels/dev.csv",
    "dev_collection": f"{BASE}/metadata/collection/collection_dev.csv",
    "dev_metadata": f"{BASE}/metadata/dev_clips_info_FSD50K.json",
}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-thesis-metadata/1"})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()
    if not data:
        raise ValueError(f"empty upstream file: {url}")
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def csv_rows(raw: bytes):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def split_labels(value: str):
    return tuple(x.strip() for x in (value or "").split(",") if x.strip())


def normalize_fid(value) -> str:
    raw = str(value or "").strip()
    if raw.lower().endswith(".wav"):
        raw = raw[:-4]
    return raw


def v1_freesound_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = set()
    for row in rows:
        group = (row.get("source_group") or "").strip()
        if group.startswith("freesound:"):
            ids.add(group.split(":", 1)[1])
    if not ids:
        raise ValueError("V1 manifest yielded no Freesound denylist")
    return ids


def metadata_fields(meta: dict):
    uploader = str(meta.get("uploader") or meta.get("username") or "").strip()
    license_value = str(meta.get("license") or meta.get("licence") or "").strip()
    title = str(meta.get("title") or "").strip()
    return uploader, license_value, title


def build_partition(name: str, gt_rows, collection_rows, metadata):
    gt = {normalize_fid(r["fname"]): set(split_labels(r.get("labels", ""))) for r in gt_rows}
    collection = {normalize_fid(r["fname"]): set(split_labels(r.get("labels", ""))) for r in collection_rows}
    return {"name": name, "gt": gt, "collection": collection, "metadata": metadata}


def choose(partitions, deny_ids, per_class=14, seed=SEED):
    selected = []
    used_uploaders = set()
    diagnostics = {}

    for target in TARGETS:
        candidates = []
        stats = Counter()
        # Prefer eval because its released vocabulary is exhaustively labeled.
        for partition_priority, part in enumerate(partitions):
            gt, collection, metadata = part["gt"], part["collection"], part["metadata"]
            for fid, raw_labels in collection.items():
                if target not in raw_labels:
                    continue
                stats[f"{part['name']}_collection_label"] += 1
                if fid not in gt:
                    continue
                stats[f"{part['name']}_released_partition"] += 1
                if fid in deny_ids:
                    stats["denied_v1_id"] += 1
                    continue
                meta = metadata.get(fid)
                if not isinstance(meta, dict):
                    stats["metadata_missing"] += 1
                    continue
                uploader, license_value, title = metadata_fields(meta)
                if not uploader or not license_value:
                    stats["metadata_incomplete"] += 1
                    continue
                target_in_gt = target in gt[fid]
                rank = hashlib.sha256(
                    f"{seed}|{target}|{part['name']}|{fid}|{uploader}".encode()
                ).hexdigest()
                candidates.append(
                    (
                        partition_priority,
                        rank,
                        {
                            "candidate_id": f"fsd50k_{part['name']}_{fid}",
                            "target_class": target,
                            "freesound_id": fid,
                            "source_group": f"fsd50k-uploader:{uploader}",
                            "uploader": uploader,
                            "license": license_value,
                            "freesound_url": f"https://freesound.org/s/{fid}/",
                            "title": title,
                            "ground_truth_labels": ",".join(sorted(gt[fid])),
                            "collection_labels": ",".join(sorted(raw_labels)),
                            "target_exact_in_ground_truth": "YES" if target_in_gt else "NO",
                            "label_basis": (
                                "collection_raw_annotation+released_ground_truth"
                                if target_in_gt
                                else "collection_raw_annotation_requires_human_confirmation"
                            ),
                            "source_partition": f"FSD50K_{part['name']}",
                            "audio_acquired": "NO",
                            "pcm_sha256": "",
                            "human_audit_status": "NOT_REVIEWED",
                        },
                    )
                )
                stats["usable_metadata"] += 1

        candidates.sort(key=lambda x: (x[0], x[1]))
        picked = 0
        for _, _, row in candidates:
            if row["uploader"] in used_uploaders:
                stats["duplicate_uploader_skipped"] += 1
                continue
            used_uploaders.add(row["uploader"])
            selected.append(row)
            picked += 1
            if picked == per_class:
                break
        diagnostics[target] = dict(stats)
        if picked < per_class:
            raise ValueError(
                f"Only {picked} independent uploader candidates for {target}; need {per_class}; "
                f"diagnostics={diagnostics[target]}"
            )

    return selected, diagnostics


def canonical_identity(rows):
    lines = [
        "|".join(
            (
                r["candidate_id"],
                r["target_class"],
                r["freesound_id"],
                r["source_group"],
                r["license"],
            )
        )
        for r in sorted(rows, key=lambda x: x["candidate_id"])
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v1-manifest", type=Path, required=True)
    p.add_argument("--out-csv", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--per-class", type=int, default=14)
    p.add_argument("--seed", type=int, default=SEED)
    a = p.parse_args()
    if a.per_class < 10:
        raise ValueError("per-class must be >=10")

    raw = {name: download(url) for name, url in URLS.items()}
    partitions = [
        build_partition(
            "eval",
            csv_rows(raw["eval_ground_truth"]),
            csv_rows(raw["eval_collection"]),
            json.loads(raw["eval_metadata"].decode("utf-8")),
        ),
        build_partition(
            "dev",
            csv_rows(raw["dev_ground_truth"]),
            csv_rows(raw["dev_collection"]),
            json.loads(raw["dev_metadata"].decode("utf-8")),
        ),
    ]
    deny = v1_freesound_ids(a.v1_manifest)
    rows, diagnostics = choose(partitions, deny, a.per_class, a.seed)

    a.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(r["target_class"] for r in rows)
    partition_counts = Counter(r["source_partition"] for r in rows)
    groups = {r["source_group"] for r in rows}
    ids = {r["freesound_id"] for r in rows}
    if ids & deny:
        raise AssertionError("V1 Freesound leakage detected")
    if len(groups) != len(rows):
        raise AssertionError("uploader source groups are not unique")

    report = {
        "schema": "hesychia.pi15-external-target-candidate.v2",
        "status": "CANDIDATE_METADATA_ONLY_NOT_FROZEN",
        "selection_seed": a.seed,
        "source_dataset": "FSD50K collection annotations cross-referenced with released dev/eval sets",
        "target_counts": dict(counts),
        "partition_counts": dict(partition_counts),
        "candidate_rows": len(rows),
        "distinct_source_groups": len(groups),
        "v1_freesound_ids_denied": len(deny),
        "overlap_with_v1_freesound_ids": 0,
        "source_group_definition": "distinct Freesound uploader across the selected external cohort",
        "canonical_candidate_identity_sha256": canonical_identity(rows),
        "diagnostics": diagnostics,
        "upstream_files": {
            name: {"url": URLS[name], "sha256": sha256_bytes(data), "bytes": len(data)}
            for name, data in raw.items()
        },
        "label_interpretation": (
            "Collection annotations preserve raw human labels for small classes. "
            "A target may therefore appear in collection while having been merged into parent classes "
            "in the released 200-class ground truth. Such clips require explicit human target-purity confirmation."
        ),
        "gates_before_use": [
            "close OE1 human audit and apply exclusions",
            "acquire only selected audio clips without changing candidate IDs",
            "verify clip-level license and attribution",
            "convert/resample deterministically and record PCM SHA-256",
            "human-listen every selected external target clip for target purity",
            "add >=4 new speech speakers independent of V1",
            "freeze final scene manifest before any CNN/DSP/Oracle inference",
        ],
        "scientific_boundary": "Metadata selection is not a test result and does not unseal the confirmatory audio test.",
    }
    a.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
