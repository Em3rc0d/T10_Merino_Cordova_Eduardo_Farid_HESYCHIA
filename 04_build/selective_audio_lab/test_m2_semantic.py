from __future__ import annotations
import csv
import sys
import tempfile
from pathlib import Path
import unittest

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from semantic_benchmark import run_benchmark
from urbansound8k import (
    EXPECTED_CLASSES,
    assert_no_leakage,
    load_metadata,
    split_metadata,
    validate_contract,
)

class SemanticBenchmarkTests(unittest.TestCase):
    def make_fixture(self, root: Path):
        (root / "metadata").mkdir(parents=True)
        rows = []
        sr = 16000
        duration = 0.35
        t = np.arange(int(sr * duration)) / sr

        # Two official classes are enough to exercise the full fold/selection contract.
        classes = [(0, EXPECTED_CLASSES[0], 260.0), (8, EXPECTED_CLASSES[8], 980.0)]
        for fold in range(1, 11):
            fold_dir = root / "audio" / f"fold{fold}"
            fold_dir.mkdir(parents=True)
            for j, (class_id, class_name, freq) in enumerate(classes):
                fsid = fold * 1000 + class_id + 1
                filename = f"{fsid}-{class_id}-0-0.wav"
                y = 0.7 * np.sin(2 * np.pi * (freq + fold) * t)
                y += 0.02 * np.sin(2 * np.pi * (freq * 0.5) * t)
                sf.write(fold_dir / filename, y.astype(np.float32), sr)
                rows.append({
                    "slice_file_name": filename,
                    "fsID": fsid,
                    "start": 0.0,
                    "end": duration,
                    "salience": 1,
                    "fold": fold,
                    "classID": class_id,
                    "class": class_name,
                })

        with (root / "metadata" / "UrbanSound8K.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "slice_file_name","fsID","start","end","salience","fold","classID","class"
            ])
            writer.writeheader()
            writer.writerows(rows)

    def test_dataset_contract_and_benchmark_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "UrbanSound8K"
            self.make_fixture(root)

            report = validate_contract(
                root, require_official_shape=False, verify_audio=True
            )
            self.assertEqual(report.rows, 20)
            self.assertEqual(report.folds, tuple(range(1, 11)))
            self.assertEqual(report.missing_audio, 0)
            self.assertTrue(report.occurrence_fold_consistency_ok)
            self.assertEqual(report.cross_fold_fsid_count, 0)

            out = Path(td) / "out"
            summary = run_benchmark(
                root, out, seed=42, require_official_shape=False
            )
            self.assertEqual(summary["dataset"], "UrbanSound8K")
            self.assertEqual(summary["no_leakage_check"], "labeled_occurrence_passed")
            self.assertIn(summary["selected_model"], {"svm_rbf", "random_forest"})
            self.assertTrue((out / "semantic_summary.json").exists())
            self.assertTrue((out / "validation_models.csv").exists())
            self.assertTrue((out / "confusion_matrix_test_fold10.csv").exists())
            self.assertTrue((out / "predictions_test_fold10.csv").exists())
            self.assertTrue(any(out.glob("*_selected.joblib")))
            self.assertTrue((out / "benchmark_manifest.json").exists())
            self.assertEqual(summary["split_counts"], {
                "train": 16,
                "validation": 2,
                "test": 2,
            })
            self.assertEqual(set(summary["fold_counts"]), {str(i) for i in range(1, 11)})
            self.assertEqual(len(summary["metadata_sha256"]), 64)
            self.assertEqual(len(summary["selected_model_sha256"]), 64)
            self.assertIn("fixed holdout protocol", summary["protocol_note"])
            self.assertGreaterEqual(summary["test"]["macro_f1"], 0.5)

    def test_cross_fold_fsid_across_classes_is_diagnostic_not_blocking(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "UrbanSound8K"
            self.make_fixture(root)
            metadata = root / "metadata" / "UrbanSound8K.csv"
            with metadata.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            victim = rows[-1]  # fold10, class 8: deliberately different class
            old_name = victim["slice_file_name"]
            victim["fsID"] = rows[0]["fsID"]
            victim["slice_file_name"] = (
                f"{rows[0]['fsID']}-{victim['classID']}-0-99.wav"
            )
            old_path = root / "audio" / "fold10" / old_name
            new_path = root / "audio" / "fold10" / victim["slice_file_name"]
            if old_path.exists():
                old_path.rename(new_path)
            with metadata.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "slice_file_name","fsID","start","end",
                        "salience","fold","classID","class"
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            report = validate_contract(
                root, require_official_shape=False, verify_audio=True
            )
            self.assertTrue(report.occurrence_fold_consistency_ok)
            self.assertGreater(report.cross_fold_fsid_count, 0)
            self.assertTrue(report.cross_fold_fsid_cross_class_only)

            df = load_metadata(root)
            train, val, test = split_metadata(df)
            assert_no_leakage(train, val, test)

    def test_same_labeled_occurrence_across_folds_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "UrbanSound8K"
            self.make_fixture(root)
            metadata = root / "metadata" / "UrbanSound8K.csv"
            with metadata.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            # Force the same (fsID,classID,occurrenceID) into fold 10 while
            # keeping a distinct sliceID.
            source = rows[0]
            victim = rows[-2]
            old_name = victim["slice_file_name"]
            victim["fsID"] = source["fsID"]
            victim["classID"] = source["classID"]
            victim["class"] = source["class"]
            victim["slice_file_name"] = (
                f"{source['fsID']}-{source['classID']}-0-99.wav"
            )
            old_path = root / "audio" / "fold10" / old_name
            new_path = root / "audio" / "fold10" / victim["slice_file_name"]
            old_path.rename(new_path)

            with metadata.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "slice_file_name","fsID","start","end",
                        "salience","fold","classID","class"
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            report = validate_contract(
                root, require_official_shape=False, verify_audio=True
            )
            self.assertFalse(report.occurrence_fold_consistency_ok)
            self.assertGreater(report.cross_fold_occurrence_count, 0)

            df = load_metadata(root)
            train, val, test = split_metadata(df)
            with self.assertRaisesRegex(ValueError, "labeled-occurrence leakage"):
                assert_no_leakage(train, val, test)

if __name__ == "__main__":
    unittest.main()
