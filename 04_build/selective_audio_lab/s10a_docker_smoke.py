"""Run the S10-A HTTP smoke against the *running* Docker console.

    docker compose exec -T hesychia python s10a_docker_smoke.py

Uses the real API, generates runs and checks persisted artifacts. Requires no
extra packages beyond the existing Docker runtime. Does not validate M4/RNF-04.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from urllib import error, parse, request


def call(base: str, route: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        base + route,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def fetch_bytes(base: str, route: str) -> bytes:
    with request.urlopen(base + route, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {route}")
        return response.read()


def run_job(base: str, target: str, timeout: float) -> dict:
    code, accepted = call(
        base,
        "/api/jobs/attenuate",
        {"target_label": target, "seed": 42, "cap_db": 12, "alpha": 1.0,
         "protect_target": False},
    )
    assert code == 202, f"Unable to start {target}: {code} {accepted}"
    job_id = parse.quote(accepted["jobId"], safe="")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_code, job = call(base, "/api/jobs/" + job_id)
        assert status_code == 200, f"Missing job: {job}"
        if job["status"] == "completed":
            code, result = call(base, job["resultRef"])
            assert code == 200, f"Missing run: {result}"
            return result
        if job["status"] == "failed":
            raise RuntimeError(f"{target} job failed: {job.get('error')}")
        time.sleep(0.5)
    raise TimeoutError(f"{target} job timed out after {timeout} seconds")


def verify_evidence(base: str, run: dict) -> None:
    run_id = parse.quote(run["run_id"], safe="")
    code, integrity = call(base, "/api/runs/" + run_id + "/integrity")
    assert code == 200 and integrity.get("validated") is True, (
        f"Run integrity invalid: {code} {integrity}"
    )
    assert integrity.get("checksums") == "ok"
    assert integrity.get("sqlite") == "coherent"
    print(f"PASS evidence: {run['run_id']}, hashes/SQLite verified")


def smoke(base: str, timeout: float) -> None:
    code, health = call(base, "/api/health")
    assert code == 200 and health.get("status") == "ok", (
        f"Server unavailable: {code} {health}"
    )
    print("PASS health")

    code, bad = call(base, "/api/jobs/attenuate", {"target_label": "unknown"})
    assert code == 400 and bad.get("error") == "invalid_parameters", (
        f"Unknown targets should be rejected: {code} {bad}"
    )
    print("PASS unknown-target rejection")

    allowed = run_job(base, "drilling_synthetic", timeout)
    assert allowed["policy"]["decision"] == "ALLOW"
    assert allowed["config"]["target_label"] == "drilling_synthetic"
    assert allowed["config"]["baseline"] == "oracle_IRM_stem_demo"
    assert allowed["config"]["safety_policy_version"] == "S10A-1.0"
    assert allowed["config"]["source_scope"] == "synthetic_procedural_fixture_only"
    assert math.isfinite(float(allowed["metrics"]["A_target_db"]))
    verify_evidence(base, allowed)
    print("PASS drilling ALLOW / oracle (not learned M4)")

    blocked = run_job(base, "siren_synthetic", timeout)
    assert blocked["policy"]["decision"] == "BLOCK"
    assert blocked["policy"]["reason"] == "mandatory_protected_signal"
    assert blocked["config"]["safety_policy_version"] == "S10A-1.0"
    verify_evidence(base, blocked)
    mix = fetch_bytes(base, blocked["audio"]["mixture"])
    out = fetch_bytes(base, blocked["audio"]["output"])
    assert mix == out, "Blocked WAV differs from mixture WAV"
    print("PASS siren BLOCK / identical WAV bytes")

    # Ensure the two scenarios are distinct, not just relabeled audio.
    drill_wav = fetch_bytes(base, allowed["audio"]["target"])
    siren_wav = fetch_bytes(base, blocked["audio"]["target"])
    assert hashlib.sha256(drill_wav).digest() != hashlib.sha256(siren_wav).digest()
    print("PASS distinct synthetic targets")
    print("S10A DOCKER SMOKE: PASS")
    print("Note: synthetic/oracle demo; not scientific M4 or clinical validation.")


def main() -> int:
    parser = argparse.ArgumentParser(description="S10-A running-console smoke")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=float, default=150)
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("--timeout must be in (0, 600]")
    try:
        smoke(args.url.rstrip("/"), args.timeout)
    except (AssertionError, RuntimeError, TimeoutError, OSError, ValueError,
            KeyError, TypeError) as exc:
        print(f"S10A DOCKER SMOKE: FAIL - {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
