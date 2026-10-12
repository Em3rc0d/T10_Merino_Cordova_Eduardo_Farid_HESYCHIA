from __future__ import annotations
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from semantic_features import extract_features
from urbansound8k import (
    EXPECTED_CLASSES,
    assert_no_leakage,
    audio_path,
    load_metadata,
    metadata_path,
    split_metadata,
    validate_contract,
)

def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def feature_cache_key(row) -> str:
    return f"fold{int(row.fold)}__{row.slice_file_name}.npy"

def build_matrix(root: Path, frame: pd.DataFrame, cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    xs, ys, files = [], [], []
    for row in frame.itertuples(index=False):
        cache = cache_dir / feature_cache_key(row)
        if cache.exists():
            feat = np.load(cache)
        else:
            wav = audio_path(root, int(row.fold), str(row.slice_file_name))
            feat = extract_features(wav)
            np.save(cache, feat)
        xs.append(feat)
        ys.append(int(row.classID))
        files.append(str(row.slice_file_name))
    return np.stack(xs), np.asarray(ys, dtype=np.int64), files

def make_models(seed: int):
    return {
        "svm_rbf": Pipeline([
            ("scale", StandardScaler()),
            ("model", SVC(C=10.0, gamma="scale", kernel="rbf")),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
    }

def metric_dict(y_true, y_pred):
    return {
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "macro_precision": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
    }

def run_benchmark(
    dataset_root: str | Path,
    out_dir: str | Path,
    *,
    seed: int = 42,
    require_official_shape: bool = True,
):
    root = Path(dataset_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = validate_contract(
        root,
        require_official_shape=require_official_shape,
        verify_audio=True,
    )
    df = load_metadata(root)
    train_df, val_df, test_df = split_metadata(df)
    assert_no_leakage(train_df, val_df, test_df)

    cache = out / "feature_cache"
    x_train, y_train, train_files = build_matrix(root, train_df, cache)
    x_val, y_val, val_files = build_matrix(root, val_df, cache)
    x_test, y_test, test_files = build_matrix(root, test_df, cache)

    validation_rows = []
    fitted = {}
    for name, model in make_models(seed).items():
        t0 = time.perf_counter()
        model.fit(x_train, y_train)
        train_s = time.perf_counter() - t0
        pred_val = model.predict(x_val)
        metrics = metric_dict(y_val, pred_val)
        validation_rows.append({"model": name, **metrics, "fit_seconds": train_s})
        fitted[name] = model

    validation_df = pd.DataFrame(validation_rows).sort_values(
        ["macro_f1", "macro_recall", "model"],
        ascending=[False, False, True],
    )
    selected = str(validation_df.iloc[0]["model"])

    # Freeze candidate after validation. Test fold 10 is evaluated once here.
    model = fitted[selected]
    pred_test = model.predict(x_test)
    test_metrics = metric_dict(y_test, pred_test)

    labels = sorted(EXPECTED_CLASSES)
    cm = confusion_matrix(y_test, pred_test, labels=labels)
    cm_df = pd.DataFrame(
        cm,
        index=[EXPECTED_CLASSES[i] for i in labels],
        columns=[EXPECTED_CLASSES[i] for i in labels],
    )

    predictions = pd.DataFrame({
        "slice_file_name": test_files,
        "y_true": y_test,
        "y_pred": pred_test,
        "true_class": [EXPECTED_CLASSES[int(x)] for x in y_test],
        "pred_class": [EXPECTED_CLASSES[int(x)] for x in pred_test],
        "fold": 10,
    })

    validation_path = out / "validation_models.csv"
    cm_path = out / "confusion_matrix_test_fold10.csv"
    predictions_path = out / "predictions_test_fold10.csv"
    model_path = out / f"{selected}_selected.joblib"

    validation_df.to_csv(validation_path, index=False)
    cm_df.to_csv(cm_path)
    predictions.to_csv(predictions_path, index=False)
    joblib.dump(model, model_path)

    fold_counts = {
        str(int(fold)): int(count)
        for fold, count in df.groupby("fold").size().sort_index().items()
    }
    split_counts = {
        "train": int(len(train_df)),
        "validation": int(len(val_df)),
        "test": int(len(test_df)),
    }
    metadata_file = metadata_path(root)
    manifest = {
        "source": {
            "metadata_path": str(metadata_file),
            "metadata_sha256": sha256_file(metadata_file),
            "dataset_rows": int(report.rows),
            "fold_counts": fold_counts,
            "split_counts": split_counts,
        },
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
            }
            for path in (
                validation_path,
                cm_path,
                predictions_path,
                model_path,
            )
        ],
    }
    (out / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "run_id": "M2-US8K-BASELINE-001",
        "dataset": "UrbanSound8K",
        "dataset_rows": report.rows,
        "fold_contract": {
            "train": [1,2,3,4,5,6,7,8],
            "validation": [9],
            "test": [10],
        },
        "split_counts": split_counts,
        "fold_counts": fold_counts,
        "metadata_sha256": manifest["source"]["metadata_sha256"],
        "no_leakage_check": "labeled_occurrence_passed",
        "dataset_integrity": {
            "official_shape_ok": report.official_shape_ok,
            "filename_metadata_consistency_ok": report.filename_metadata_consistency_ok,
            "occurrence_fold_consistency_ok": report.occurrence_fold_consistency_ok,
            "cross_fold_occurrence_count": report.cross_fold_occurrence_count,
            "cross_fold_fsid_count_diagnostic": report.cross_fold_fsid_count,
            "cross_fold_fsid_cross_class_only": report.cross_fold_fsid_cross_class_only,
        },
        "feature_contract": {
            "sample_rate_hz": 16000,
            "duration_s": 4.0,
            "mfcc": 20,
            "logmel_bins": 64,
            "summary": "mean+std",
        },
        "selection_rule": "max validation Macro-F1, then Macro-Recall; test not used for selection",
        "selected_model": selected,
        "validation": validation_df.to_dict(orient="records"),
        "test": test_metrics,
        "rnf03_target_macro_f1": 0.85,
        "rnf03_met": bool(test_metrics["macro_f1"] >= 0.85),
        "selected_model_sha256": sha256_file(model_path),
        "benchmark_manifest": "benchmark_manifest.json",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "protocol_note": (
            "The thesis uses a fixed holdout protocol: folds 1-8 train, 9 validation, "
            "10 final test. Results must not be presented as directly comparable to "
            "published evaluations that use 10-fold cross-validation. Official folds "
            "are preserved. Leakage blocking is performed at labeled-occurrence level "
            "(fsID,classID,occurrenceID); cross-fold fsID reuse across different target "
            "classes is retained as a dataset diagnostic rather than 'fixed' by reshuffling."
        ),
        "note": (
            "This is a semantic recognition baseline (M2). "
            "It does not localize time-frequency bins and does not control M4 automatically."
        ),
    }
    (out / "semantic_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--out", default="outputs/m2_urbansound8k")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--allow-subset",
        action="store_true",
        help="For tests/fixtures only. Real thesis run must use the full official dataset.",
    )
    args = ap.parse_args()
    summary = run_benchmark(
        args.dataset_root,
        args.out,
        seed=args.seed,
        require_official_shape=not args.allow_subset,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
