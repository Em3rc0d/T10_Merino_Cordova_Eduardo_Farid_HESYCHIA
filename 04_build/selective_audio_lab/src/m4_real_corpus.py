"""Provenance-gated audio scene builder for M4 (train/validation, no test exposure).

The existence of a manifest row does NOT prove source isolation or valid license.
"""
from __future__ import annotations

import csv
from functools import lru_cache
import math
from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf

from m4_causal_frontend import SR, HOP
from m4_data_gate import audit_registry

ALLOWED_SPLITS = ("train", "val")


def load_approved_sources(registry: str | Path, *, experimental_pseudo: bool = False):
    """Stop if any declared source is missing, altered or crosses splits."""
    audit = audit_registry(registry, verify_files=True, strict_isolated=not experimental_pseudo)
    if audit["status"] != "PASS":
        raise ValueError("M4 source integrity gate BLOCKED: " + "; ".join(audit["problems"]))
    root = Path(registry).parent
    with Path(registry).open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        path = Path(row["path"])
        row["resolved_path"] = str(path if path.is_absolute() else root / path)
    return rows, audit


@lru_cache(maxsize=96)
def _read(path: str):
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if not np.isfinite(data).all() or data.size == 0:
        raise ValueError(f"nonfinite/empty audio {path}")
    mono = data.mean(axis=1)
    if sr != SR:
        gcd = math.gcd(sr, SR)
        mono = scipy.signal.resample_poly(mono, SR // gcd, sr // gcd).astype(np.float32)
    if np.sqrt(np.mean(mono.astype(np.float64)**2)) < 1e-5:
        raise ValueError(f"silent/unusable source: {path}")
    return mono


def segment(row: dict, rng: np.random.Generator, samples: int):
    audio = _read(row["resolved_path"])
    offset = int(rng.integers(0, len(audio) - samples + 1)) if len(audio) > samples else 0
    audio = audio[offset:offset+samples]
    if len(audio) < samples:
        audio = np.pad(audio, (0, samples-len(audio)))
    return audio.astype(np.float32), offset


def scene(rows: list[dict], *, split: str, rng: np.random.Generator,
          seconds: float = 4.0, target_present: bool = True,
          target_snr_db: float = 0., background_db: float = -10.):
    if split not in ALLOWED_SPLITS:
        raise ValueError("Training scene may only use train or val. Test is sealed.")
    n = int(round(seconds * SR))
    if n < HOP or n % HOP:
        raise ValueError("Duration must be a positive multiple of one 160-sample hop")
    pools = {role: [row for row in rows if row["split"] == split and row["role"] == role]
             for role in ("target", "protected", "background")}
    if any(not values for values in pools.values()):
        raise ValueError(f"Missing one of three source roles in split {split}")
    chosen = {role: pool[int(rng.integers(len(pool)))] for role, pool in pools.items()}
    protected, p_offset = segment(chosen["protected"], rng, n)
    background, b_offset = segment(chosen["background"], rng, n)
    if target_present:
        target, t_offset = segment(chosen["target"], rng, n)
    else:
        target, t_offset = np.zeros(n, dtype=np.float32), None

    def adjust(wave, reference, db):
        rw = float(np.sqrt(np.mean(wave.astype(np.float64)**2)))
        rr = float(np.sqrt(np.mean(reference.astype(np.float64)**2)))
        if rw < 1e-5 or rr < 1e-5:
            raise ValueError("Silent source/invalid SNR normalization")
        return (wave * (rr / rw) * 10**(db/20)).astype(np.float32)

    if target_present:
        target = adjust(target, protected, target_snr_db)
    background = adjust(background, protected, background_db)
    mix = protected + target + background
    peak = float(np.max(np.abs(mix)))
    scale = max(1., peak / .95)
    protected, target, background = (v / scale for v in (protected, target, background))
    mix = protected + target + background
    return dict(mixture=mix.astype(np.float32), target=target.astype(np.float32),
                protected=protected.astype(np.float32), background=background.astype(np.float32),
                provenance=dict(split=split, source_ids={k: v["source_id"] for k,v in chosen.items()},
                                offsets={"target": t_offset,"protected": p_offset,"background": b_offset},
                                target_present=target_present, target_snr_db=target_snr_db,
                                background_db=background_db))
