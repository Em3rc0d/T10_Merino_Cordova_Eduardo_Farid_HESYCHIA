from __future__ import annotations
import argparse
import json

from urbansound8k import validate_contract


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--allow-subset", action="store_true")
    args = ap.parse_args()

    report = validate_contract(
        args.dataset_root,
        require_official_shape=not args.allow_subset,
        verify_audio=True,
    )
    valid = bool(
        report.official_shape_ok
        and report.filename_metadata_consistency_ok
        and report.occurrence_fold_consistency_ok
        and report.missing_audio == 0
    )
    print(json.dumps({
        "valid": valid,
        "rows": report.rows,
        "folds": list(report.folds),
        "classes": list(report.classes),
        "missing_audio": report.missing_audio,
        "official_shape_ok": report.official_shape_ok,
        "filename_metadata_consistency_ok": report.filename_metadata_consistency_ok,
        "occurrence_fold_consistency_ok": report.occurrence_fold_consistency_ok,
        "cross_fold_occurrence_count": report.cross_fold_occurrence_count,
        "cross_fold_occurrence_sample": list(report.cross_fold_occurrence_sample),
        "cross_fold_fsid_count": report.cross_fold_fsid_count,
        "cross_fold_fsid_sample": list(report.cross_fold_fsid_sample),
        "cross_fold_fsid_cross_class_only": report.cross_fold_fsid_cross_class_only,
        "note": (
            "cross_fold_fsid_* is diagnostic only. UrbanSound8K v1.0 contains "
            "a small number of Freesound IDs assigned to different folds for "
            "different target classes; official folds are preserved. Blocking "
            "leakage is checked at labeled-occurrence level "
            "(fsID,classID,occurrenceID)."
        ),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
