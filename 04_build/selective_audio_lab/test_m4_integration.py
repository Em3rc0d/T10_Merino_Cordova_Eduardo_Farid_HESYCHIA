from __future__ import annotations

import json
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from m4_experimental import MODEL_ROOT, ExperimentalPredictor, inspect_model
from audio_core import synthesize_drilling
from attenuation import apply_selective_attenuation
from policy import resolve_policy
from run_demo import run_demo
from compare_demo import run_comparison, validate_comparison
from validate_artifacts import validate_run, EvidenceValidationError
import test_web_server as web_tests


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional CPU Torch runtime not installed")
class M4IntegrationTests(unittest.TestCase):
    def test_mixture_only_inference_and_no_oracle_fallback(self):
        predictor = ExperimentalPredictor()
        p, t, b = synthesize_drilling(42)
        called = []
        def mixture_only(mixture, target_id):
            called.append((mixture.shape, target_id))
            return predictor.predict(mixture, target_id)
        with patch("attenuation.oracle_irm", side_effect=AssertionError("Oracle used by CNN")):
            result = apply_selective_attenuation(p, t, b, resolve_policy("drilling_synthetic", [], 12),
                                                 engine="cnn_experimental", predictor=mixture_only)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0][1], 4)
        self.assertTrue(np.isfinite(result[1]).all())
        self.assertEqual(result[-1]["executed_engine"], "cnn_experimental")

    def test_block_skips_predictor_and_is_bit_exact(self):
        p, t, b = synthesize_drilling(42)
        def forbidden(*args):
            raise AssertionError("BLOCK invoked CNN")
        result = apply_selective_attenuation(p, t, b, resolve_policy("siren_synthetic", [], 12),
                                             engine="cnn_experimental", predictor=forbidden)
        self.assertTrue(np.array_equal(result[0], result[1]))
        self.assertEqual(result[-1]["executed_engine"], "bypass")

    def test_paired_metrics_checkpoint_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            pair = run_comparison(tmp, "PAIR", seed=42)
            self.assertTrue(validate_comparison(tmp, "PAIR")["validated"])
            self.assertEqual(pair["runs"]["oracle"]["mixture_sha256"], pair["runs"]["cnn_experimental"]["mixture_sha256"])
            cnn = Path(tmp) / "PAIR-CNN"
            self.assertTrue(validate_run(cnn, "PAIR-CNN")["validated"])
            summary = json.loads((cnn / "demo_summary.json").read_text())
            self.assertEqual(summary["config"]["model"]["sha256"], inspect_model()["checkpoint_sha256"])
            with (cnn / "checkpoint.pt").open("ab") as f:
                f.write(b"tamper")
            with self.assertRaises(EvidenceValidationError):
                validate_run(cnn, "PAIR-CNN")

    def test_corrupt_checkpoint_fails_explicitly_but_block_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "model"
            shutil.copytree(MODEL_ROOT, root)
            (root / "checkpoint.pt").write_bytes(b"corrupt")
            self.assertFalse(inspect_model(root)["ready"])
            with self.assertRaises(ValueError):
                run_demo(Path(tmp)/"allow", engine="cnn_experimental", model_root=root)
            blocked = run_demo(Path(tmp)/"block", engine="cnn_experimental", model_root=root,
                               target_label="siren_synthetic")
            self.assertEqual(blocked["config"]["executed_engine"], "bypass")
            self.assertIsNone(blocked["config"]["model"])

    def test_nonfinite_and_wrong_shape_masks_rejected(self):
        p, t, b = synthesize_drilling(42)
        for mask in (np.zeros((1, 1)), np.full((257, 401), np.nan), np.full((257, 401), 1.5)):
            with self.subTest(shape=mask.shape), self.assertRaises(ValueError):
                apply_selective_attenuation(p, t, b, resolve_policy("drilling_synthetic", [], 12),
                                             engine="cnn_experimental", predictor=lambda *args: mask)


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional CPU Torch runtime not installed")
class M4APITests(unittest.TestCase):
    setUp = web_tests.WebConsoleTests.setUp
    tearDown = web_tests.WebConsoleTests.tearDown
    get_json = web_tests.WebConsoleTests.get_json
    post_json = web_tests.WebConsoleTests.post_json
    post_error = web_tests.WebConsoleTests.post_error
    wait_job = web_tests.WebConsoleTests.wait_job

    def test_real_cnn_api_run_and_sqlite(self):
        self.server.model_root = MODEL_ROOT
        _, info = self.get_json("/api/m4")
        self.assertTrue(info["ready"])
        self.assertEqual(info["parameters"], 236833)
        _, job = self.post_json("/api/jobs/attenuate", {"engine": "cnn_experimental"})
        final = self.wait_job(job["jobId"])
        self.assertEqual(final["status"], "completed", final["error"])
        _, summary = self.get_json(final["resultRef"])
        self.assertEqual(summary["config"]["executed_engine"], "cnn_experimental")
        _, integrity = self.get_json(final["resultRef"] + "/integrity")
        self.assertTrue(integrity["validated"])

    def test_comparison_api_same_scene(self):
        self.server.model_root = MODEL_ROOT
        _, job = self.post_json("/api/jobs/compare", {"seed": 42})
        final = self.wait_job(job["jobId"])
        self.assertEqual(final["status"], "completed", final["error"])
        _, pair = self.get_json(final["resultRef"])
        self.assertTrue(pair["same_scene_verified"])
        _, integrity = self.get_json(final["resultRef"] + "/integrity")
        self.assertTrue(integrity["validated"])

    def test_missing_model_cnn_fails_and_siren_bypasses(self):
        _, job = self.post_json("/api/jobs/attenuate", {"engine": "cnn_experimental"})
        self.assertEqual(self.wait_job(job["jobId"])["status"], "failed")
        _, job = self.post_json("/api/jobs/attenuate", {"engine": "cnn_experimental", "target_label": "siren_synthetic"})
        final = self.wait_job(job["jobId"])
        self.assertEqual(final["status"], "completed", final["error"])
        self.assertEqual(final["result"]["config"]["executed_engine"], "bypass")

    def test_unknown_or_final_model_rejected(self):
        for engine in ("final", "invented", ""):
            self.assertEqual(self.post_error("/api/jobs/attenuate", {"engine": engine})[0], 400)


if __name__ == "__main__":
    unittest.main()
