from __future__ import annotations
import sys
import tempfile
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from audio_core import synthesize
from attenuation import apply_selective_attenuation
from evidence_store import EvidenceStore
from policy import resolve_policy

class ContractV12Tests(unittest.TestCase):
    def test_allow_contract(self):
        p, t, b = synthesize(seed=42)
        policy = resolve_policy("siren_synthetic", ["speech_like_synthetic"], 12.0)
        mix, out, _, _, _, mask, gain, metrics = apply_selective_attenuation(p, t, b, policy)
        self.assertEqual(policy.decision, "ALLOW")
        self.assertEqual(metrics["sr"], 16000)
        self.assertEqual(metrics["n_fft"], 512)
        self.assertEqual(metrics["hop"], 160)
        self.assertEqual(len(mix), len(out))
        self.assertTrue(np.isfinite(out).all())
        self.assertGreaterEqual(float(mask.min()), 0.0)
        self.assertLessEqual(float(mask.max()), 1.0)
        self.assertGreaterEqual(float(gain.min()), 0.0)
        self.assertLessEqual(float(gain.max()), 1.0)
        self.assertGreaterEqual(metrics["A_target_db"], 6.0)
        self.assertLessEqual(metrics["A_protected_db"], 1.0)
        self.assertGreater(metrics["SI_SDRi_protected_db"], 0.0)

    def test_protected_precedence(self):
        p, t, b = synthesize(seed=42)
        policy = resolve_policy("speech_like_synthetic", ["speech_like_synthetic"], 12.0)
        mix, out, _, _, _, _, gain, metrics = apply_selective_attenuation(p, t, b, policy)
        self.assertEqual(policy.decision, "BLOCK")
        self.assertEqual(policy.reason, "target_is_protected")
        self.assertTrue(np.allclose(gain, 1.0))
        self.assertTrue(np.allclose(mix, out, atol=1e-5))
        self.assertAlmostEqual(metrics["A_target_db"], 0.0, places=3)

    def test_reproducible_seed(self):
        a = synthesize(seed=42)
        b = synthesize(seed=42)
        for xa, xb in zip(a, b):
            self.assertTrue(np.array_equal(xa, xb))

    def test_sqlite_roundtrip(self):
        p, t, b = synthesize(seed=42)
        policy = resolve_policy("siren_synthetic", ["speech_like_synthetic"], 12.0)
        _, _, _, _, _, _, _, metrics = apply_selective_attenuation(p, t, b, policy)
        metrics["wall_time_ms"] = 1.0
        artifacts = [{"artifact":"dummy.wav","kind":"audio","path":"dummy.wav","sha256":"abc123"}]
        policy_dict = {
            "target_label": policy.target_label,
            "protected_set": list(policy.protected_set),
            "decision": policy.decision,
            "reason": policy.reason,
        }
        with tempfile.TemporaryDirectory() as td:
            store = EvidenceStore(Path(td) / "evidence.sqlite")
            store.persist_demo(
                run_id="TEST-RUN-001",
                seed=42,
                metrics=metrics,
                artifacts=artifacts,
                policy=policy_dict,
                config={"test": True},
            )
            summary = store.summary("TEST-RUN-001")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["policy"]["decision"], "ALLOW")
            self.assertEqual(summary["artifact_count"], 1)
            self.assertIn("A_target_db", summary["metrics"])

if __name__ == "__main__":
    unittest.main()
