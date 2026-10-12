from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from audio_core import SR, N_FFT, HOP, synthesize
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/demo_run")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--target-label", default="siren_synthetic")
    ap.add_argument("--protected", nargs="*", default=["speech_like_synthetic"])
    ap.add_argument("--cap-db", type=float, default=12.0)
    ap.add_argument("--alpha", type=float, default=1.0)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    policy = resolve_policy(args.target_label, args.protected, args.cap_db)
    protected, target, background = synthesize(args.seed)

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
        protected,
        target,
        background,
        policy=policy,
        alpha=args.alpha,
    )
    metrics["wall_time_ms"] = float((time.perf_counter() - start) * 1000)

    audio_paths = {
        "protected.wav": p,
        "target.wav": tg,
        "background.wav": bg,
        "mixture.wav": mixture,
        "output_selective.wav": output,
    }

    artifact_rows: list[dict] = []
    for name, data in audio_paths.items():
        path = out / name
        sf.write(path, data, SR)
        artifact_rows.append(
            {
                "artifact": name,
                "kind": "audio",
                "path": path.name,
                "sha256": sha256(path),
            }
        )

    np.save(out / "mask_irm.npy", mask)
    artifact_rows.append(
        {
            "artifact": "mask_irm.npy",
            "kind": "mask",
            "path": "mask_irm.npy",
            "sha256": sha256(out / "mask_irm.npy"),
        }
    )
    np.save(out / "gain.npy", gain)
    artifact_rows.append(
        {
            "artifact": "gain.npy",
            "kind": "mask",
            "path": "gain.npy",
            "sha256": sha256(out / "gain.npy"),
        }
    )

    pd.DataFrame([metrics]).to_csv(out / "demo_metrics.csv", index=False)
    pd.DataFrame(artifact_rows).to_csv(out / "artifacts_manifest.csv", index=False)

    config = {
        "seed": args.seed,
        "sr": SR,
        "n_fft": N_FFT,
        "hop": HOP,
        "target_label": args.target_label,
        "protected_set": list(policy.protected_set),
        "cap_db": args.cap_db,
        "alpha": args.alpha,
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
        run_id=RUN_ID,
        seed=args.seed,
        metrics=metrics,
        artifacts=artifact_rows,
        policy=policy_dict,
        config=config,
    )
    db_summary = store.summary(RUN_ID)

    summary = {
        "run_id": RUN_ID,
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

    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
