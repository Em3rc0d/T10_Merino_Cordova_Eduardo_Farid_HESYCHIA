from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from audio_core import DURATION, synthesize
from attenuation import apply_selective_attenuation
from policy import resolve_policy


def run_latency_benchmark(
    out_dir: str | Path = "outputs/latency",
    *,
    runs: int = 40,
    seed: int = 42,
    device_label: str | None = None,
) -> dict:
    if not isinstance(runs, int) or isinstance(runs, bool) or not 5 <= runs <= 500:
        raise ValueError("runs must be an integer within [5, 500]")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer within [0, 2^32-1]")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    policy = resolve_policy(
        "siren_synthetic",
        ["speech_like_synthetic"],
        12.0,
    )

    latencies = []
    for i in range(runs):
        p, t, b = synthesize(seed=seed + i)
        t0 = time.perf_counter()
        apply_selective_attenuation(p, t, b, policy=policy)
        latencies.append((time.perf_counter() - t0) * 1000)

    arr = np.array(latencies, dtype=np.float64)
    label = (device_label or os.environ.get("HESYCHIA_DEVICE_LABEL") or "unlabeled_host").strip()
    summary = {
        "runs": runs,
        "seed": seed,
        "device_label": label,
        "runtime_context": "docker_or_local_python_process_on_host_cpu",
        "python": platform.python_version(),
        "machine": platform.machine(),
        "logical_cpus_visible": os.cpu_count(),
        "audio_duration_s": DURATION,
        "processing_p50_ms": float(np.percentile(arr, 50)),
        "processing_p95_ms": float(np.percentile(arr, 95)),
        "processing_mean_ms": float(np.mean(arr)),
        "realtime_factor_mean": float(np.mean(arr) / (DURATION * 1000)),
        "measurement_scope": "whole_clip_processing_only",
        "note": (
            "Esta medición corresponde al procesamiento local del clip completo "
            "en el host que ejecuta este proceso/contenedor. No equivale a p95 por hop, "
            "E2E de captura/salida ni perfil Android."
        ),
    }

    pd.DataFrame(
        {"run": list(range(runs)), "elapsed_ms": latencies}
    ).to_csv(out / "latency_samples.csv", index=False)

    (out / "latency_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/latency")
    ap.add_argument("--runs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device-label", default=None)
    args = ap.parse_args()

    summary = run_latency_benchmark(
        args.out,
        runs=args.runs,
        seed=args.seed,
        device_label=args.device_label,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
