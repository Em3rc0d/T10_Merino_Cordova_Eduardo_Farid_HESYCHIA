from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib import request

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
        with request.urlopen(self.base + path, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def post_json(self, path, payload):
        req = request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_health_and_truthful_status(self):
        health = self.get_json("/api/health")
        self.assertEqual(health["status"], "ok")
        status = self.get_json("/api/status")
        self.assertFalse(status["dataset"]["mounted"])
        states = {x["id"]: x["state"] for x in status["modules"]}
        self.assertEqual(states["M3b"], "implemented")
        self.assertEqual(states["M4"], "baseline")
        self.assertEqual(states["M5"], "partial")

    def test_attenuation_job_generates_real_evidence(self):
        job = self.post_json(
            "/api/jobs/attenuate",
            {"seed": 42, "cap_db": 12.0, "alpha": 1.0},
        )
        job_id = job["jobId"]
        final = None
        for _ in range(80):
            current = self.get_json(f"/api/jobs/{job_id}")
            if current["status"] in ("completed", "failed"):
                final = current
                break
            time.sleep(0.2)
        self.assertIsNotNone(final)
        self.assertEqual(final["status"], "completed", final.get("error"))
        run = self.get_json(final["resultRef"])
        self.assertGreaterEqual(run["metrics"]["A_target_db"], 6.0)
        self.assertLessEqual(run["metrics"]["A_protected_db"], 1.0)
        self.assertTrue((Path(self.tmp.name) / "outputs" / run["run_id"] / "evidence.sqlite").exists())
        self.assertTrue((Path(self.tmp.name) / "outputs" / run["run_id"] / "waveform_comparison.png").exists())
        self.assertTrue((Path(self.tmp.name) / "outputs" / run["run_id"] / "spectrogram_comparison.png").exists())


if __name__ == "__main__":
    unittest.main()