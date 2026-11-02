"""Pinned public audio acquisition and source-group split audit.

ESC-50 clips are candidate pseudo-stems. No automatic isolation approval.
Downloading public, licensed research data is distinct from certifying its quality.
"""
from __future__ import annotations

import csv
import hashlib
import math
import re
import tarfile
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf

from .common import canonical_hash, read_json, sha256, write_json

ESC_REV = "33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6"
ESC_ROOT = f"https://raw.githubusercontent.com/karolpiczak/ESC-50/{ESC_REV}"
TARGETS = ("vacuum_cleaner", "chainsaw")
CATEGORIES = TARGETS + ("rain", "wind", "clock_alarm", "siren")
SPEECH_MD5 = "5df7d4e78065366204ca6845bb08f490"
SPEECH_URL = "https://www.openslr.org/resources/31/train-clean-5.tar.gz"
SR = 16000


def download(url, dest, max_bytes=500_000_000, retries=3):
    """Atomic, bounded public download; record actual content SHA separately."""
    dest = Path(dest)
    if dest.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-research/1"})
            with urllib.request.urlopen(req, timeout=60) as r, part.open("wb") as f:
                size = 0
                while b := r.read(1024 * 1024):
                    size += len(b)
                    if size > max_bytes:
                        raise ValueError("Download exceeds declared maximum")
                    f.write(b)
            part.replace(dest)
            return dest
        except Exception:
            part.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            time.sleep(min(attempt + 1, 3))


def _extract_speech(archive, root):
    digest = hashlib.md5()
    with archive.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != SPEECH_MD5:
        raise ValueError("OpenSLR archive fails publisher MD5")
    marker = root / "speech_extracted.json"
    if marker.exists():
        if read_json(marker)["archive_sha256"] != sha256(archive):
            raise ValueError("Speech extraction marker/archive mismatch")
        return
    # Only canonical regular FLACs; no tar links, metadata paths or executables.
    count, total = 0, 0
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            if not member.name.endswith(".flac"):
                continue
            if not member.isfile() or not re.fullmatch(
                    r"LibriSpeech/train-clean-5/\d+/\d+/\d+-\d+-\d+\.flac", member.name):
                raise ValueError("Noncanonical speech archive member")
            total += member.size
            count += 1
            if member.size > 30_000_000 or total > 2_000_000_000 or count > 10000:
                raise ValueError("Expanded speech archive exceeds limits")
            dest = root / member.name
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as src, dest.open("wb") as out:
                    while b := src.read(1024 * 1024):
                        out.write(b)
    write_json(marker, {"archive_sha256": sha256(archive), "flac_files": count})


def _convert(original, pcm):
    x, rate = sf.read(original, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if rate != SR:
        gcd = math.gcd(rate, SR)
        x = scipy.signal.resample_poly(x, SR // gcd, rate // gcd).astype(np.float32)
    if not np.isfinite(x).all() or len(x) < SR:
        raise ValueError(f"Invalid/short original audio: {original}")
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    if rms < 1e-5:
        raise ValueError(f"Silent source: {original}")
    pcm.parent.mkdir(parents=True, exist_ok=True)
    sf.write(pcm, x, SR, subtype="FLOAT")
    # Hash a sample-quantized normalized waveform to catch exact gain/format copies.
    normalized = x / max(float(np.max(np.abs(x))), 1e-8)
    fingerprint = hashlib.sha256(np.round(normalized * 4096).astype("<i2").tobytes()).hexdigest()
    return {"duration_s": len(x) / SR, "rms": rms,
            "clipped_fraction": float(np.mean(np.abs(x) >= .999)),
            "pcm_sha256": sha256(pcm), "normalized_pcm_hash": fingerprint}


def audit_assets(assets, root=None, verify_files=True):
    errors, groups, ids = [], defaultdict(set), set()
    for asset in assets:
        aid, split = asset["asset_id"], asset["split"]
        if aid in ids or split not in ("train", "val", "test"):
            errors.append(f"duplicate id/invalid split: {aid}")
        ids.add(aid)
        for key in ("source_group", "speaker_id", "raw_sha256", "pcm_sha256", "normalized_pcm_hash"):
            if asset.get(key):
                groups[(key, asset[key])].add(split)
        if not asset.get("source_group") or not asset.get("license_evidence"):
            errors.append(f"missing source/license evidence: {aid}")
        if asset["role"] == "speech" and not asset.get("speaker_id"):
            errors.append(f"missing speech identity: {aid}")
        if verify_files:
            path = Path(root) / asset["path"]
            if not path.is_file() or sha256(path) != asset["pcm_sha256"]:
                errors.append(f"missing/changed PCM: {aid}")
    for key, splits in groups.items():
        if len(splits) > 1:
            errors.append(f"cross-split leakage {key[0]}: {key[1]}")
    for split in ("train", "val", "test"):
        for cls in TARGETS + ("speech", "background", "alert"):
            if not any(a["split"] == split and (a["class"] == cls or a["role"] == cls)
                       for a in assets):
                errors.append(f"missing {split}/{cls}")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors,
            "counts": dict(Counter(f"{a['split']}/{a['role']}/{a['class']}" for a in assets)),
            "source_groups": {s: len({a["source_group"] for a in assets if a["split"] == s})
                              for s in ("train", "val", "test")},
            "scope": "Exact bytes, normalized exact PCM, declared source and speaker identity; "
                     "not a perceptual near-duplicate or source-purity certification."}


def prepare(root, *, speech_per_speaker=4, workers=6):
    root = Path(root).resolve()
    if (root / "registry.json").exists():
        raise ValueError("Corpus already registered; use a fresh root for a new version")
    raw = root / "raw"
    for remote, name in (("meta/esc50.csv", "esc50.csv"), ("LICENSE", "LICENSE_ESC50.txt"),
                         ("README.md", "ESC50_README.md")):
        # Always use a revision-specific metadata copy, even if staging files exist.
        download(f"{ESC_ROOT}/{remote}", raw / f"pinned_{name}", 2_000_000)
    download("https://www.openslr.org/31/", raw / "SLR31.html", 1_000_000)
    download("https://www.openslr.org/resources/31/md5sum.txt", raw / "SLR31_md5sum.txt", 10000)
    checksums = (raw / "SLR31_md5sum.txt").read_text()
    if f"{SPEECH_MD5}  train-clean-5.tar.gz" not in checksums:
        raise ValueError("Publisher speech checksum listing differs")
    with (raw / "pinned_esc50.csv").open() as f:
        meta = [r for r in csv.DictReader(f) if r["category"] in CATEGORIES]

    def acquire(row):
        return download(f"{ESC_ROOT}/audio/{row['filename']}", raw / "esc50" / row["filename"], 2_000_000)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(acquire, meta))
    archive = download(SPEECH_URL, raw / "train-clean-5.tar.gz", 400_000_000)
    _extract_speech(archive, raw)
    assets = []
    license_text = (raw / "pinned_LICENSE_ESC50.txt").read_text()
    for row in meta:
        original = raw / "esc50" / row["filename"]
        aid = "esc50_" + Path(row["filename"]).stem
        pcm = root / "pcm" / f"{aid}.wav"
        role = "target" if row["category"] in TARGETS else (
            "alert" if row["category"] in ("siren", "clock_alarm") else "background")
        # Official source-file folds, no reshuffling of excerpts across partitions.
        split = "train" if int(row["fold"]) <= 3 else ("val" if row["fold"] == "4" else "test")
        stem = "-".join(row["filename"].split("-")[:-1])
        attribution = [line for line in license_text.splitlines() if f"[{stem}.ogg]" in line]
        if len(attribution) != 1:
            raise ValueError(f"Missing/ambiguous per-clip attribution: {aid}")
        assets.append(dict(asset_id=aid, role=role, **{"class": row["category"]}, split=split,
                           source_group="freesound:" + row["src_file"], speaker_id="",
                           path=str(pcm.relative_to(root)), raw_sha256=sha256(original),
                           origin=f"{ESC_ROOT}/audio/{row['filename']}",
                           license="CC-BY-NC-3.0 (ESC-50 collection); see per-clip attribution",
                           attribution=attribution[0], license_evidence="raw/pinned_LICENSE_ESC50.txt",
                           review="PENDING_HUMAN_ISOLATION_REVIEW", reference_grade="pseudo_stem",
                           **_convert(original, pcm)))
    speech_root = raw / "LibriSpeech" / "train-clean-5"
    speakers = sorted(p.name for p in speech_root.iterdir() if p.is_dir())
    # Partition identities BEFORE selecting clips. Deterministic, unrelated to model/test scores.
    speakers.sort(key=lambda s: canonical_hash(["m4-speech-split-v1", s]))
    ntrain, nval = int(.7 * len(speakers)), max(2, int(.15 * len(speakers)))
    for idx, speaker in enumerate(speakers):
        split = "train" if idx < ntrain else ("val" if idx < ntrain + nval else "test")
        clips = sorted((speech_root / speaker).rglob("*.flac"))
        clips.sort(key=lambda p: canonical_hash(["speech-clip-v1", p.stem]))
        for original in clips[:speech_per_speaker]:
            aid = "slr31_" + original.stem
            pcm = root / "pcm" / f"{aid}.wav"
            assets.append(dict(asset_id=aid, role="speech", **{"class": "speech"}, split=split,
                               source_group="librispeech:" + speaker,
                               speaker_id="librispeech:" + speaker,
                               path=str(pcm.relative_to(root)), raw_sha256=sha256(original),
                               origin=SPEECH_URL + "#" + str(original.relative_to(raw)),
                               license="CC-BY-4.0", license_evidence="raw/SLR31.html",
                               attribution="LibriSpeech: Panayotov, Chen, Povey and Khudanpur (2015)",
                               review="PENDING_HUMAN_SPEECH_REVIEW", reference_grade="speech",
                               **_convert(original, pcm)))
    audit = audit_assets(assets, root)
    write_json(root / "leakage_report.json", audit)
    if audit["status"] != "PASS":
        raise ValueError(f"Corpus audit blocked: {audit['errors']}")
    manifest = dict(schema="m4-sci-sources-v1", targets=list(TARGETS), assets=assets,
                    esc_revision=ESC_REV, speech_archive_sha256=sha256(archive),
                    academic_research_only=True, review_status="PENDING_HUMAN_REVIEW",
                    evidence_sha256={p.name: sha256(p) for p in raw.iterdir()
                                     if p.is_file() and p.suffix in (".txt", ".md", ".csv", ".html")},
                    acquisition_scope="real recordings, synthetically mixed; ESC pseudo-stems",
                    limitations=["No source isolation or listening review certified",
                                 "No perceptual/cropped near-duplicate search certified",
                                 "Speech is English read speech; no Spanish or clinical validation",
                                 "ESC-50 source folds are not a separate field-domain test"])
    write_json(root / "registry.json", manifest)
    with (root / "human_review.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=("asset_id", "split", "class", "path", "pcm_sha256",
                                               "source_group", "isolation_review", "reviewer", "note"))
        writer.writeheader()
        for a in assets:
            writer.writerow({**{k: a[k] for k in ("asset_id", "split", "class", "path", "pcm_sha256", "source_group")},
                             "isolation_review": "PENDING", "reviewer": "", "note": ""})
    return audit


def load_registry(root, *, allow_unreviewed=False, splits=("train", "val")):
    root = Path(root)
    reg = read_json(root / "registry.json")
    if reg["review_status"] != "APPROVED" and not allow_unreviewed:
        raise ValueError("Corpus review pending; use --pilot-unreviewed for declared pilot only")
    # Metadata audit across all partitions. Decode/hash only the requested partitions.
    audit = audit_assets(reg["assets"], verify_files=False)
    if audit["status"] != "PASS":
        raise ValueError(str(audit["errors"]))
    for a in reg["assets"]:
        if a["split"] in splits and sha256(root / a["path"]) != a["pcm_sha256"]:
            raise ValueError(f"PCM changed: {a['asset_id']}")
    return reg
