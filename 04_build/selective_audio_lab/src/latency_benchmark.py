from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from audio_core import DURATION, synthesize
from attenuation import apply_selective_attenuation
from policy import resolve_policy

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/latency")
    ap.add_argument("--runs", type=int, default=40)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    policy = resolve_policy(
        "siren_synthetic",
        ["speech_like_synthetic"],
        12.0,
    )

    latencies = []
    for i in range(args.runs):
        p, t, b = synthesize(seed=42 + i)
        t0 = time.perf_counter()
        apply_selective_attenuation(p, t, b, policy=policy)
        latencies.append((time.perf_counter() - t0) * 1000)

    arr = np.array(latencies)
    summary = {
        "runs": args.runs,
        "environment": "local_python_runtime_container_reference",
        "audio_duration_s": DURATION,
        "processing_p50_ms": float(np.percentile(arr, 50)),
        "processing_p95_ms": float(np.percentile(arr, 95)),
        "processing_mean_ms": float(np.mean(arr)),
        "realtime_factor_mean": float(np.mean(arr) / (DURATION * 1000)),
        "measurement_scope": "whole_clip_processing_only",
        "note": (
            "Esta medición corresponde al procesamiento local del clip completo. "
            "No equivale a p95 por hop, E2E de captura/salida ni perfil Android."
        ),
    }

    pd.DataFrame(
        {"run": list(range(args.runs)), "elapsed_ms": latencies}
    ).to_csv(out / "latency_samples.csv", index=False)

    (out / "latency_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
