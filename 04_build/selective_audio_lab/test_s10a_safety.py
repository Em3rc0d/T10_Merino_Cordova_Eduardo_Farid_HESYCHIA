"""S10-A security policy and synthetic fixture regression tests."""
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from audio_core import synthesize, synthesize_drilling
from attenuation import apply_selective_attenuation
from policy import (POLICY_VERSION, MANDATORY_PROTECTED, resolve_policy)

class S10ASafetyTests(unittest.TestCase):
    def test_mandatory_emergency_signals(self):
        for label in ("siren_synthetic","siren","emergency_siren","fire_alarm",
                      "evacuation_alarm","car_horn","warning_horn"):
            with self.subTest(label=label):
                p = resolve_policy(label, [], 12.0)
                self.assertEqual(p.decision, "BLOCK")
                self.assertEqual(p.reason, "mandatory_protected_signal")
                self.assertIn(label, p.protected_set)

    def test_unknown_labels_fail_closed(self):
        for label in ("unknown","SIREN","siren_synthetic ",""):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    resolve_policy(label, [], 12.0)

    def test_manual_protection_only_adds(self):
        allowed = resolve_policy("drilling_synthetic", [], 12.0)
        blocked = resolve_policy("drilling_synthetic", ["drilling_synthetic"], 12.0)
        self.assertEqual(allowed.decision, "ALLOW")
        self.assertEqual(blocked.decision, "BLOCK")
        self.assertEqual(blocked.reason, "target_is_protected")
        self.assertTrue(MANDATORY_PROTECTED.issubset(set(allowed.protected_set)))

    def test_drilling_fixture_reproducible_and_distinct_from_siren(self):
        a = synthesize_drilling(42)
        b = synthesize_drilling(42)
        for x, y in zip(a, b):
            self.assertTrue(np.array_equal(x, y))
        self.assertFalse(np.array_equal(a[1], synthesize(42)[1]))

    def test_siren_digital_bypass_exact(self):
        p,t,b = synthesize(42)
        policy = resolve_policy("siren_synthetic", [], 12.0)
        mix,out,_,_,_,_,gain,metrics = apply_selective_attenuation(p,t,b,policy)
        self.assertTrue(np.array_equal(mix,out))
        self.assertTrue(np.all(gain == 1))
        self.assertEqual(metrics["A_target_db"], 0.0)
        self.assertEqual(metrics["A_protected_db"], 0.0)
        self.assertEqual(metrics["policy_reason"], "mandatory_protected_signal")

    def test_drilling_stays_oracle_not_neural(self):
        p,t,b=synthesize_drilling(42)
        policy=resolve_policy("drilling_synthetic",["speech_like_synthetic"],12.0)
        mix,out,_,_,_,mask,gain,metrics=apply_selective_attenuation(p,t,b,policy)
        self.assertEqual(metrics["baseline_type"], "oracle_IRM_stem_demo")
        self.assertEqual(metrics["policy_decision"], "ALLOW")
        self.assertFalse(np.array_equal(mix,out))
        self.assertTrue(np.isfinite(out).all())
        self.assertGreaterEqual(float(mask.min()),0.0)
        self.assertLessEqual(float(mask.max()),1.0)
        self.assertLessEqual(float(gain.max()),1.0)

if __name__ == "__main__":
    unittest.main()
