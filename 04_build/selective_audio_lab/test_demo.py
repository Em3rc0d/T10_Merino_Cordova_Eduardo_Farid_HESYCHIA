import sys
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from audio_core import synthesize_drilling
from attenuation import apply_selective_attenuation
from policy import resolve_policy

class DemoSmokeTests(unittest.TestCase):
    def test_baseline_smoke(self):
        p, t, b = synthesize_drilling(seed=42)
        policy = resolve_policy("drilling_synthetic", ["speech_like_synthetic"], 12.0)
        mix, out, _, _, _, mask, _, metrics = apply_selective_attenuation(p, t, b, policy)
        self.assertEqual(len(mix), len(out))
        self.assertTrue(np.isfinite(out).all())
        self.assertGreaterEqual(float(mask.min()), 0.0)
        self.assertLessEqual(float(mask.max()), 1.0)
        self.assertGreaterEqual(metrics["A_target_db"], 6.0)
        self.assertLessEqual(metrics["A_protected_db"], 1.0)

if __name__ == "__main__":
    unittest.main()
