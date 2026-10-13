from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

import librosa
import numpy as np
import pandas as pd

from attenuation import apply_selective_attenuation
from audio_core import SR, DURATION
from policy import resolve_policy
from urbansound8k import audio_path, load_metadata, validate_contract

EPS = 1e-9


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64) + EPS))


def peak_normalize(x: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak <= 0:
        return x.astype(np.float32)
    return (x / peak).astype(np.float32)


def load_segment(path: Path, rng: np.random.Generator) -> np.ndarray:
    duration = float(librosa.get_duration(path=str(path)))
    max_offset = max(0.0, duration - DURATION)
    offset = float(rng.uniform(0.0, max_offset)) if max_offset > 0 else 0.0
    y, _ = librosa.load(
        str(path),
        sr=SR,
        mono=True,
        offset=offset,
        duration=DURATION,
        res_type="soxr_hq",
    )
    target_len = int(SR * DURATION)
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]
    return peak_normalize(y)


def scale_to_relative_db(x: np.ndarray, ref: np.ndarray, db: float) -> np.ndarray:
    desired = rms(ref) * (10.0 ** (db / 20.0))
    return (x * (desired / (rms(x) + EPS))).astype(np.float32)


def ci95(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=np.float64)
    n = len(arr)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
    return {
        "mean": mean,
        "sd": sd,
        "ci95_low": mean - half,
        "ci95_high": mean + half,
        "n": n,
    }


def collect_speech(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.flac")) + sorted(root.rglob("*.wav"))
    if not files:
        raise FileNotFoundError(
            f"No .flac/.wav speech files found under {root}"
        )
    return files


def run_batch(
    dataset_root: str | Path,
    speech_root: str | Path,
    out_dir: str | Path,
    *,
    n: int = 100,
    seed: int = 42,
    target_snrs: tuple[float, ...] = (-5.0, 0.0, 5.0, 10.0),
    caps: tuple[float, ...] = (12.0, 18.0, 24.0, 30.0),
    background_db: float = -10.0,
):
    if n < 100:
        raise ValueError("Scientific batch requires n >= 100")
    root = Path(dataset_root)
    speech_root = Path(speech_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    validate_contract(root, require_official_shape=True, verify_audio=True)
    df = load_metadata(root)
    sirens = df[df["class"] == "siren"].copy()
    backgrounds = df[df["class"].isin([
        "air_conditioner", "engine_idling", "street_music"
    ])].copy()
    speech_files = collect_speech(speech_root)
    if len(sirens) < 1 or len(backgrounds) < 1:
        raise RuntimeError("UrbanSound8K siren/background pool is empty")

    rng = np.random.default_rng(seed)
    rows = []
    for mix_id in range(n):
        siren_row = sirens.iloc[int(rng.integers(0, len(sirens)))]
        bg_row = backgrounds.iloc[int(rng.integers(0, len(backgrounds)))]
        speech_path = speech_files[int(rng.integers(0, len(speech_files)))]
        snr_db = float(target_snrs[mix_id % len(target_snrs)])

        speech = load_segment(speech_path, rng)
        target = load_segment(
            audio_path(root, int(siren_row.fold), str(siren_row.slice_file_name)),
            rng,
        )
        background = load_segment(
            audio_path(root, int(bg_row.fold), str(bg_row.slice_file_name)),
            rng,
        )
        target = scale_to_relative_db(target, speech, snr_db)
        background = scale_to_relative_db(background, speech, background_db)

        for cap_db in caps:
            policy = resolve_policy("siren", ("speech",), cap_db)
            _, _, _, _, _, _, _, metrics = apply_selective_attenuation(
                speech, target, background, policy, alpha=1.0
            )
            rows.append({
                "mix_id": mix_id,
                "seed": seed,
                "siren_file": str(siren_row.slice_file_name),
                "speech_file": speech_path.name,
                "background_file": str(bg_row.slice_file_name),
                "target_snr_db": snr_db,
                "background_relative_db": background_db,
                "cap_db": cap_db,
                "A_target_db": metrics["A_target_db"],
                "A_protected_db": metrics["A_protected_db"],
                "SI_SDRi_protected_db": metrics["SI_SDRi_protected_db"],
                "SI_SDRi_target_db": metrics["SI_SDRi_target_db"],
                "gain_min": metrics["gain_min"],
            })
        if mix_id == 0 or (mix_id + 1) % 10 == 0 or mix_id + 1 == n:
            print(f"[real-mixtures] {mix_id + 1}/{n}", flush=True)

    result = pd.DataFrame(rows)
    result.to_csv(out / "real_mixture_runs.csv", index=False)

    aggregate_rows = []
    for (cap_db, snr_db), group in result.groupby(["cap_db", "target_snr_db"]):
        row = {
            "cap_db": float(cap_db),
            "target_snr_db": float(snr_db),
            "n": int(len(group)),
        }
        for metric in (
            "A_target_db",
            "A_protected_db",
            "SI_SDRi_protected_db",
            "SI_SDRi_target_db",
        ):
            stats = ci95(group[metric].tolist())
            for key, value in stats.items():
                if key != "n":
                    row[f"{metric}_{key}"] = value
        aggregate_rows.append(row)

    aggregate_df = pd.DataFrame(aggregate_rows).sort_values(
        ["cap_db", "target_snr_db"]
    )
    aggregate_df.to_csv(out / "real_mixture_aggregate.csv", index=False)

    primary = result[result["cap_db"] == 12.0]
    primary_summary = {
        metric: ci95(primary[metric].tolist())
        for metric in (
            "A_target_db",
            "A_protected_db",
            "SI_SDRi_protected_db",
            "SI_SDRi_target_db",
        )
    }
    summary = {
        "run_id": "M4-ORACLE-REAL-MIX-BATCH-001",
        "status": "oracle_ceiling_not_learned_model_performance",
        "n_mixtures": n,
        "n_rows": int(len(result)),
        "dataset_target": "UrbanSound8K/siren",
        "dataset_protected": str(speech_root),
        "background_classes": [
            "air_conditioner", "engine_idling", "street_music"
        ],
        "target_snr_db": list(target_snrs),
        "caps_db": list(caps),
        "background_relative_db": background_db,
        "seed": seed,
        "primary_cap_db": 12.0,
        "primary_cap_summary": primary_summary,
        "note": (
            "This experiment estimates an oracle ceiling using clean stems. "
            "It is not learned M4 performance and must be labeled 'techo oracle'."
        ),
        "artifacts": [
            "real_mixture_runs.csv",
            "real_mixture_aggregate.csv",
        ],
    }
    (out / "real_mixture_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def parse_float_list(value: str) -> tuple[float, ...]:
    return tuple(float(x.strip()) for x in value.split(",") if x.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--speech-root", required=True)
    ap.add_argument("--out", default="outputs/m4_real_mixture_oracle_batch")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--target-snrs", default="-5,0,5,10")
    ap.add_argument("--caps", default="12,18,24,30")
    ap.add_argument("--background-db", type=float, default=-10.0)
    args = ap.parse_args()
    run_batch(
        args.dataset_root,
        args.speech_root,
        args.out,
        n=args.n,
        seed=args.seed,
        target_snrs=parse_float_list(args.target_snrs),
        caps=parse_float_list(args.caps),
        background_db=args.background_db,
    )


if __name__ == "__main__":
    main()
