from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'src'))

from semantic_benchmark_10fold import mean_sd_ci95
from real_mixture_oracle_batch import ci95, run_batch


class ReviewClosureTests(unittest.TestCase):
    def test_10fold_stats_are_finite(self):
        stats = mean_sd_ci95([0.6, 0.7, 0.8, 0.9])
        self.assertAlmostEqual(stats['mean'], 0.75)
        self.assertGreater(stats['sd'], 0)
        self.assertLess(stats['ci95_low'], stats['mean'])
        self.assertGreater(stats['ci95_high'], stats['mean'])

    def test_real_mix_stats_are_finite(self):
        stats = ci95([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(stats['mean'], 2.5)
        self.assertGreater(stats['sd'], 0)

    def test_real_mix_rejects_underpowered_batch_before_io(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'n >= 100'):
                run_batch(td, td, Path(td) / 'out', n=99)


if __name__ == '__main__':
    unittest.main()