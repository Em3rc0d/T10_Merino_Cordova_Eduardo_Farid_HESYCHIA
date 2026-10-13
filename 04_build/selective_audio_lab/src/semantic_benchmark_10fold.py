from __future__ import annotations
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from semantic_benchmark import (
    build_matrix,
    make_models,
    metric_dict,
)
from semantic_features import RESAMPLE_TYPE
from urbansound8k import load_metadata, validate_contract


def mean_sd_ci95(values: list[float]) -> dict:
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


def run_cv(dataset_root: str | Path, out_dir: str | Path, seed: int = 42):
    root = Path(dataset_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    validate_contract(root, require_official_shape=True, verify_audio=True)
    df = load_metadata(root)

    cache = out / f"feature_cache_v2_sr16000_{RESAMPLE_TYPE}"
    all_x, all_y, all_files, all_folds = [], [], [], []
    for fold in range(1, 11):
        frame = df[df["fold"] == fold].copy()
        x, y, files = build_matrix(
            root, frame, cache, split_name=f"fold{fold}"
        )
        all_x.append(x)
        all_y.append(y)
        all_files.extend(files)
        all_folds.extend([fold] * len(frame))
    X = np.concatenate(all_x, axis=0)
    y = np.concatenate(all_y, axis=0)
    folds = np.asarray(all_folds, dtype=np.int64)

    rows = []
    for model_name in ("svm_rbf", "random_forest"):
        for test_fold in range(1, 11):
            train_idx = folds != test_fold
            test_idx = folds == test_fold
            model = make_models(seed)[model_name]
            t0 = time.perf_counter()
            model.fit(X[train_idx], y[train_idx])
            fit_seconds = time.perf_counter() - t0
            pred = model.predict(X[test_idx])
            rows.append({
                "model": model_name,
                "test_fold": test_fold,
                "n_train": int(train_idx.sum()),
                "n_test": int(test_idx.sum()),
                **metric_dict(y[test_idx], pred),
                "fit_seconds": float(fit_seconds),
            })
            print(
                f"[10fold] {model_name} fold={test_fold} "
                f"Macro-F1={rows[-1]['macro_f1']:.4f}",
                flush=True,
            )

    fold_df = pd.DataFrame(rows)
    fold_df.to_csv(out / "m2_10fold_per_fold.csv", index=False)

    aggregate = {}
    for model_name, group in fold_df.groupby("model"):
        aggregate[model_name] = {
            metric: mean_sd_ci95(group[metric].tolist())
            for metric in (
                "macro_f1",
                "macro_recall",
                "macro_precision",
                "accuracy",
            )
        }

    summary = {
        "run_id": "M2-US8K-10FOLD-COMPARABILITY-001",
        "dataset": "UrbanSound8K",
        "protocol": (
            "Official predefined folds used as 10 held-out folds. "
            "Model hyperparameters are fixed before this run; no fold is used "
            "for tuning. This is a secondary comparability benchmark and does "
            "not replace the frozen 1-8/9/10 RNF-03 result."
        ),
        "seed": seed,
        "models": aggregate,
        "artifact": "m2_10fold_per_fold.csv",
    }
    (out / "m2_10fold_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--out", default="outputs/m2_10fold")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    run_cv(args.dataset_root, args.out, seed=args.seed)


if __name__ == "__main__":
    main()
