import pathlib
import sys
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from m4_causal_bridge import BINS, HOP, N_FFT, CausalSpectrum, frames, ideal_mask, reconstruct_stream


class CausalBridgeTests(unittest.TestCase):
    def test_unity_reconstructs(self):
        for n in (160, 161, 640, 5144, 16000):
            x = np.random.default_rng(n).normal(size=n).astype(np.float32) * .1
            y = reconstruct_stream(x, lambda frame: np.ones(BINS))
            np.testing.assert_allclose(y, x, atol=2e-5)

    def test_block_policy_forces_unity(self):
        x = np.random.default_rng(3).normal(size=1280).astype(np.float32)
        def must_not_call(_):
            raise AssertionError("network called in BLOCK")
        np.testing.assert_allclose(reconstruct_stream(x, must_not_call, block_decision="BLOCK"), x, atol=2e-5)

    def test_zero_gain(self):
        x = np.random.default_rng(4).normal(size=1280).astype(np.float32)
        self.assertLess(float(np.abs(reconstruct_stream(x, lambda f: np.zeros(BINS))).max()), 2e-6)

    def test_future_does_not_affect_previous(self):
        x = np.random.default_rng(8).normal(size=HOP*20).astype(np.float32)
        y = x.copy()
        y[HOP*9:] *= -2
        np.testing.assert_array_equal(frames(x)[:9], frames(y)[:9])

    def test_mask_absent_target(self):
        speech = np.random.default_rng(5).normal(size=HOP*10).astype(np.float32)
        mask = ideal_mask(np.zeros_like(speech), speech, np.zeros_like(speech))
        self.assertEqual(mask.shape, (10, BINS))
        self.assertTrue(np.all(mask == 0))

    def test_callback_only_current_frame(self):
        x = np.random.default_rng(10).normal(size=HOP*8).astype(np.float32)
        got=[]
        reconstruct_stream(x,lambda f:(got.append(f.copy()) or np.ones(BINS)))
        extracted = frames(x)
        # The callback additionally sees flushing silence, so compare only real frames.
        for j in range(8):
            np.testing.assert_allclose(got[j], np.log1p(20*np.abs(extracted[j])), atol=1e-5)

    def test_bad_gain_blocks(self):
        with self.assertRaises(ValueError):
            reconstruct_stream(np.ones(HOP), lambda f: np.full(BINS, np.nan))


if __name__ == "__main__":
    unittest.main()
