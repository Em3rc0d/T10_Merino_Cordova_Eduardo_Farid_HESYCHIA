from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from m4_oracle_audit import audit, load_rows


class M4OracleAuditTests(unittest.TestCase):
    def make_csv(self, root: Path, *, duplicate=False, incomplete=False, nan=False):
        path = root / "real_mixture_runs.csv"
        rows = [
            {"mix_id": 0, "cap_db": 12, "A_target_db": 8.0, "A_protected_db": 0.6},
            {"mix_id": 1, "cap_db": 12, "A_target_db": 7.0, "A_protected_db": 1.12},
            {"mix_id": 0, "cap_db": 18, "A_target_db": 8.1, "A_protected_db": 0.5},
            {"mix_id": 1, "cap_db": 18, "A_target_db": 5.0, "A_protected_db": 0.5},
        ]
        if incomplete:
            rows.pop()
        if duplicate:
            rows.append(rows[0].copy())
        if nan:
            rows[0]["A_target_db"] = "nan"
        with path.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_gate_counts_each_mixture_not_only_means(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = audit(self.make_csv(root), root / "out", min_mixtures=2)
            self.assertEqual(summary["evidence_type"], "offline_oracle_known_stems_not_learned_M4")
            self.assertEqual(summary["primary_result"]["target_pass"], 2)
            self.assertEqual(summary["primary_result"]["protected_pass"], 1)
            self.assertEqual(summary["primary_result"]["joint_pass"], 1)
            self.assertEqual(summary["primary_gate"], "NOT_MET_FOR_ALL_MIXTURES")
            self.assertTrue((root / "out" / "m4_oracle_audit_summary.json").exists())
            self.assertTrue((root / "out" / "m4_oracle_per_mix_audit.csv").exists())
            self.assertEqual(summary["by_cap"][1]["joint_fail"], 1)

    def test_default_requires_at_least_100_mixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "al menos 100"):
                audit(self.make_csv(root), root / "out")

    def test_reject_duplicate_and_missing_cap_and_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for config in ({"duplicate": True}, {"incomplete": True}, {"nan": True}):
                with self.subTest(config=config):
                    with self.assertRaises(ValueError):
                        load_rows(self.make_csv(root, **config))

    def test_reject_primary_cap_not_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "No existe cap primario"):
                audit(self.make_csv(root), root / "out", min_mixtures=2, primary_cap_db=24)


if __name__ == "__main__":
    unittest.main()
