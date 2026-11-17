#!/usr/bin/env python3
"""Measured M4 CNN forward-pass-only benchmark, with a real pinned checkpoint.

The input is deterministic artificial audio; this never opens a thesis test split.
Chunks use real historical context in an offline feature sequence and output only
new frames. This is NOT physical streaming, STFT+iSTFT E2E or capture latency.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch


def physical_memory_bytes():
    try:
        import psutil
        return int(psutil.virtual_memory().total)
    except Exception:
        try:
            return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
        except Exception:
            return None


def peak_rss_bytes():
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)
    except Exception:
        return None


def hashfile(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fixture(sr, seconds, seed, device):
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * seconds), dtype=np.float32) / sr
    x = (
        0.045 * np.sin(2 * np.pi * 470 * t)
        + 0.03 * np.sin(2 * np.pi * 940 * t)
        + 0.008 * rng.normal(size=t.shape)
    ).astype("float32")
    return torch.from_numpy(x).to(device)


def benchmark(
    checkpoint: Path,
    model_src: Path,
    out: Path,
    *,
    seed=20261108,
    runs=100,
    warmup=8,
    hops=16,
    seconds=2.0,
    device="cpu",
    threads=4,
    min_samples=1,
    device_label="unlabeled_host",
):
    if runs < 5 or warmup < 1 or hops < 1 or seconds <= 0.05 or min_samples < 1:
        raise ValueError("Invalid benchmark configuration")
    if device not in ("cpu", "cuda"):
        raise ValueError("Only cpu/cuda are supported")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    if not checkpoint.is_file() or not model_src.is_dir():
        raise FileNotFoundError("Checkpoint/model-src missing")
    if device == "cpu":
        torch.set_num_threads(threads)

    sys.path.insert(0, str(model_src.resolve()))
    from m4_scientific.model import (
        HOP,
        SR,
        features,
        frontend_contract,
        load_checkpoint,
        spectrum,
    )

    model, _ = load_checkpoint(checkpoint)
    model = model.to(device).eval()
    label = torch.tensor([0], device=device, dtype=torch.long)
    sig = fixture(SR, seconds, seed, device)

    with torch.inference_mode():
        feature_seq = features(spectrum(sig))[0]

    left = max(0, int(model.receptive_frames) - 1)
    blocks = []
    for end in range(hops, feature_seq.shape[0] + hops, hops):
        hi = min(end, feature_seq.shape[0])
        lo = max(0, hi - hops - left)
        if hi <= lo:
            continue
        n_new = hi - (end - hops)
        if n_new <= 0:
            continue
        blocks.append((lo, hi, n_new, feature_seq[lo:hi][None].contiguous()))
    if not blocks:
        raise ValueError("Insufficient frames for a single block")

    sync = (lambda: torch.cuda.synchronize()) if device == "cuda" else (lambda: None)
    samples = []
    for run in range(warmup + runs):
        for block_index, (lo, hi, n_new, inp) in enumerate(blocks):
            sync()
            t0 = time.perf_counter_ns()
            with torch.inference_mode():
                mask = model(inp, label)[:, -n_new:]
                gain = model.gain(mask)
                if not bool(torch.isfinite(gain).all()):
                    raise ValueError("Non-finite output")
            sync()
            elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
            if run >= warmup:
                samples.append(
                    {
                        "run_id": run - warmup,
                        "block_index": block_index,
                        "input_context_frames": hi - lo,
                        "output_frames": n_new,
                        "m4_ms": elapsed_ms,
                        "chunk_duration_ms": n_new * HOP / SR * 1000,
                    }
                )

    if len(samples) < min_samples:
        raise ValueError(
            f"Benchmark produced {len(samples)} timed blocks; "
            f"at least {min_samples} are required"
        )

    elapsed = np.array([row["m4_ms"] for row in samples], dtype=float)
    duration = np.array([row["chunk_duration_ms"] for row in samples], dtype=float)

    out.mkdir(parents=True, exist_ok=True)
    csv_file = out / "m4_forward_samples.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)

    report = {
        "schema": "hesychia.pi14-m4-forward-only.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": hashfile(checkpoint),
        "checkpoint_file": str(checkpoint.resolve()),
        "source_file": str((model_src / "m4_scientific" / "model.py").resolve()),
        "script_sha256": hashfile(Path(__file__)),
        "frontend": frontend_contract(),
        "model_type": type(model).__name__,
        "torch_version": torch.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpus_visible": os.cpu_count(),
        "cpu_model": platform.processor() or None,
        "physical_memory_bytes": physical_memory_bytes(),
        "peak_process_rss_bytes": peak_rss_bytes(),
        "device": device,
        "device_label": device_label,
        "threads": threads,
        "seed": seed,
        "runs": runs,
        "warmup_runs": warmup,
        "block_count": len(blocks),
        "min_timed_blocks": min_samples,
        "receptive_frames": int(model.receptive_frames),
        "block_hops": hops,
        "input_audio_seconds": float(seconds),
        "signal": "synthetic deterministic mixed tones+Gaussian noise; NOT test audio",
        "block_ms": {
            "p50": float(np.percentile(elapsed, 50)),
            "p95": float(np.percentile(elapsed, 95)),
            "p99": float(np.percentile(elapsed, 99)),
            "mean": float(elapsed.mean()),
        },
        "model_only_rtf": float(elapsed.sum() / duration.sum()),
        "samples": int(len(samples)),
        "source": "real checkpoint loaded; synthetic features of a fixed offline audio signal",
        "measurement_scope": (
            "M4 forward+gain on offline chunks with historical context; "
            "no STFT/feature or iSTFT processing in timed interval"
        ),
        "warnings": [
            "Does not demonstrate real-time audio capture/output, physical streaming or E2E latency",
            "Inputs are precomputed from an offline clip; does not measure streaming FFT/buffering",
            "Repeated chunks are dependent; percentiles describe repeated-run timing, not independent scenes",
            "Model-only RTF<1 is not sufficient to claim realtime system",
            "Runner results do not replace the final Acer Nitro 5 benchmark required by OE3",
        ],
    }
    (out / "m4_forward_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--model-src", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--hops", type=int, default=16)
    parser.add_argument("--seconds", type=float, default=2)
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--min-samples", type=int, default=1000)
    parser.add_argument("--device-label", default="unlabeled_host")
    args = parser.parse_args()

    report = benchmark(
        args.checkpoint,
        args.model_src,
        args.out,
        seed=args.seed,
        runs=args.runs,
        warmup=args.warmup,
        hops=args.hops,
        seconds=args.seconds,
        device=args.device,
        threads=args.threads,
        min_samples=args.min_samples,
        device_label=args.device_label,
    )
    print(
        json.dumps(
            {
                "checkpoint_sha256": report["checkpoint_sha256"],
                "scope": report["measurement_scope"],
                "block_ms": report["block_ms"],
                "model_only_rtf": report["model_only_rtf"],
                "samples": report["samples"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
