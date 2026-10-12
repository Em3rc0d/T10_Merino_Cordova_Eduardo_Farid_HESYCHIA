from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from run_demo import run_demo
from semantic_benchmark import run_benchmark
from urbansound8k import validate_contract

LAB_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = LAB_ROOT / "web"
DEFAULT_OUTPUT_ROOT = Path(
    os.environ.get("HESYCHIA_OUTPUT_ROOT", LAB_ROOT / "outputs" / "web")
)
DEFAULT_DATASET_ROOT = Path(
    os.environ.get("URBANSOUND8K_ROOT", "/data/UrbanSound8K")
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, worker) -> dict:
        job_id = f"{kind.upper()}-{uuid.uuid4().hex[:10]}"
        job = {
            "jobId": job_id,
            "kind": kind,
            "status": "queued",
            "createdAt": utc_now(),
            "startedAt": None,
            "endedAt": None,
            "resultRef": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job

        def runner():
            with self._lock:
                job["status"] = "running"
                job["startedAt"] = utc_now()
            try:
                result, result_ref = worker(job_id)
                with self._lock:
                    job["status"] = "completed"
                    job["result"] = result
                    job["resultRef"] = result_ref
                    job["endedAt"] = utc_now()
            except Exception as exc:
                with self._lock:
                    job["status"] = "failed"
                    job["error"] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "trace": traceback.format_exc(limit=8),
                    }
                    job["endedAt"] = utc_now()

        threading.Thread(target=runner, daemon=True).start()
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list(self) -> list[dict]:
        with self._lock:
            return [dict(v) for v in reversed(list(self._jobs.values()))]


def _safe_child(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("unsafe path")
    return candidate


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_demo_runs(output_root: Path) -> list[dict]:
    if not output_root.exists():
        return []
    rows = []
    for summary_path in output_root.glob("*/demo_summary.json"):
        try:
            summary = _load_json(summary_path)
            metrics = summary.get("metrics", {})
            policy = summary.get("policy", {})
            rows.append(
                {
                    "run_id": summary.get("run_id"),
                    "status": summary.get("evidence_store", {}).get("status"),
                    "decision": policy.get("decision"),
                    "A_target_db": metrics.get("A_target_db"),
                    "A_protected_db": metrics.get("A_protected_db"),
                    "SI_SDRi_protected_db": metrics.get("SI_SDRi_protected_db"),
                    "path": summary_path.parent.name,
                    "mtime": summary_path.stat().st_mtime,
                }
            )
        except Exception:
            continue
    rows.sort(key=lambda x: x["mtime"], reverse=True)
    for row in rows:
        row.pop("mtime", None)
    return rows


def load_run(output_root: Path, run_id: str) -> dict:
    run_dir = _safe_child(output_root, run_id)
    summary_path = run_dir / "demo_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(run_id)
    summary = _load_json(summary_path)
    artifacts = []
    for item in summary.get("artifacts", []):
        copy = dict(item)
        copy["url"] = f"/artifacts/{run_id}/{item['path']}"
        artifacts.append(copy)
    summary["artifacts"] = artifacts
    summary["figures"] = {
        "waveform": f"/artifacts/{run_id}/waveform_comparison.png",
        "spectrogram": f"/artifacts/{run_id}/spectrogram_comparison.png",
    }
    summary["audio"] = {
        "mixture": f"/artifacts/{run_id}/mixture.wav",
        "output": f"/artifacts/{run_id}/output_selective.wav",
        "protected": f"/artifacts/{run_id}/protected.wav",
        "target": f"/artifacts/{run_id}/target.wav",
        "background": f"/artifacts/{run_id}/background.wav",
    }
    return summary


def system_status(dataset_root: Path) -> dict:
    metadata = dataset_root / "metadata" / "UrbanSound8K.csv"
    fold1 = dataset_root / "audio" / "fold1"
    fold10 = dataset_root / "audio" / "fold10"
    dataset_mounted = metadata.exists() and fold1.exists() and fold10.exists()
    return {
        "service": "ok",
        "scope": "PI8+ technical prototype",
        "clinicalClaim": False,
        "physicalANC": False,
        "dataset": {
            "root": str(dataset_root),
            "mounted": dataset_mounted,
            "metadata": metadata.exists(),
            "fold1": fold1.exists(),
            "fold10": fold10.exists(),
            "validation": "not_run",
        },
        "modules": [
            {
                "id": "M1",
                "name": "Ingesta y representación",
                "state": "partial",
                "evidence": "DSP baseline 16 kHz / STFT implementado",
            },
            {
                "id": "M2",
                "name": "Reconocimiento semántico",
                "state": "software_ready_evidence_pending",
                "evidence": "pipeline UrbanSound8K + SVM/RF + fixture CI",
            },
            {
                "id": "M3a",
                "name": "Mezclas controladas",
                "state": "baseline",
                "evidence": "stems sintéticos reproducibles",
            },
            {
                "id": "M3b",
                "name": "Política target/protected",
                "state": "implemented",
                "evidence": "ALLOW/BLOCK + protected precedence",
            },
            {
                "id": "M4",
                "name": "Máscara T-F + reconstrucción",
                "state": "baseline",
                "evidence": "IRM oracle + gain + iSTFT; learned model pendiente",
            },
            {
                "id": "M5",
                "name": "Runtime / profiling",
                "state": "partial",
                "evidence": "procesamiento de clip medido; streaming/E2E pendiente",
            },
            {
                "id": "M6",
                "name": "Evidencia / métricas",
                "state": "implemented",
                "evidence": "SQLite + Run ID + SHA-256 + validator",
            },
        ],
        "criteria": {
            "semantic": {"Macro-F1": ">= 0.85"},
            "acoustic": {
                "A_target_db": ">= 6",
                "A_protected_db": "<= 1",
                "SI_SDRi_protected_db": "> 0",
            },
            "compute": {
                "laptop_p95_per_hop_ms": "<= 10",
                "laptop_e2e_p95_ms": "<= 60",
                "android_tflite_p95_ms": "<= 20",
            },
        },
        "pending": [
            "UrbanSound8K full benchmark evidence",
            "learned target-conditioned M4",
            "blockwise laptop streaming",
            "TFLite export/parity",
            "physical Honor X8c profiling",
            "10-minute stability validation",
        ],
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "HESYCHIA/0.1"

    @property
    def output_root(self) -> Path:
        return self.server.output_root

    @property
    def dataset_root(self) -> Path:
        return self.server.dataset_root

    @property
    def jobs(self) -> JobManager:
        return self.server.jobs

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}")

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._send_json({"status": "ok", "service": "hesychia-web"})
            return
        if path == "/api/status":
            self._send_json(system_status(self.dataset_root))
            return
        if path == "/api/jobs":
            self._send_json({"jobs": self.jobs.list()})
            return
        if path.startswith("/api/jobs/"):
            job_id = unquote(path.removeprefix("/api/jobs/"))
            job = self.jobs.get(job_id)
            if not job:
                self._send_json({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(job)
            return
        if path == "/api/runs":
            self._send_json({"runs": list_demo_runs(self.output_root)})
            return
        if path.startswith("/api/runs/"):
            run_id = unquote(path.removeprefix("/api/runs/"))
            try:
                self._send_json(load_run(self.output_root, run_id))
            except FileNotFoundError:
                self._send_json({"error": "run_not_found"}, HTTPStatus.NOT_FOUND)
            except ValueError:
                self._send_json({"error": "invalid_run_id"}, HTTPStatus.BAD_REQUEST)
            return
        if path.startswith("/artifacts/"):
            parts = [unquote(x) for x in path.split("/") if x]
            if len(parts) != 3:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            _, run_id, filename = parts
            try:
                file_path = _safe_child(self.output_root, run_id, filename)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self._send_file(file_path)
            return
        if path in ("/", "/index.html"):
            self._send_file(WEB_ROOT / "index.html")
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self._json_body()
        except Exception as exc:
            self._send_json(
                {"error": "invalid_json", "message": str(exc)},
                HTTPStatus.BAD_REQUEST,
            )
            return

        if path == "/api/jobs/attenuate":
            try:
                seed = int(payload.get("seed", 42))
                cap_db = float(payload.get("cap_db", 12.0))
                alpha = float(payload.get("alpha", 1.0))
            except (TypeError, ValueError):
                self._send_json(
                    {"error": "invalid_parameters"},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            def worker(job_id):
                run_id = job_id.replace("ATTENUATE-", "RUN-")
                out = self.output_root / run_id
                summary = run_demo(
                    out,
                    seed=seed,
                    target_label="siren_synthetic",
                    protected=["speech_like_synthetic"],
                    cap_db=cap_db,
                    alpha=alpha,
                    run_id=run_id,
                )
                return summary, f"/api/runs/{run_id}"

            job = self.jobs.start("attenuate", worker)
            self._send_json(job, HTTPStatus.ACCEPTED)
            return

        if path == "/api/dataset/validate":
            if not self.dataset_root.exists():
                self._send_json(
                    {
                        "error": "dataset_not_mounted",
                        "root": str(self.dataset_root),
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            def worker(job_id):
                report = validate_contract(
                    self.dataset_root,
                    require_official_shape=True,
                    verify_audio=True,
                )
                return asdict(report), None

            job = self.jobs.start("dataset", worker)
            self._send_json(job, HTTPStatus.ACCEPTED)
            return

        if path == "/api/jobs/benchmark":
            metadata = self.dataset_root / "metadata" / "UrbanSound8K.csv"
            if not metadata.exists():
                self._send_json(
                    {
                        "error": "dataset_not_mounted",
                        "message": "Mount the official UrbanSound8K dataset before starting M2.",
                        "root": str(self.dataset_root),
                    },
                    HTTPStatus.CONFLICT,
                )
                return
            seed = int(payload.get("seed", 42))

            def worker(job_id):
                out = LAB_ROOT / "outputs" / "m2_urbansound8k" / job_id
                summary = run_benchmark(
                    self.dataset_root,
                    out,
                    seed=seed,
                    require_official_shape=True,
                )
                return summary, str(out.relative_to(LAB_ROOT))

            job = self.jobs.start("benchmark", worker)
            self._send_json(job, HTTPStatus.ACCEPTED)
            return

        if path in (
            "/api/jobs/train-mask",
            "/api/jobs/export-tflite",
            "/api/streaming/session",
        ):
            self._send_json(
                {
                    "implemented": False,
                    "state": "pending",
                    "message": (
                        "This contract is documented but is intentionally disabled "
                        "until the corresponding thesis module is implemented and tested."
                    ),
                },
                HTTPStatus.NOT_IMPLEMENTED,
            )
            return

        self._send_json({"error": "route_not_found"}, HTTPStatus.NOT_FOUND)


class AppServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        address,
        handler,
        *,
        output_root: Path,
        dataset_root: Path,
    ):
        super().__init__(address, handler)
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.dataset_root = dataset_root
        self.jobs = JobManager()


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    *,
    output_root: str | Path | None = None,
    dataset_root: str | Path | None = None,
) -> AppServer:
    return AppServer(
        (host, port),
        AppHandler,
        output_root=Path(output_root or DEFAULT_OUTPUT_ROOT),
        dataset_root=Path(dataset_root or DEFAULT_DATASET_ROOT),
    )


def main():
    ap = argparse.ArgumentParser(description="HESYCHIA reproducible demo web console")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    ap.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    args = ap.parse_args()

    server = create_server(
        args.host,
        args.port,
        output_root=args.output_root,
        dataset_root=args.dataset_root,
    )
    print(
        f"HESYCHIA web console: http://{args.host}:{server.server_address[1]} "
        f"| dataset={args.dataset_root}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
