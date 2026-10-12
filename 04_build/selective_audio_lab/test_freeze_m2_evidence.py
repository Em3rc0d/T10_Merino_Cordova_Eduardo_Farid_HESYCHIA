from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
SCRIPT = ROOT / 'src' / 'freeze_m2_evidence.py'


class FreezeM2EvidenceTests(unittest.TestCase):
    def test_freeze_bundle_is_created_from_real_run_contract(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            run = base / 'run'
            out = base / 'frozen'
            run.mkdir()

            summary = {
                'run_id': 'M2-US8K-BASELINE-001',
                'dataset': 'UrbanSound8K',
                'dataset_rows': 8732,
                'selected_model': 'svm_rbf',
                'test': {'macro_f1': 0.7257233295971242},
                'rnf03_target_macro_f1': 0.85,
                'rnf03_met': False,
                'metadata_sha256': 'a' * 64,
                'selected_model_sha256': 'b' * 64,
            }
            (run / 'semantic_summary.json').write_text(
                json.dumps(summary), encoding='utf-8'
            )
            for name in (
                'validation_models.csv',
                'confusion_matrix_test_fold10.csv',
                'predictions_test_fold10.csv',
                'benchmark_manifest.json',
            ):
                (run / name).write_text('fixture\n', encoding='utf-8')
            (run / 'svm_rbf_selected.joblib').write_bytes(b'fixture-model')

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    '--run-dir', str(run),
                    '--out', str(out),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            result = json.loads(proc.stdout)
            self.assertTrue(result['frozen'])
            self.assertEqual(result['run_id'], 'M2-US8K-BASELINE-001')
            self.assertAlmostEqual(result['test_macro_f1'], 0.7257233295971242)
            self.assertFalse(result['rnf03_met'])
            self.assertTrue(Path(result['archive']).exists())
            bundle = Path(result['bundle_dir'])
            self.assertTrue((bundle / 'FREEZE_MANIFEST.json').exists())


if __name__ == '__main__':
    unittest.main()