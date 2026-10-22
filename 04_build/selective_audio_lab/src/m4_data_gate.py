"""Audita registro M4 por fuente antes de generar mezclas; NO certifica calidad acústica."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = ("source_id", "role", "split", "recording_id", "speaker_id",
          "path", "sha256", "license", "reference_grade")
SPLITS = {"train", "val", "test"}
ROLES = {"target", "protected", "background"}
GRADES = {"target": {"isolated", "pseudo_stem"},
          "protected": {"speech"}, "background": {"background"}}
HASH = re.compile(r"^[a-fA-F0-9]{64}$")


def checksum(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def audit_registry(registry: str | Path, *, verify_files: bool = True,
                   strict_isolated: bool = True) -> dict:
    path = Path(registry)
    with path.open(encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        missing = sorted(set(FIELDS) - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"missing fields: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError("empty registry")
    errors = []
    ids = set()
    by_recording, by_speaker, by_hash = defaultdict(set), defaultdict(set), defaultdict(set)
    counts = Counter()
    for number, row in enumerate(rows, 2):
        item = {key: (row.get(key) or "").strip() for key in FIELDS}
        sid, role, split = item["source_id"], item["role"], item["split"]
        record, speaker = item["recording_id"], item["speaker_id"]
        digest, grade = item["sha256"].lower(), item["reference_grade"]
        if not sid or sid in ids:
            errors.append(f"line {number}: empty or duplicate source_id")
        ids.add(sid)
        if split not in SPLITS or role not in ROLES or grade not in GRADES.get(role, set()):
            errors.append(f"line {number}: invalid split/role/reference_grade")
        if not record:
            errors.append(f"line {number}: recording_id missing")
        if role == "protected" and not speaker:
            errors.append(f"line {number}: speaker_id missing")
        if item["license"].lower() in {"", "unknown", "none", "tbd"}:
            errors.append(f"line {number}: license missing/unknown")
        if not HASH.fullmatch(digest):
            errors.append(f"line {number}: invalid sha256")
        if strict_isolated and role == "target" and grade != "isolated":
            errors.append(f"line {number}: pseudo_stem cannot serve as isolated reference")
        if record and split in SPLITS:
            by_recording[record].add(split)
        if role == "protected" and speaker and split in SPLITS:
            by_speaker[speaker].add(split)
        if HASH.fullmatch(digest) and split in SPLITS:
            by_hash[digest].add(split)
        counts[(split, role)] += 1
        if verify_files:
            audio = Path(item["path"])
            if not audio.is_absolute():
                audio = path.parent / audio
            if not audio.is_file():
                errors.append(f"line {number}: audio file missing")
            elif HASH.fullmatch(digest) and checksum(audio) != digest:
                errors.append(f"line {number}: SHA256 mismatch")
    for kind, groups in (("recording_id", by_recording),
                         ("speaker_id", by_speaker), ("sha256", by_hash)):
        count = sum(len(partitions) > 1 for partitions in groups.values())
        if count:
            errors.append(f"cross-split leakage by {kind}: {count}")
    for split in sorted(SPLITS):
        for role in sorted(ROLES):
            if not counts[(split, role)]:
                errors.append(f"missing {split}/{role} source")
    return {
        "schema_version": "m4-source-registry-v1",
        "status": "PASS" if not errors else "BLOCKED",
        "rows": len(rows),
        "verify_files": verify_files,
        "reference_scope": "isolated_target" if strict_isolated else "pseudo_stem_permitted",
        "counts": {f"{split}/{role}": counts[(split, role)]
                   for split in sorted(SPLITS) for role in sorted(ROLES)},
        "problems": errors,
        "caveat": ("Passing validates declared provenance keys and hashes only; "
                   "does not establish source isolation, rights clearance, "
                   "near-duplicate absence or statistical independence."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-file-hashes", action="store_true",
                    help="Schema smoke test only: not a source-integrity gate")
    ap.add_argument("--allow-pseudo-stems", action="store_true",
                    help="Experimental claim becomes pseudo-stem attenuation")
    args = ap.parse_args()
    result = audit_registry(args.registry, verify_files=not args.skip_file_hashes,
                            strict_isolated=not args.allow_pseudo_stems)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
