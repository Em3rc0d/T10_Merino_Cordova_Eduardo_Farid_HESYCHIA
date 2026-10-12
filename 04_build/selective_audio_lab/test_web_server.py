from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from web_server import create_server


class WebConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.server = create_server(
            "127.0.0.1",
            0,
            output_root=base / "outputs",
            dataset_root=base / "missing_dataset",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def get_json(self, path):
        with request.urlopen(self.base + path, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def post_json(self, path, payload):
        req = request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def post_error(self, path, payload):
        req = request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(error.HTTPError) as ctx:
            request.urlopen(req, timeout=15)
        return ctx.exception.code, json.loads(ctx.exception.read().decode("utf-8"))

    def wait_job(self, job_id):
        for _ in range(100):
            _, current = self.get_json(f"/api/jobs/{job_id}")
            if current["status"] in ("completed", "failed"):
                return current
            time.sleep(0.2)
        self.fail(f"job did not finish: {job_id}")

    def test_health_and_truthful_status(self):
        status_code, health = self.get_json("/api/health")
        self.assertEqual(status_code, 200)
        self.assertEqual(health["status"], "ok")

        _, status = self.get_json("/api/status")
        self.assertFalse(status["dataset"]["mounted"])
        states = {x["id"]: x["state"] for x in status["modules"]}
        self.assertEqual(states["M3b"], "implemented")
        self.assertEqual(states["M4"], "baseline")
        self.assertEqual(states["M5"], "partial")

    def test_allow_job_generates_real_evidence_and_integrity_passes(self):
        status_code, job = self.post_json(
            "/api/jobs/attenuate",
            {
                "seed": 42,
                "cap_db": 12.0,
                "alpha": 1.0,
                "protect_target": False,
            },
        )
        self.assertEqual(status_code, 202)
        final = self.wait_job(job["jobId"])
        self.assertEqual(final["status"], "completed", final.get("error"))

        _, run = self.get_json(final["resultRef"])
        self.assertEqual(run["policy"]["decision"], "ALLOW")
        self.assertGreaterEqual(run["metrics"]["A_target_db"], 6.0)
        self.assertLessEqual(run["metrics"]["A_protected_db"], 1.0)
        run_dir = Path(self.tmp.name) / "outputs" / run["run_id"]
        self.assertTrue((run_dir / "evidence.sqlite").exists())
        self.assertTrue((run_dir / "waveform_comparison.png").exists())
        self.assertTrue((run_dir / "spectrogram_comparison.png").exists())

        code, integrity = self.get_json(
            f"/api/runs/{run['run_id']}/integrity"
        )
        self.assertEqual(code, 200)
        self.assertTrue(integrity["validated"])

    def test_block_job_preserves_mixture(self):
        _, job = self.post_json(
            "/api/jobs/attenuate",
            {
                "seed": 42,
                "cap_db": 12.0,
                "alpha": 1.0,
                "protect_target": True,
            },
        )
        final = self.wait_job(job["jobId"])
        self.assertEqual(final["status"], "completed", final.get("error"))
        _, run = self.get_json(final["resultRef"])
        self.assertEqual(run["policy"]["decision"], "BLOCK")
        self.assertEqual(run["policy"]["reason"], "target_is_protected")
        self.assertAlmostEqual(run["metrics"]["A_target_db"], 0.0, places=3)

        self.assertAlmostEqual(run["metrics"]["A_protected_db"], 0.0, places=3)
        self.assertAlmostEqual(run["metrics"]["SI_SDRi_protected_db"], 0.0, places=3)

    def test_invalid_attenuation_parameters_are_rejected(self):
        cases = [
            {"alpha": 1.2},
            {"alpha": "nan"},
            {"cap_db": -1},
            {"cap_db": "inf"},
            {"seed": -1},
            {"seed": True},
            {"protect_target": "yes"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                code, body = self.post_error("/api/jobs/attenuate", payload)
                self.assertEqual(code, 400)
                self.assertEqual(body["error"], "invalid_parameters")

    def test_benchmark_is_blocked_without_dataset(self):
        code, body = self.post_error("/api/jobs/benchmark", {"seed": 42})
        self.assertEqual(code, 409)
        self.assertEqual(body["error"], "dataset_not_mounted")

    def test_dataset_validation_is_blocked_without_metadata(self):
        code, body = self.post_error("/api/dataset/validate", {})
        self.assertEqual(code, 409)
        self.assertEqual(body["error"], "dataset_not_mounted")

    def test_pending_contracts_return_501(self):
        for path in (
            "/api/jobs/train-mask",
            "/api/jobs/export-tflite",
            "/api/streaming/session",
        ):
            with self.subTest(path=path):
                code, body = self.post_error(path, {})
                self.assertEqual(code, 501)
                self.assertFalse(body["implemented"])


if __name__ == "__main__":
    unittest.main()
