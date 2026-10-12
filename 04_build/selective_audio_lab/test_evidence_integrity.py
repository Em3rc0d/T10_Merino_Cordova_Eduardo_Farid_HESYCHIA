from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from run_demo import run_demo
from validate_artifacts import EvidenceValidationError, validate_run


class EvidenceIntegrityTests(unittest.TestCase):
    def test_validator_accepts_coherent_run(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            summary = run_demo(out, run_id="VALID-RUN-001")
            result = validate_run(out, summary["run_id"])
            self.assertTrue(result["validated"])
            self.assertEqual(result["checksums"], "ok")
            self.assertEqual(result["sqlite"], "coherent")
            self.assertEqual(result["input_assets"], "bound_to_real_sha256")

    def test_validator_detects_artifact_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            summary = run_demo(out, run_id="TAMPER-FILE-001")
            with (out / "mixture.wav").open("ab") as f:
                f.write(b"tamper")
            with self.assertRaises(EvidenceValidationError):
                validate_run(out, summary["run_id"])

    def test_validator_detects_sqlite_metric_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            summary = run_demo(out, run_id="TAMPER-DB-001")
            with sqlite3.connect(out / "evidence.sqlite") as con:
                con.execute(
                    "UPDATE metric SET value=value+1 WHERE run_id=? AND name='A_target_db'",
                    (summary["run_id"],),
                )
            with self.assertRaises(EvidenceValidationError):
                validate_run(out, summary["run_id"])

    def test_validator_detects_input_asset_hash_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            summary = run_demo(out, run_id="TAMPER-ASSET-001")
            with sqlite3.connect(out / "evidence.sqlite") as con:
                con.execute(
                    "UPDATE audio_asset SET checksum=? WHERE role='protected'",
                    ("f" * 64,),
                )
            with self.assertRaises(EvidenceValidationError):
                validate_run(out, summary["run_id"])


if __name__ == "__main__":
    unittest.main()
