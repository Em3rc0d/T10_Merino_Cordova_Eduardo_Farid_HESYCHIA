#!/usr/bin/env python3
"""Prepare a metadata-only external target cohort candidate for PI15.

No audio bytes are downloaded or decoded. The script selects FSD50K evaluation
clips for the two HESYCHIA target classes while excluding every Freesound ID
already present in the V1 corpus and enforcing distinct uploader groups.

This is a candidate-selection step only. It MUST NOT be treated as a frozen test
or model evaluation until OE1 audit/exclusions are closed and the selected audio
bytes are acquired, hashed and passed through the freeze gate.
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
}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-thesis-metadata/1"})
    with urllib.request.urlopen(req, timeout=90) as response:
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
    # FSD50K metadata has historically used these keys; tolerate harmless naming variants.
    uploader = str(meta.get("uploader") or meta.get("username") or "").strip()
    license_value = str(meta.get("license") or meta.get("licence") or "").strip()
    title = str(meta.get("title") or "").strip()
    return uploader, license_value, title


def choose(gt_rows, collection_rows, metadata, deny_ids, per_class=12, seed=SEED):
    gt = {str(r["fname"]).strip(): set(split_labels(r.get("labels", ""))) for r in gt_rows}
    collection = {str(r["fname"]).strip(): set(split_labels(r.get("labels", ""))) for r in collection_rows}
    selected = []
    used_uploaders = set()

    for target in TARGETS:
        candidates = []
        for fid, labels in collection.items():
            if target not in labels:
                continue
            if fid not in gt or target not in gt[fid]:
                continue
            if fid in deny_ids:
                continue
            meta = metadata.get(fid) or metadata.get(int(fid) if fid.isdigit() else fid)
            if not isinstance(meta, dict):
                continue
            uploader, license_value, title = metadata_fields(meta)
            if not uploader or not license_value:
                continue
            # Deterministic order independent of upstream row order.
            rank = hashlib.sha256(f"{seed}|{target}|{fid}|{uploader}".encode()).hexdigest()
            candidates.append((rank, fid, uploader, license_value, title, sorted(gt[fid]), sorted(labels)))
        candidates.sort()

        picked = 0
        for _, fid, uploader, license_value, title, labels_gt, labels_collection in candidates:
            if uploader in used_uploaders:
                continue
            used_uploaders.add(uploader)
            selected.append({
                "candidate_id": f"fsd50k_eval_{fid}",
                "target_class": target,
                "freesound_id": fid,
                "source_group": f"fsd50k-uploader:{uploader}",
                "uploader": uploader,
                "license": license_value,
                "freesound_url": f"https://freesound.org/s/{fid}/",
                "title": title,
                "ground_truth_labels": ",".join(labels_gt),
                "collection_labels": ",".join(labels_collection),
                "source_partition": "FSD50K_eval",
                "audio_acquired": "NO",
                "pcm_sha256": "",
                "human_audit_status": "NOT_REVIEWED",
            })
            picked += 1
            if picked == per_class:
                break
        if picked < per_class:
            raise ValueError(f"Only {picked} independent uploader candidates for {target}; need {per_class}")

    return selected


def canonical_identity(rows):
    lines = [
        "|".join((r["candidate_id"], r["target_class"], r["freesound_id"], r["source_group"], r["license"]))
        for r in sorted(rows, key=lambda x: x["candidate_id"])
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v1-manifest", type=Path, required=True)
    p.add_argument("--out-csv", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--per-class", type=int, default=12)
    p.add_argument("--seed", type=int, default=SEED)
    a = p.parse_args()
    if a.per_class < 10:
        raise ValueError("per-class must be >=10 so total independent target groups can reach >=20")

    raw = {name: download(url) for name, url in URLS.items()}
    gt_rows = csv_rows(raw["eval_ground_truth"])
    collection_rows = csv_rows(raw["eval_collection"])
    metadata = json.loads(raw["eval_metadata"].decode("utf-8"))
    deny = v1_freesound_ids(a.v1_manifest)
    rows = choose(gt_rows, collection_rows, metadata, deny, a.per_class, a.seed)

    a.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    counts = Counter(r["target_class"] for r in rows)
    groups = {r["source_group"] for r in rows}
    ids = {r["freesound_id"] for r in rows}
    if ids & deny:
        raise AssertionError("V1 Freesound leakage detected")
    if len(groups) != len(rows):
        raise AssertionError("uploader source groups are not unique")

    report = {
        "schema": "hesychia.pi15-external-target-candidate.v1",
        "status": "CANDIDATE_METADATA_ONLY_NOT_FROZEN",
        "selection_seed": a.seed,
        "source_dataset": "FSD50K evaluation set",
        "source_repository": "Fhrozen/FSD50k mirror of official FSD50K",
        "target_counts": dict(counts),
        "candidate_rows": len(rows),
        "distinct_source_groups": len(groups),
        "v1_freesound_ids_denied": len(deny),
        "overlap_with_v1_freesound_ids": 0,
        "source_group_definition": "distinct FSD50K Freesound uploader, conservative grouping across clips",
        "canonical_candidate_identity_sha256": canonical_identity(rows),
        "upstream_files": {
            name: {"url": URLS[name], "sha256": sha256_bytes(data), "bytes": len(data)}
            for name, data in raw.items()
        },
        "gates_before_use": [
            "close OE1 human audit and apply exclusions",
            "acquire only the selected audio clips without changing IDs",
            "verify clip-level license and attribution",
            "convert/resample deterministically and record PCM SHA-256",
            "human-listen selected external clips for target purity",
            "add >=4 new speech speakers independent of V1",
            "freeze final scene manifest before any CNN/DSP/Oracle inference",
        ],
        "scientific_boundary": "Metadata selection is not a test result and does not unseal the confirmatory audio test.",
    }
    a.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
