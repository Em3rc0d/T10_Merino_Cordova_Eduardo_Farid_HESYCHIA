from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soundfile as sf

from audio_core import SR, N_FFT, HOP, stft_complex, synthesize
from attenuation import apply_selective_attenuation
from evidence_store import EvidenceStore
from policy import resolve_policy

RUN_ID = "PI8-DEMO-RUN-001"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _register_artifact(rows: list[dict], path: Path, kind: str) -> None:
    rows.append(
        {
            "artifact": path.name,
            "kind": kind,
            "path": path.name,
            "sha256": sha256(path),
        }
    )


def _save_real_figures(out: Path, mixture: np.ndarray, output: np.ndarray) -> list[Path]:
    """Generate figures exclusively from the current run audio."""
    time_axis = np.arange(len(mixture)) / SR

    waveform_path = out / "waveform_comparison.png"
    fig, axes = plt.subplots(2, 1, figsize=(11, 4.8), sharex=True)
    axes[0].plot(time_axis, mixture, linewidth=0.7)
    axes[0].set_title("Mezcla de entrada")
    axes[0].set_ylabel("Amplitud")
    axes[0].grid(alpha=0.2)
    axes[1].plot(time_axis, output, linewidth=0.7)
    axes[1].set_title("Salida con atenuación selectiva")
    axes[1].set_xlabel("Tiempo (s)")
    axes[1].set_ylabel("Amplitud")
    axes[1].grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(waveform_path, dpi=150)
    plt.close(fig)

    spec_path = out / "spectrogram_comparison.png"
    mix_db = 20 * np.log10(np.abs(stft_complex(mixture)) + 1e-8)
    out_db = 20 * np.log10(np.abs(stft_complex(output)) + 1e-8)
    vmax = float(max(mix_db.max(), out_db.max()))
    vmin = vmax - 80.0
    extent = [0.0, len(mixture) / SR, 0.0, SR / 2.0]

    fig, axes = plt.subplots(2, 1, figsize=(11, 5.4), sharex=True)
    axes[0].imshow(
        mix_db,
        origin="lower",
        aspect="auto",
        extent=extent,
        vmin=vmin,
        vmax=vmax,
    )
    axes[0].set_title("Espectrograma · mezcla")
    axes[0].set_ylabel("Frecuencia (Hz)")
    axes[1].imshow(
        out_db,
        origin="lower",
        aspect="auto",
        extent=extent,
        vmin=vmin,
        vmax=vmax,
    )
    axes[1].set_title("Espectrograma · salida")
    axes[1].set_xlabel("Tiempo (s)")
    axes[1].set_ylabel("Frecuencia (Hz)")
    fig.tight_layout()
    fig.savefig(spec_path, dpi=150)
    plt.close(fig)

    return [waveform_path, spec_path]


def run_demo(
    out_dir: str | Path = "outputs/demo_run",
    *,
    seed: int = 42,
    target_label: str = "siren_synthetic",
    protected: list[str] | tuple[str, ...] = ("speech_like_synthetic",),
    cap_db: float = 12.0,
    alpha: float = 1.0,
    run_id: str = RUN_ID,
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if target_label != "siren_synthetic":
        raise ValueError(
            "The current controlled generator only supports target_label='siren_synthetic'."
        )
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer within [0, 2^32-1]")
    if not np.isfinite(cap_db) or not 0.0 <= cap_db <= 120.0:
        raise ValueError("cap_db must be finite and within [0, 120]")
    if not np.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be finite and between 0 and 1")
    protected = tuple(str(x).strip() for x in protected if str(x).strip())
    if not protected:
        raise ValueError("protected set must not be empty")

    policy = resolve_policy(target_label, protected, cap_db)
    protected_audio, target, background = synthesize(seed)

    start = time.perf_counter()
    (
        mixture,
        output,
        p,
        tg,
        bg,
        mask,
        gain,
        metrics,
    ) = apply_selective_attenuation(
        protected_audio,
        target,
        background,
        policy=policy,
        alpha=alpha,
    )
    metrics["wall_time_ms"] = float((time.perf_counter() - start) * 1000)

    artifact_rows: list[dict] = []
    audio_paths = {
        "protected.wav": p,
        "target.wav": tg,
        "background.wav": bg,
        "mixture.wav": mixture,
        "output_selective.wav": output,
    }
    for name, data in audio_paths.items():
        path = out / name
        sf.write(path, data, SR)
        _register_artifact(artifact_rows, path, "audio")

    mask_path = out / "mask_irm.npy"
    gain_path = out / "gain.npy"
    np.save(mask_path, mask)
    np.save(gain_path, gain)
    _register_artifact(artifact_rows, mask_path, "mask")
    _register_artifact(artifact_rows, gain_path, "mask")

    for figure_path in _save_real_figures(out, mixture, output):
        _register_artifact(artifact_rows, figure_path, "report")

    pd.DataFrame([metrics]).to_csv(out / "demo_metrics.csv", index=False)
    pd.DataFrame(artifact_rows).to_csv(out / "artifacts_manifest.csv", index=False)

    config = {
        "seed": seed,
        "sr": SR,
        "n_fft": N_FFT,
        "hop": HOP,
        "target_label": target_label,
        "protected_set": list(policy.protected_set),
        "cap_db": cap_db,
        "alpha": alpha,
        "baseline": "oracle_IRM_stem_demo",
    }
    policy_dict = {
        "target_label": policy.target_label,
        "protected_set": list(policy.protected_set),
        "cap_db": policy.cap_db,
        "decision": policy.decision,
        "reason": policy.reason,
    }

    store = EvidenceStore(out / "evidence.sqlite")
    store.persist_demo(
        run_id=run_id,
        seed=seed,
        metrics=metrics,
        artifacts=artifact_rows,
        policy=policy_dict,
        config=config,
    )
    db_summary = store.summary(run_id)

    summary = {
        "run_id": run_id,
        "scope": "incremento_funcional_local_reproducible",
        "warning": "No clinical claim. Synthetic/stem-controlled demo only.",
        "config": config,
        "policy": policy_dict,
        "metrics": metrics,
        "artifacts": artifact_rows,
        "evidence_store": {
            "path": "evidence.sqlite",
            "status": db_summary["status"],
            "artifact_count": db_summary["artifact_count"],
        },
    }
    (out / "demo_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/demo_run")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--target-label", default="siren_synthetic")
    ap.add_argument("--protected", nargs="*", default=["speech_like_synthetic"])
    ap.add_argument("--cap-db", type=float, default=12.0)
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--run-id", default=RUN_ID)
    args = ap.parse_args()

    summary = run_demo(
        args.out,
        seed=args.seed,
        target_label=args.target_label,
        protected=args.protected,
        cap_db=args.cap_db,
        alpha=args.alpha,
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
