from __future__ import annotations
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent / "src"))
from m4_causal_frontend import CausalWOLA, HOP, N_FFT, process_offline_as_stream


class M4CausalDesignTests(unittest.TestCase):
    def test_bypass_reconstruction(self):
        x = np.random.default_rng(42).normal(0, .1, 16000).astype(np.float32)
        np.testing.assert_allclose(process_offline_as_stream(x), x, atol=2e-6)

    def test_unit_gain_matches_bypass(self):
        x = np.random.default_rng(7).normal(size=4096).astype(np.float32)
        np.testing.assert_allclose(
            process_offline_as_stream(x),
            process_offline_as_stream(x, np.ones(N_FFT // 2 + 1)), atol=1e-6)

    def test_future_cannot_change_prior_outputs(self):
        a = np.random.default_rng(11).normal(size=HOP * 10).astype(np.float32)
        b = a.copy()
        b[HOP * 6:] += 10
        left, right = CausalWOLA(), CausalWOLA()
        for index in range(6):
            _, lhs = left.push(a[index * HOP:(index + 1) * HOP])
            _, rhs = right.push(b[index * HOP:(index + 1) * HOP])
            np.testing.assert_array_equal(lhs, rhs)

    def test_zero_gain(self):
        x = np.random.default_rng(1).normal(size=800).astype(np.float32)
        self.assertLess(np.abs(process_offline_as_stream(x, np.zeros(257))).max(), 1e-6)

    def test_invalid_gain_rejected(self):
        with self.assertRaises(ValueError):
            CausalWOLA().push(np.zeros(HOP), np.full(257, 1.1))
