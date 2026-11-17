#!/usr/bin/env python3
"""Select a metadata-only external LibriSpeech test-clean speaker cohort for PI15.

No audio is downloaded or decoded. The selector parses LibriSpeech SPEAKERS.TXT,
keeps only test-clean speakers, excludes every speaker_id already present in the
HESYCHIA V1 source manifest, and deterministically selects a balanced candidate
set. Audio acquisition and hashing happen only after OE1 closes and before freeze.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.request
from pathlib import Path

SPEAKERS_URL = (
    "https://raw.githubusercontent.com/oscarknagg/voicemap/master/"
    "data/LibriSpeech/SPEAKERS.TXT"
)
SEED = 20261117


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-thesis-metadata/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    if not data:
        raise ValueError("empty speaker metadata")
    return data


def v1_speaker_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = set()
    for row in rows:
        sid = (row.get("speaker_id") or "").strip()
        if sid.startswith("librispeech:"):
            ids.add(sid.split(":", 1)[1])
        group = (row.get("source_group") or "").strip()
        if group.startswith("librispeech:"):
            ids.add(group.split(":", 1)[1])
    if not ids:
        raise ValueError("V1 manifest yielded no LibriSpeech speaker IDs")
    return ids


def parse_speakers(raw: bytes):
    rows = []
    for line in raw.decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        reader_id, sex, subset, minutes = parts[:4]
        name = "|".join(parts[4:]).strip()
        if not reader_id.isdigit():
            continue
        rows.append(
            {
                "speaker_id": reader_id,
                "sex": sex,
                "subset": subset,
                "minutes": minutes,
                "name": name,
            }
        )
    if not rows:
        raise ValueError("speaker metadata parser produced no rows")
    return rows


def select(rows, deny: set[str], *, count=6, seed=SEED):
    candidates = [r for r in rows if r["subset"] == "test-clean" and r["speaker_id"] not in deny]
    if len(candidates) < count:
        raise ValueError(f"only {len(candidates)} independent test-clean speakers; need {count}")

    # Prefer balanced sex representation when possible, but selection is deterministic.
    selected = []
    per_sex = count // 2
    for sex in ("F", "M"):
        pool = [r for r in candidates if r["sex"] == sex]
        pool.sort(
            key=lambda r: (
                hashlib.sha256(f"{seed}|{sex}|{r['speaker_id']}".encode()).hexdigest(),
                r["speaker_id"],
            )
        )
        selected.extend(pool[:per_sex])

    if len(selected) < count:
        used = {r["speaker_id"] for r in selected}
        rest = [r for r in candidates if r["speaker_id"] not in used]
        rest.sort(
            key=lambda r: (
                hashlib.sha256(f"{seed}|rest|{r['speaker_id']}".encode()).hexdigest(),
                r["speaker_id"],
            )
        )
        selected.extend(rest[: count - len(selected)])

    if len({r["speaker_id"] for r in selected}) != count:
        raise AssertionError("speaker selection is not unique")

    return [
        {
            "candidate_id": f"librispeech_test_clean_{r['speaker_id']}",
            "speaker_id": f"librispeech:{r['speaker_id']}",
            "reader_id": r["speaker_id"],
            "sex": r["sex"],
            "subset": r["subset"],
            "declared_minutes": r["minutes"],
            "reader_name": r["name"],
            "source_group": f"librispeech:{r['speaker_id']}",
            "license": "CC BY 4.0",
            "audio_acquired": "NO",
            "pcm_sha256": "",
            "human_audit_status": "NOT_REVIEWED",
        }
        for r in selected
    ]


def canonical_identity(rows):
    lines = [
        "|".join((r["speaker_id"], r["sex"], r["subset"], r["license"]))
        for r in sorted(rows, key=lambda x: x["speaker_id"])
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v1-manifest", type=Path, required=True)
    p.add_argument("--out-csv", type=Path, required=True)
    p.add_argument("--out-json", type=Path, required=True)
    p.add_argument("--count", type=int, default=6)
    p.add_argument("--seed", type=int, default=SEED)
    a = p.parse_args()
    if a.count < 4:
        raise ValueError("count must be >=4")

    raw = download(SPEAKERS_URL)
    all_rows = parse_speakers(raw)
    deny = v1_speaker_ids(a.v1_manifest)
    selected = select(all_rows, deny, count=a.count, seed=a.seed)

    selected_ids = {r["reader_id"] for r in selected}
    if selected_ids & deny:
        raise AssertionError("V1 speaker leakage detected")
    if any(r["subset"] != "test-clean" for r in selected):
        raise AssertionError("non-test-clean speaker selected")

    a.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with a.out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(selected[0].keys()))
        w.writeheader()
        w.writerows(selected)

    test_clean_total = sum(r["subset"] == "test-clean" for r in all_rows)
    report = {
        "schema": "hesychia.pi15-external-speech-candidate.v1",
        "status": "CANDIDATE_METADATA_ONLY_NOT_FROZEN",
        "selection_seed": a.seed,
        "source_dataset": "LibriSpeech test-clean (SLR12)",
        "speaker_metadata_source": SPEAKERS_URL,
        "speaker_metadata_sha256": hashlib.sha256(raw).hexdigest(),
        "source_license": "CC BY 4.0",
        "test_clean_speakers_in_metadata": test_clean_total,
        "v1_speaker_ids_denied": len(deny),
        "selected_speakers": len(selected),
        "selected_female": sum(r["sex"] == "F" for r in selected),
        "selected_male": sum(r["sex"] == "M" for r in selected),
        "overlap_with_v1_speakers": 0,
        "canonical_candidate_identity_sha256": canonical_identity(selected),
        "gates_before_use": [
            "close OE1 human audit",
            "acquire selected test-clean audio from OpenSLR SLR12 without changing speaker IDs",
            "verify archive/checksum/license",
            "select and hash actual utterance PCM per speaker",
            "freeze >=4 speakers with the external target cohort before inference",
        ],
        "scientific_boundary": "Metadata selection is not a confirmatory result and does not open test audio.",
    }
    a.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
