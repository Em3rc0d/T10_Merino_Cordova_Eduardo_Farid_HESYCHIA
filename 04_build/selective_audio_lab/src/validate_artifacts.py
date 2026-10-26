from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from evidence_store import EvidenceStore


class EvidenceValidationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _fail(message: str) -> None:
    raise EvidenceValidationError(message)


def validate_run(run_dir: str | Path, run_id: str = "PI8-DEMO-RUN-001") -> dict:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "artifacts_manifest.csv"
    summary_path = run_dir / "demo_summary.json"
    db_path = run_dir / "evidence.sqlite"

    for path in (manifest_path, summary_path, db_path):
        if not path.exists():
            _fail(f"missing evidence file: {path.name}")

    with manifest_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        _fail("artifact manifest is empty")

    required_columns = {"artifact", "kind", "path", "sha256"}
    if set(rows[0]) != required_columns:
        _fail(
            "artifact manifest columns mismatch: "
            f"expected {sorted(required_columns)}, found {sorted(rows[0])}"
        )

    seen_paths = set()
    manifest_map = {}
    for row in rows:
        rel = row["path"]
        if rel in seen_paths:
            _fail(f"duplicate artifact path in manifest: {rel}")
        seen_paths.add(rel)
        path = run_dir / rel
        if path.resolve().parent != run_dir.resolve():
            _fail("unsafe artifact path")
        if not path.exists():
            _fail(f"missing artifact: {path}")
        actual = sha256(path)
        if actual != row["sha256"]:
            _fail(f"checksum mismatch: {path}")
        manifest_map[rel] = {
            "kind": row["kind"],
            "checksum": row["sha256"],
        }

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("run_id") != run_id:
        _fail("run_id mismatch between requested run and demo_summary.json")

    store = EvidenceStore(db_path)
    try:
        snap = store.audit_snapshot(run_id)
    except KeyError:
        _fail("run_id missing from SQLite")

    if snap["run"]["status"] != "completed":
        _fail("run not completed in SQLite")

    db_artifacts = {
        item["path"]: {
            "kind": item["kind"],
            "checksum": item["checksum"],
        }
        for item in snap["artifacts"]
    }
    if db_artifacts != manifest_map:
        _fail("artifact manifest and SQLite artifact rows are not identical")

    summary_policy = summary.get("policy", {})
    if summary_policy.get("target_label") != snap["policy"]["target_label"]:
        _fail("policy target mismatch between summary and SQLite")
    if list(summary_policy.get("protected_set", [])) != list(
        snap["policy"]["protected_set"]
    ):
        _fail("protected_set mismatch between summary and SQLite")
    if summary_policy.get("decision") != snap["policy"]["decision"]:
        _fail("policy decision mismatch between summary and SQLite")
    if summary_policy.get("reason") != snap["policy"]["reason"]:
        _fail("policy reason mismatch between summary and SQLite")

    if summary.get("config") != snap["experiment"]["config"]:
        _fail("experiment config mismatch between summary and SQLite")

    model = summary.get("config", {}).get("model")
    if model:
        if snap["model"]["checksum"] != model["sha256"] or snap["model"]["format"] != model["format"]:
            _fail("checkpoint model mismatch between summary and SQLite")
        if model["checkpoint"] != "checkpoint.pt" or sha256(run_dir / "checkpoint.pt") != model["sha256"]:
            _fail("checkpoint SHA mismatch")
        if sha256(run_dir / "model_manifest.json") != model["manifest_sha256"]:
            _fail("model manifest SHA mismatch")
    if summary.get("config", {}).get("executed_engine") == "bypass" and snap["model"]["id"] != "POLICY-BYPASS":
        _fail("bypass must not claim a model was executed")

    summary_metrics = summary.get("metrics", {})
    expected_metrics = (
        "A_target_db",
        "A_protected_db",
        "SI_SDRi_protected_db",
        "wall_time_ms",
    )
    for name in expected_metrics:
        if name not in summary_metrics or name not in snap["metrics"]:
            _fail(f"metric missing from summary or SQLite: {name}")
        if not math.isclose(
            float(summary_metrics[name]),
            float(snap["metrics"][name]["value"]),
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            _fail(f"metric mismatch between summary and SQLite: {name}")

    required_assets = {
        "protected": "protected.wav",
        "target": "target.wav",
        "background": "background.wav",
    }
    assets_by_role = {item["role"]: item for item in snap["assets"]}
    if set(assets_by_role) != set(required_assets):
        _fail(
            "run_asset roles mismatch: "
            f"expected {sorted(required_assets)}, found {sorted(assets_by_role)}"
        )

    for role, filename in required_assets.items():
        asset = assets_by_role[role]
        manifest_item = manifest_map.get(filename)
        if not manifest_item:
            _fail(f"input audio missing from manifest: {filename}")
        if asset["path"] != filename:
            _fail(f"audio_asset path mismatch for role {role}")
        if asset["checksum"] != manifest_item["checksum"]:
            _fail(f"audio_asset checksum mismatch for role {role}")
        if not asset["asset_id"].endswith(asset["checksum"][:16]):
            _fail(f"audio_asset id does not bind checksum for role {role}")
        if int(asset["sr"]) != int(summary_metrics["sr"]):
            _fail(f"sample rate mismatch for role {role}")
        if not math.isclose(
            float(asset["duration_s"]),
            float(summary_metrics["duration_s"]),
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            _fail(f"duration mismatch for role {role}")

    return {
        "validated": True,
        "run_id": run_id,
        "artifact_count": len(rows),
        "asset_count": len(snap["assets"]),
        "policy": snap["policy"],
        "checksums": "ok",
        "sqlite": "coherent",
        "summary": "coherent",
        "input_assets": "bound_to_real_sha256",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="outputs/demo_run")
    ap.add_argument("--run-id", default="PI8-DEMO-RUN-001")
    args = ap.parse_args()
    result = validate_run(args.run_dir, args.run_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
