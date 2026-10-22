from __future__ import annotations
import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from m4_data_gate import audit_registry


class M4DataGateTests(unittest.TestCase):
    def registry(self, root, *, leak=False, pseudo=False, corrupt=False):
        rows = []
        for split in ("train", "val", "test"):
            for role in ("target", "protected", "background"):
                sid = f"{split}_{role}"
                wav = root / f"{sid}.wav"
                wav.write_bytes(sid.encode())
                digest = hashlib.sha256(wav.read_bytes()).hexdigest()
                if corrupt and split == "val" and role == "target":
                    digest = "0" * 64
                rows.append(dict(source_id=sid, role=role, split=split,
                                 recording_id=("cross" if leak and role == "target" else sid),
                                 speaker_id=(f"speaker-{split}" if role == "protected" else ""),
                                 path=wav.name, sha256=digest, license="CC BY 4.0",
                                 reference_grade=("pseudo_stem" if pseudo and role == "target" else
                                                  "isolated" if role == "target" else
                                                  "speech" if role == "protected" else "background")))
        path = root / "registry.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_pass_with_disjoint_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            self.assertEqual("PASS", audit_registry(self.registry(d))["status"])

    def test_block_cross_split_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            self.assertEqual("BLOCKED", audit_registry(self.registry(d, leak=True))["status"])

    def test_block_pseudo_as_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            source = self.registry(d, pseudo=True)
            self.assertEqual("BLOCKED", audit_registry(source)["status"])
            self.assertEqual("PASS", audit_registry(source, strict_isolated=False)["status"])

    def test_reject_changed_sha256(self):
        with tempfile.TemporaryDirectory() as folder:
            d = Path(folder)
            self.assertEqual("BLOCKED", audit_registry(self.registry(d, corrupt=True))["status"])
