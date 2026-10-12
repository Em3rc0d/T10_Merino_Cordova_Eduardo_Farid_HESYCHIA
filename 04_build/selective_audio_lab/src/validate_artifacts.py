from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from evidence_store import EvidenceStore

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="outputs/demo_run")
    ap.add_argument("--run-id", default="PI8-DEMO-RUN-001")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)

    with (run_dir / "artifacts_manifest.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        path = run_dir / row["path"]
        if not path.exists():
            raise SystemExit(f"missing artifact: {path}")
        if sha256(path) != row["sha256"]:
            raise SystemExit(f"checksum mismatch: {path}")

    summary = json.loads((run_dir / "demo_summary.json").read_text(encoding="utf-8"))
    if summary["run_id"] != args.run_id:
        raise SystemExit("run_id mismatch")

    store = EvidenceStore(run_dir / "evidence.sqlite")
    db_summary = store.summary(args.run_id)
    if db_summary["status"] != "completed":
        raise SystemExit("run not completed in SQLite")
    if db_summary["artifact_count"] != len(rows):
        raise SystemExit("artifact count mismatch between SQLite and manifest")

    print(json.dumps({
        "validated": True,
        "run_id": args.run_id,
        "artifact_count": len(rows),
        "policy": db_summary["policy"],
        "checksums": "ok",
        "sqlite": "ok",
    }, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
