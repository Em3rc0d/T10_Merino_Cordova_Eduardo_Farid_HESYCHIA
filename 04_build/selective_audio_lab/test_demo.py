import sys
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'src'))
from run_demo import synthesize, process

class DemoContractTests(unittest.TestCase):
    def test_dsp_contract(self):
        p, t, b = synthesize(seed=42)
        mix, out, p2, t2, b2, mask, m = process(p, t, b)
        self.assertEqual(m['sr'], 16000)
        self.assertEqual(m['n_fft'], 512)
        self.assertEqual(m['hop'], 160)
        self.assertTrue(np.isfinite(out).all())
        self.assertTrue(np.isfinite(mask).all())
        self.assertGreaterEqual(float(mask.min()), 0.0)
        self.assertLessEqual(float(mask.max()), 1.0)
        self.assertGreaterEqual(m['A_target_db'], 6.0)
        self.assertLessEqual(m['A_protected_db'], 1.0)
        self.assertGreater(m['SI_SDRi_protected_db'], 0.0)

    def test_reproducible_seed(self):
        a = synthesize(seed=42)
        b = synthesize(seed=42)
        for xa, xb in zip(a, b):
            self.assertTrue(np.array_equal(xa, xb))

if __name__ == '__main__':
    unittest.main()
