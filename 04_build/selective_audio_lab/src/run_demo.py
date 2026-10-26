from __future__ import annotations

import argparse
import hashlib
import json
import time
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import soundfile as sf

from audio_core import SR, N_FFT, HOP, stft_complex, synthesize, synthesize_drilling
from attenuation import apply_selective_attenuation
from evidence_store import EvidenceStore
from policy import DEMO_TARGETS, POLICY_VERSION, resolve_policy

RUN_ID = "S10A-DEMO-RUN-001"


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


def _save_mask_figure(out, mask):
    path = out / "mask.png"
    fig, ax = plt.subplots(figsize=(10, 3))
    im = ax.imshow(mask, origin="lower", aspect="auto", vmin=0, vmax=1,
                   extent=[0, 4, 0, SR / 2])
    ax.set(xlabel="Tiempo (s)", ylabel="Frecuencia (Hz)", title="Máscara del motor ejecutado; BLOCK = placeholder cero")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def run_demo(
    out_dir: str | Path = "outputs/s10a_demo_run",
    *,
    seed: int = 42,
    target_label: str = "drilling_synthetic",
    protected: list[str] | tuple[str, ...] = ("speech_like_synthetic",),
    cap_db: float = 12.0,
    alpha: float = 1.0,
    run_id: str = RUN_ID,
    engine: str = "oracle",
    model_root=None,
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if target_label not in DEMO_TARGETS:
        raise ValueError("Only explicit synthetic demo targets are supported")
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
    if engine not in ("oracle", "cnn_experimental"):
        raise ValueError("Unsupported mask engine")
    predictor, model_info = None, None
    if engine == "cnn_experimental" and policy.decision == "ALLOW":
        from m4_experimental import ExperimentalPredictor, MODEL_ROOT
        predictor = ExperimentalPredictor(model_root or MODEL_ROOT)
        model_info = predictor.info
    generator = synthesize_drilling if target_label == "drilling_synthetic" else synthesize
    protected_audio, target, background = generator(seed)

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
        engine=engine,
        predictor=predictor.predict if predictor else None,
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

    mask_path = out / ("mask_predicted.npy" if engine == "cnn_experimental" else "mask_irm.npy")
    gain_path = out / "gain.npy"
    np.save(mask_path, mask)
    np.save(gain_path, gain)
    _register_artifact(artifact_rows, mask_path, "mask")
    _register_artifact(artifact_rows, gain_path, "mask")

    for figure_path in _save_real_figures(out, mixture, output):
        _register_artifact(artifact_rows, figure_path, "report")
    _register_artifact(artifact_rows, _save_mask_figure(out, mask), "report")

    if model_info:
        # Every run is self-contained even when the installed model later changes.
        for name in ("checkpoint.pt", "model_manifest.json", "training_history.json", "training_sources.json"):
            dest = out / name
            shutil.copyfile(predictor.root / name, dest)
            _register_artifact(artifact_rows, dest, "model" if name == "checkpoint.pt" else "config")
        from m4_experimental import inspect_model
        copied = inspect_model(out)
        if not copied["ready"] or copied["checkpoint_sha256"] != model_info["checkpoint_sha256"]:
            raise ValueError("Checkpoint snapshot is inconsistent")

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
        "baseline": metrics["baseline_type"],
        "requested_engine": engine,
        "executed_engine": metrics["executed_engine"],
        "model": ({"id": model_info["model_id"], "format": "pytorch",
                   "sha256": model_info["checkpoint_sha256"],
                   "manifest_sha256": model_info["manifest_sha256"],
                   "checkpoint": "checkpoint.pt", "status": "candidate"} if model_info else None),
        "measurement_scope": "offline_synthetic_engineering_demo_not_scientific_validation",
        "wall_time_scope": "DSP_and_inference_excludes_model_load_and_artifact_IO_not_E2E",
        "mask_role": "bypass_placeholder" if policy.decision == "BLOCK" else "learned" if model_info else "oracle_privileged",
        "safety_policy_version": POLICY_VERSION,
        "source_scope": "synthetic_procedural_fixture_only",
    }
    policy_dict = {
        "target_label": policy.target_label,
        "protected_set": list(policy.protected_set),
        "cap_db": policy.cap_db,
        "decision": policy.decision,
        "reason": policy.reason,
        "version": POLICY_VERSION,
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
        "warning": "Procedural synthetic engineering demo. Oracle uses stems; CNN uses mixture+target only. Protected surrogate is NOT intelligible speech; no scientific RNF-04 evidence or streaming.",
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
    ap.add_argument("--out", default="outputs/s10a_demo_run")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--target-label", default="drilling_synthetic")
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
