"""M4 source review tests; all signals here are synthetic fixtures."""
import csv
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from m4_corpus_intake import audio_quality
from m4_audio_review import build_report

class M4AudioReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.source = base / "fake.mp3"
        self.source.write_bytes(b"fixture preview bytes")
        self.source_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.wav = base / "test.wav"
        self.save_wav(16000)
        self.registry = base / "registry.csv"
        self.write_registry(self.source_sha)

    def save_wav(self, sr, channels=1, subtype="PCM_16", seconds=5):
        t = np.arange(sr*seconds)/sr
        wave = 0.1*np.sin(2*np.pi*500*t)
        if channels==2:
            wave = np.column_stack((wave,wave))
        sf.write(self.wav,wave,sr,subtype=subtype)

    def write_registry(self, sha):
        cols = ("candidate_id","role","source_dataset","origin_uri","download_uri",
                "expected_sha256","recording_group_id","speaker_id","license_id",
                "license_evidence_uri","reviewed_license","audio_path","split",
                "isolation_review","reviewer","review_note")
        with self.registry.open("w",newline="",encoding="utf-8") as dest:
            writer=csv.DictWriter(dest,fieldnames=cols)
            writer.writeheader()
            writer.writerow({
                "candidate_id":"FS_TEST","role":"target","source_dataset":"fixture",
                "origin_uri":"https://freesound.org/s/117120",
                "download_uri":"https://cdn.freesound.org/previews/117/test.mp3",
                "expected_sha256":sha,"recording_group_id":"a",
                "license_id":"CC-BY-4.0",
                "license_evidence_uri":"https://freesound.org/s/117120"
            })

    def inspect(self, **kw):
        return build_report(registry=self.registry,candidate_id="FS_TEST",
                            source=self.source,wav=self.wav,**kw)

    def test_qc_pass_but_isolation_pending(self):
        sha=hashlib.sha256(self.wav.read_bytes()).hexdigest()
        x=self.inspect(expected_wav_sha256=sha)
        self.assertEqual(x["automatic_qc"],"PASS")
        self.assertEqual(x["corpus_admission"],"NOT_ADMITTED")
        self.assertEqual(x["acoustic_review"]["status"],"PENDING")

    def test_wrong_preview_hash_fails(self):
        self.write_registry("0"*64)
        self.assertIn("SOURCE_HASH_MISMATCH",self.inspect()["automatic_qc_problems"])

    def test_wrong_wav_hash_fails(self):
        self.assertIn("DERIVED_WAV_HASH_MISMATCH",self.inspect(
            expected_wav_sha256="0"*64)["automatic_qc_problems"])

    def test_stereo_fails(self):
        self.save_wav(16000,channels=2)
        self.assertIn("NOT_16KHZ_MONO",self.inspect()["automatic_qc_problems"])

    def test_sample_rate_fails(self):
        self.save_wav(8000)
        self.assertIn("NOT_16KHZ_MONO",self.inspect()["automatic_qc_problems"])

    def test_bit_depth_fails(self):
        self.save_wav(16000,subtype="PCM_24")
        self.assertIn("NOT_WAV_PCM16",self.inspect()["automatic_qc_problems"])

    def test_short_clip_fails(self):
        self.save_wav(16000,seconds=1)
        self.assertIn("AUDIO_QC_SHORTER_THAN_EXPERIMENT_SCENE",
                      self.inspect()["automatic_qc_problems"])

    def test_existing_qc_helper_accepts_string(self):
        self.assertEqual(audio_quality(str(self.wav))["sample_rate_hz"],16000)

    def test_unknown_id_rejected(self):
        with self.assertRaises(ValueError):
            build_report(registry=self.registry,candidate_id="other",
                         source=self.source,wav=self.wav)

if __name__=="__main__":
    unittest.main()
