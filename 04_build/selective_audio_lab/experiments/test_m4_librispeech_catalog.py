import csv
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from m4_librispeech_catalog import generate, speaker_id

class LibriSpeechCatalogTests(unittest.TestCase):
    def test_unique_speaker_candidates_unreviewed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for subset, sp in [('train-clean-100','101'),('dev-clean','102'),('test-clean','103')]:
                folder=root/subset/sp/'12'; folder.mkdir(parents=True)
                sf.write(folder/(sp+'-12-0001.flac'),np.random.default_rng(1).normal(size=16000).astype('float32'),16000)
            dest=root/'catalog.csv'
            out=generate(root,dest)
            self.assertEqual(out['total_candidates'],3)
            rows=list(csv.DictReader(dest.read_text().splitlines()))
            self.assertTrue(all(not r['reviewed_license'] and not r['split'] for r in rows))
            self.assertEqual(len({r['speaker_id'] for r in rows}),3)
    def test_reject_bad_names(self):
        with self.assertRaises(ValueError):speaker_id(Path('/x/not-librispeech.flac'))

if __name__=='__main__':unittest.main()
