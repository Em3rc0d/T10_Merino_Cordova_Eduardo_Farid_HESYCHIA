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
    print(json.dumps({
        "valid": True,
        "rows": report.rows,
        "folds": list(report.folds),
        "classes": list(report.classes),
        "missing_audio": report.missing_audio,
        "official_shape_ok": report.official_shape_ok,
    }, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
