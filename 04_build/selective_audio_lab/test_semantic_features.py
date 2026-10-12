from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from semantic_features import FEATURE_DIM, RESAMPLE_TYPE, SR, extract_features, load_audio


class SemanticFeatureTests(unittest.TestCase):
    def test_non_16khz_audio_uses_available_soxr_resampler(self):
        self.assertEqual(RESAMPLE_TYPE, "soxr_hq")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample_22050.wav"
            native_sr = 22050
            t = np.arange(native_sr, dtype=np.float32) / native_sr
            y = 0.6 * np.sin(2 * np.pi * 440.0 * t)
            sf.write(path, y, native_sr)

            loaded = load_audio(path)
            self.assertEqual(loaded.shape, (SR * 4,))
            self.assertTrue(np.isfinite(loaded).all())

            feat = extract_features(path)
            self.assertEqual(feat.shape, (FEATURE_DIM,))
            self.assertTrue(np.isfinite(feat).all())


if __name__ == "__main__":
    unittest.main()
