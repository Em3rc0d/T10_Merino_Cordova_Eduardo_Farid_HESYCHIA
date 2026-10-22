"""Small offline test suite for deterministic, non-semantic acoustic screen."""
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from m4_tonal_screen import inspect_wav, sha256


class TestM4TonalScreen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'tone.wav'
        t = np.arange(16000) / 16000
        sf.write(self.file, .2 * np.sin(2*np.pi*800*t), 16000, subtype='PCM_16')

    def test_deterministic_screen_is_not_admission(self):
        a, b = inspect_wav(self.file), inspect_wav(self.file)
        self.assertEqual(a, b)
        self.assertEqual(a['acoustic_isolation_certification'], 'NOT_DETERMINED')
        self.assertEqual(a['corpus_admission'], 'NOT_ADMITTED')
        self.assertGreater(a['stft']['active_frames'], 0)

    def test_matching_pinned_hash(self):
        self.assertEqual(inspect_wav(self.file, sha256(self.file))['file_sha256'], sha256(self.file))

    def test_mismatch_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_SHA256_MISMATCH'):
            inspect_wav(self.file, '0'*64)

    def test_stereo_rejected(self):
        stereo = Path(self.tmp.name) / 'stereo.wav'
        audio, sr = sf.read(self.file)
        sf.write(stereo, np.column_stack([audio, audio]), sr)
        with self.assertRaisesRegex(ValueError, 'NOT_M4_PCM16_MONO_16000'):
            inspect_wav(stereo)

    def test_silence_rejected(self):
        silence = Path(self.tmp.name) / 'silence.wav'
        sf.write(silence, np.zeros(16000), 16000)
        with self.assertRaisesRegex(ValueError, 'SILENT_SIGNAL'):
            inspect_wav(silence)

    def test_wrong_samplerate_rejected(self):
        wrong = Path(self.tmp.name) / 'wrong.wav'
        sf.write(wrong, np.ones(4000) * .1, 8000)
        with self.assertRaisesRegex(ValueError, 'NOT_M4_PCM16_MONO_16000'):
            inspect_wav(wrong)


if __name__ == '__main__':
    unittest.main()
