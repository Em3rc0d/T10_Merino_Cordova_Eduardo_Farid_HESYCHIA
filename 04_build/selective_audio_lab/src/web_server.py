from __future__ import annotations

import argparse
import json
import mimetypes
import math
import os
import threading
import traceback
import uuid
import re
import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from run_demo import run_demo
from latency_benchmark import run_latency_benchmark
from semantic_benchmark import run_benchmark
from urbansound8k import validate_contract
from validate_artifacts import validate_run
from policy import DEMO_TARGETS
from m4_experimental import MODEL_ROOT, inspect_model
from compare_demo import run_comparison, validate_comparison

LAB_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = LAB_ROOT / "web"
DEFAULT_OUTPUT_ROOT = Path(
    os.environ.get("HESYCHIA_OUTPUT_ROOT", LAB_ROOT / "outputs" / "web")
)
DEFAULT_DATASET_ROOT = Path(
    os.environ.get("URBANSOUND8K_ROOT", "/data/UrbanSound8K")
)
DEFAULT_EVIDENCE_ROOT = Path(
    os.environ.get("HESYCHIA_EVIDENCE_ROOT", LAB_ROOT / "outputs")
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._worker_lock = threading.Lock()  # Matplotlib/model jobs execute serially.

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
                with self._worker_lock:
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


def _as_int(payload: dict, key: str, default: int, *, low: int, high: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if not low <= value <= high:
        raise ValueError(f"{key} must be within [{low}, {high}]")
    return value


def _as_float(
    payload: dict,
    key: str,
    default: float,
    *,
    low: float,
    high: float,
) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key} must be finite and within [{low}, {high}]")
    return value


def _as_bool(payload: dict, key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _as_label(payload: dict, key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    value = value.strip()
    if len(value) > 80:
        raise ValueError(f"{key} must contain at most 80 characters")
    return value


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
                    "engine": summary.get("config", {}).get("executed_engine", "oracle"),
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
        "mask": f"/artifacts/{run_id}/mask.png",
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


def _latest_json(root: Path, pattern: str) -> dict | None:
    if not root.exists():
        return None
    candidates = [p for p in root.glob(pattern) if p.is_file()]
    if not candidates:
        return None
    path = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        payload = _load_json(path)
    except Exception:
        return None
    payload["_evidence_path"] = str(path)
    return payload


def discover_m2_evidence(evidence_root: Path) -> dict | None:
    root = evidence_root / "m2_urbansound8k"
    direct = root / "semantic_summary.json"
    if direct.exists():
        try:
            payload = _load_json(direct)
            payload["_evidence_path"] = str(direct)
            return payload
        except Exception:
            pass
    return _latest_json(root, "**/semantic_summary.json")


def documented_m2_reference():
    """Historical text evidence is visibly distinct from mounted raw results."""
    path = LAB_ROOT.parents[1] / "docs" / "M2_REAL_RESULT_2026-10-12.md"
    if not path.exists():
        return None
    raw = path.read_bytes()
    match = re.search(r"\| Macro-F1 \| \*\*([0-9.]+)\*\*", raw.decode("utf-8"))
    if not match:
        return None
    return {"scope": "documented_historical_result_raw_artifacts_not_mounted",
            "macro_f1": float(match.group(1)), "rnf03_met": float(match.group(1)) >= .85,
            "source": "docs/M2_REAL_RESULT_2026-10-12.md",
            "source_sha256": hashlib.sha256(raw).hexdigest()}


def discover_latency_evidence(evidence_root: Path) -> dict | None:
    return _latest_json(evidence_root / "latency", "**/latency_summary.json")


def discover_latency_campaign(evidence_root: Path) -> dict | None:
    return _latest_json(
        evidence_root / "latency_campaigns",
        "**/latency_campaign_summary.json",
    )


def system_status(dataset_root: Path, evidence_root: Path, model_root=MODEL_ROOT) -> dict:
    m4 = inspect_model(model_root)
    m2_reference = documented_m2_reference()
    metadata = dataset_root / "metadata" / "UrbanSound8K.csv"
    fold1 = dataset_root / "audio" / "fold1"
    fold10 = dataset_root / "audio" / "fold10"
    dataset_mounted = metadata.exists() and fold1.exists() and fold10.exists()
    m2 = discover_m2_evidence(evidence_root)
    latency = discover_latency_evidence(evidence_root)
    latency_campaign = discover_latency_campaign(evidence_root)
    m2_measured = bool(
        m2
        and int(m2.get("dataset_rows", -1)) == 8732
        and isinstance(m2.get("test"), dict)
        and "macro_f1" in m2.get("test", {})
    )
    m2_met = bool(m2_measured and m2.get("rnf03_met"))
    latency_measured = bool(
        latency
        and latency.get("measurement_scope") == "whole_clip_processing_only"
        and latency.get("processing_p95_ms") is not None
    )
    latency_campaign_measured = bool(
        latency_campaign
        and latency_campaign.get("measurement_scope") == "whole_clip_processing_only"
        and latency_campaign.get("pooled_p95_ms") is not None
        and int(latency_campaign.get("batch_count", 0)) >= 2
    )
    pending = [
        "M4 final scientific validation: real corpus, preservation and independent test",
        "blockwise laptop streaming",
        "TFLite export/parity",
        "physical Honor X8c profiling",
        "10-minute stability validation",
    ]
    if not m2_measured:
        pending.insert(0, "M2 raw benchmark artifacts not mounted; historical result documented" if m2_reference else "UrbanSound8K full benchmark evidence")
    elif not m2_met:
        pending.insert(0, "RNF-03 semantic target >= 0.85 not met by current M2 baseline")

    return {
        "service": "ok",
        "scope": "PI9/PI10 experimental integration; scientific validation pending",
        "m4": m4,
        "m2_reference": m2_reference,
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
                "state": (
                    "implemented"
                    if m2_met
                    else "measured_not_met"
                    if m2_measured
                    else "reported_not_met"
                    if m2_reference and not m2_reference["rnf03_met"]
                    else "software_ready_evidence_pending"
                ),
                "evidence": (
                    f"UrbanSound8K real · {m2.get('selected_model')} · "
                    f"Macro-F1 test={float(m2['test']['macro_f1']):.4f} · "
                    f"RNF-03={'CUMPLE' if m2_met else 'NO CUMPLE'}"
                    if m2_measured
                    else (f"Resultado histórico documentado Macro-F1={m2_reference['macro_f1']:.4f}; RNF-03 NO CUMPLE. Artefactos crudos no montados."
                          if m2_reference and not m2_reference["rnf03_met"]
                          else "pipeline UrbanSound8K + SVM/RF + fixture CI")
                ),
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
                "state": "experimental" if m4["ready"] else "baseline",
                "evidence": ("CNN experimental disponible + Oracle; validación científica pendiente"
                             if m4["ready"] else "Oracle disponible; CNN experimental no disponible en este entorno"),
            },
            {
                "id": "M5",
                "name": "Runtime / profiling",
                "state": "partial",
                "evidence": (
                    f"{latency_campaign.get('device_label','host')} · "
                    f"campaign pooled p95={float(latency_campaign['pooled_p95_ms']):.3f} ms · "
                    f"{int(latency_campaign.get('batch_count',0))} lotes / "
                    f"{int(latency_campaign.get('total_samples',0))} muestras; "
                    "streaming/E2E pendiente"
                    if latency_campaign_measured
                    else (
                        f"{latency.get('device_label','host')} · whole-clip p95="
                        f"{float(latency['processing_p95_ms']):.3f} ms; "
                        "streaming/E2E pendiente"
                        if latency_measured
                        else "procesamiento de clip medido; streaming/E2E pendiente"
                    )
                ),
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
        "pending": pending,
        "m2_evidence": m2 if m2_measured else None,
        "latency_evidence": latency if latency_measured else None,
        "latency_campaign_evidence": (
            latency_campaign if latency_campaign_measured else None
        ),
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
    def evidence_root(self) -> Path:
        return self.server.evidence_root

    @property
    def jobs(self) -> JobManager:
        return self.server.jobs

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}")

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length < 0 or length > 65536:
            raise ValueError("request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

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
            self._send_json(system_status(self.dataset_root, self.evidence_root, self.server.model_root))
            return
        if path == "/api/m4":
            self._send_json(inspect_model(self.server.model_root))
            return
        if path.startswith("/api/comparisons/"):
            ident = unquote(path.removeprefix("/api/comparisons/").removesuffix("/integrity"))
            try:
                directory = _safe_child(self.output_root, ident)
                if path.endswith("/integrity"):
                    self._send_json(validate_comparison(self.output_root, ident))
                else:
                    self._send_json(_load_json(directory / "comparison.json"))
            except (OSError, ValueError, RuntimeError) as exc:
                self._send_json({"error": "comparison_unavailable", "message": str(exc)}, HTTPStatus.CONFLICT)
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
        if path.startswith("/api/runs/") and path.endswith("/integrity"):
            run_id = unquote(
                path.removeprefix("/api/runs/").removesuffix("/integrity").rstrip("/")
            )
            try:
                run_dir = _safe_child(self.output_root, run_id)
                self._send_json(validate_run(run_dir, run_id))
            except FileNotFoundError:
                self._send_json({"error": "run_not_found"}, HTTPStatus.NOT_FOUND)
            except (ValueError, RuntimeError) as exc:
                self._send_json(
                    {"error": "integrity_check_failed", "message": str(exc)},
                    HTTPStatus.CONFLICT,
                )
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

        if path in ("/api/jobs/attenuate", "/api/jobs/compare"):
            try:
                seed = _as_int(payload, "seed", 42, low=0, high=2**32 - 1)
                cap_db = _as_float(payload, "cap_db", 12.0, low=0.0, high=120.0)
                alpha = _as_float(payload, "alpha", 1.0, low=0.0, high=1.0)
                protect_target = _as_bool(payload, "protect_target", False)
                target_label = _as_label(payload, "target_label", "drilling_synthetic")
                engine = _as_label(payload, "engine", "oracle")
                if engine not in ("oracle", "cnn_experimental"):
                    raise ValueError("engine must be oracle or cnn_experimental; final validated model is pending")
                if target_label not in DEMO_TARGETS:
                    raise ValueError("target_label must be a supported synthetic demo target")
            except ValueError as exc:
                self._send_json(
                    {"error": "invalid_parameters", "message": str(exc)},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            def worker(job_id):
                run_id = job_id.replace("ATTENUATE-", "RUN-")
                out = self.output_root / run_id
                protected = ["speech_like_synthetic"]
                if protect_target:
                    protected.append(target_label)
                if path == "/api/jobs/compare":
                    result = run_comparison(self.output_root, job_id, model_root=self.server.model_root,
                                            seed=seed, target_label=target_label, protected=protected,
                                            cap_db=cap_db, alpha=alpha)
                    return result, f"/api/comparisons/{job_id}"
                summary = run_demo(
                    out,
                    seed=seed,
                    target_label=target_label,
                    protected=protected,
                    cap_db=cap_db,
                    alpha=alpha,
                    run_id=run_id,
                    engine=engine,
                    model_root=self.server.model_root,
                )
                return summary, f"/api/runs/{run_id}"

            job = self.jobs.start("compare" if path.endswith("compare") else "attenuate", worker)
            self._send_json(job, HTTPStatus.ACCEPTED)
            return

        if path == "/api/jobs/latency":
            try:
                runs = _as_int(payload, "runs", 40, low=5, high=200)
                seed = _as_int(payload, "seed", 42, low=0, high=2**32 - 1)
                device_label = _as_label(payload, "device_label", "")
            except ValueError as exc:
                self._send_json(
                    {"error": "invalid_parameters", "message": str(exc)},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            def worker(job_id):
                out = LAB_ROOT / "outputs" / "latency" / job_id
                summary = run_latency_benchmark(
                    out,
                    runs=runs,
                    seed=seed,
                    device_label=device_label or None,
                )
                return summary, str(out.relative_to(LAB_ROOT))

            job = self.jobs.start("latency", worker)
            self._send_json(job, HTTPStatus.ACCEPTED)
            return

        if path == "/api/dataset/validate":
            if not (self.dataset_root / "metadata" / "UrbanSound8K.csv").exists():
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
            try:
                seed = _as_int(payload, "seed", 42, low=0, high=2**32 - 1)
            except ValueError as exc:
                self._send_json(
                    {"error": "invalid_parameters", "message": str(exc)},
                    HTTPStatus.BAD_REQUEST,
                )
                return

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
        evidence_root: Path,
        model_root: Path = MODEL_ROOT,
    ):
        super().__init__(address, handler)
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.dataset_root = dataset_root
        self.evidence_root = evidence_root
        self.model_root = model_root
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.jobs = JobManager()


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    *,
    output_root: str | Path | None = None,
    dataset_root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    model_root: str | Path | None = None,
) -> AppServer:
    return AppServer(
        (host, port),
        AppHandler,
        output_root=Path(output_root or DEFAULT_OUTPUT_ROOT),
        dataset_root=Path(dataset_root or DEFAULT_DATASET_ROOT),
        evidence_root=Path(evidence_root or DEFAULT_EVIDENCE_ROOT),
        model_root=Path(model_root or MODEL_ROOT),
    )


def main():
    ap = argparse.ArgumentParser(description="HESYCHIA reproducible demo web console")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    ap.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    ap.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT))
    args = ap.parse_args()

    server = create_server(
        args.host,
        args.port,
        output_root=args.output_root,
        dataset_root=args.dataset_root,
        evidence_root=args.evidence_root,
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
