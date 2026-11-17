#!/usr/bin/env python3
"""HESYCHIA confirmatory paired analysis v2.

Adds cluster BCa intervals and the pre-specified four-case joint decision rule.
CSV schema: one row per scene/method (CNN, DSP, ORACLE), with identical mix_sha256
within each scene and fields scene_id, source_group, speaker_group, method,
a_target_db and a_protected_db.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import norm

METHODS = ("CNN", "DSP", "ORACLE")
REQUIRED = (
    "scene_id", "source_group", "speaker_group", "mix_sha256", "method",
    "a_target_db", "a_protected_db",
)


def read_pairs(path: Path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in REQUIRED):
            raise ValueError("CSV missing required columns")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV has no rows")

    scenes = defaultdict(dict)
    source_group, speaker_group, mix_hash = {}, {}, {}
    for r in rows:
        sid = r["scene_id"].strip()
        method = r["method"].strip().upper()
        if not sid or method not in METHODS:
            raise ValueError("Invalid scene_id or method")
        if method in scenes[sid]:
            raise ValueError(f"Duplicate scene/method: {sid}/{method}")
        for field, registry in (("source_group", source_group), ("speaker_group", speaker_group), ("mix_sha256", mix_hash)):
            value = r[field].strip().lower() if field == "mix_sha256" else r[field].strip()
            if sid in registry and registry[sid] != value:
                raise ValueError(f"Inconsistent {field} within scene {sid}")
            registry[sid] = value
        h = mix_hash[sid]
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError(f"Invalid mix_sha256 for {sid}")
        vals = [float(r["a_target_db"]), float(r["a_protected_db"])]
        if not all(math.isfinite(v) for v in vals):
            raise ValueError(f"Non-finite metric in {sid}/{method}")
        scenes[sid][method] = vals

    bad = [sid for sid, methods in scenes.items() if set(methods) != set(METHODS)]
    if bad:
        raise ValueError("Every scene must include CNN, DSP and ORACLE")
    ids = sorted(scenes)
    data = np.array([[scenes[sid][m] for m in METHODS] for sid in ids], dtype=float)
    return ids, source_group, speaker_group, data


def _cluster_indices(groups):
    unique = sorted(set(groups))
    if len(unique) < 3:
        raise ValueError("At least three independent clusters are required")
    by = {g: np.asarray([i for i, x in enumerate(groups) if x == g], dtype=int) for g in unique}
    return unique, by


def cluster_bootstrap(values, groups, *, seed=20261117, n_boot=10000):
    values = np.asarray(values, dtype=float)
    unique, by = _cluster_indices(groups)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        chosen = rng.integers(0, len(unique), size=len(unique))
        idx = np.concatenate([by[unique[j]] for j in chosen])
        boot[b] = float(np.mean(values[idx]))
    return boot, unique, by


def _bca_quantile(boot, theta_hat, jack, alpha):
    p = float(np.mean(boot < theta_hat))
    p = np.clip(p, 1.0 / (2 * len(boot)), 1.0 - 1.0 / (2 * len(boot)))
    z0 = norm.ppf(p)
    jack_bar = float(np.mean(jack))
    dif = jack_bar - jack
    denom = 6.0 * (np.sum(dif ** 2) ** 1.5)
    acc = float(np.sum(dif ** 3) / denom) if denom > 0 else 0.0
    za = norm.ppf(alpha)
    adjusted = norm.cdf(z0 + (z0 + za) / (1.0 - acc * (z0 + za)))
    adjusted = float(np.clip(adjusted, 0.0, 1.0))
    return float(np.quantile(boot, adjusted)), {"z0": float(z0), "acceleration": acc, "adjusted_alpha": adjusted}


def cluster_intervals(values, groups, *, seed=20261117, n_boot=10000):
    values = np.asarray(values, dtype=float)
    boot, unique, by = cluster_bootstrap(values, groups, seed=seed, n_boot=n_boot)
    theta = float(np.mean(values))
    jack = np.array([float(np.mean(np.delete(values, by[g]))) for g in unique], dtype=float)
    p_lo, p_hi = np.quantile(boot, [0.025, 0.975])
    p_one_lo, p_one_hi = np.quantile(boot, [0.05, 0.95])
    bca_lo, meta_lo = _bca_quantile(boot, theta, jack, 0.025)
    bca_hi, meta_hi = _bca_quantile(boot, theta, jack, 0.975)
    bca_one_lo, meta_one_lo = _bca_quantile(boot, theta, jack, 0.05)
    bca_one_hi, meta_one_hi = _bca_quantile(boot, theta, jack, 0.95)
    return {
        "mean": theta,
        "cluster_count": len(unique),
        "n_boot": n_boot,
        "seed": seed,
        "percentile_ci95": [float(p_lo), float(p_hi)],
        "percentile_one_sided95": {"lower": float(p_one_lo), "upper": float(p_one_hi)},
        "bca_ci95": [bca_lo, bca_hi],
        "bca_one_sided95": {"lower": bca_one_lo, "upper": bca_one_hi},
        "bca_diagnostics": {
            "two_sided_low": meta_lo, "two_sided_high": meta_hi,
            "one_sided_low": meta_one_lo, "one_sided_high": meta_one_hi,
        },
    }


def joint_decision(target_stats, protected_stats, *, voice_margin_db=1.0):
    target_pass = target_stats["bca_one_sided95"]["lower"] > 0.0
    voice_pass = protected_stats["bca_one_sided95"]["upper"] <= voice_margin_db
    if target_pass and voice_pass:
        code = "REJECT_H0_SELECTIVE_ADVANTAGE"
        interpretation = "CNN attenuates the target more than DSP while meeting protected-speech non-inferiority."
    elif target_pass and not voice_pass:
        code = "H1_NOT_SUPPORTED_TARGET_GAIN_WITH_VOICE_COST"
        interpretation = "CNN improves target attenuation, but protected-speech non-inferiority is not met."
    elif not target_pass and voice_pass:
        code = "H1_NOT_SUPPORTED_NO_TARGET_ADVANTAGE"
        interpretation = "No confirmatory target-attenuation advantage over DSP; protected speech is non-inferior."
    else:
        code = "H1_NOT_SUPPORTED_NEITHER_CONDITION"
        interpretation = "CNN does not establish target superiority or protected-speech non-inferiority versus DSP."
    return {
        "target_superiority": target_pass,
        "voice_noninferiority": voice_pass,
        "voice_margin_db": voice_margin_db,
        "decision_code": code,
        "interpretation": interpretation,
    }


def analyze(path: Path, *, seed=20261117, n_boot=10000, voice_margin_db=1.0):
    ids, src, spk, data = read_pairs(path)
    source_groups = [src[sid] for sid in ids]
    speaker_groups = [spk[sid] for sid in ids]
    delta_target = data[:, 0, 0] - data[:, 1, 0]
    delta_protected = data[:, 0, 1] - data[:, 1, 1]
    target = cluster_intervals(delta_target, source_groups, seed=seed, n_boot=n_boot)
    protected = cluster_intervals(delta_protected, source_groups, seed=seed + 1, n_boot=n_boot)
    sensitivity = {
        "target_by_speaker": cluster_intervals(delta_target, speaker_groups, seed=seed + 2, n_boot=n_boot),
        "protected_by_speaker": cluster_intervals(delta_protected, speaker_groups, seed=seed + 3, n_boot=n_boot),
    }
    method_means = {}
    for j, m in enumerate(METHODS):
        method_means[m] = {
            "a_target_db_mean": float(np.mean(data[:, j, 0])),
            "a_protected_db_mean": float(np.mean(data[:, j, 1])),
            "both_ok_6_1": int(np.sum((data[:, j, 0] >= 6.0) & (data[:, j, 1] <= 1.0))),
            "n": len(ids),
        }
    return {
        "schema": "hesychia.pi14-confirmatory-analysis.v2",
        "scene_count": len(ids),
        "source_group_count": len(set(source_groups)),
        "speaker_group_count": len(set(speaker_groups)),
        "paired_mix_sha256_verified": True,
        "estimands": {
            "cnn_minus_dsp_target_db": target,
            "cnn_minus_dsp_protected_loss_db": protected,
        },
        "speaker_cluster_sensitivity": sensitivity,
        "joint_decision": joint_decision(target, protected, voice_margin_db=voice_margin_db),
        "method_means": method_means,
        "notes": [
            "Primary resampling unit: source_group; all scenes in sampled groups remain together.",
            "BCa and percentile intervals are both reported; the pre-specified decision uses one-sided 95% BCa bounds.",
            "Oracle is a privileged reference and is not part of the CNN-vs-DSP hypothesis test.",
            "Historical both_ok 6/1 dB is descriptive only.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--by-scene", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20261117)
    p.add_argument("--boot", type=int, default=10000)
    p.add_argument("--voice-margin-db", type=float, default=1.0)
    a = p.parse_args()
    res = analyze(a.by_scene, seed=a.seed, n_boot=a.boot, voice_margin_db=a.voice_margin_db)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res["joint_decision"], ensure_ascii=False))


if __name__ == "__main__":
    main()
