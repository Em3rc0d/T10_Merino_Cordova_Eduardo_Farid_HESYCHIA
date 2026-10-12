from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
SCRIPT = ROOT / 'src' / 'freeze_latency_campaign.py'


class FreezeLatencyCampaignTests(unittest.TestCase):
    def write_batch(self, root: Path, name: str, samples: list[float]):
        d = root / name
        d.mkdir(parents=True)
        with (d / 'latency_samples.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['run', 'elapsed_ms'])
            for i, value in enumerate(samples):
                writer.writerow([i, value])
        ordered = sorted(samples)
        # Values below are sufficient for fixture discovery; campaign recomputes pooled metrics.
        summary = {
            'runs': len(samples),
            'seed': 42,
            'device_label': 'Acer Nitro 5',
            'processing_p50_ms': sum(samples) / len(samples),
            'processing_p95_ms': ordered[-1],
            'processing_mean_ms': sum(samples) / len(samples),
            'measurement_scope': 'whole_clip_processing_only',
        }
        (d / 'latency_summary.json').write_text(
            json.dumps(summary), encoding='utf-8'
        )

    def test_campaign_aggregates_two_matching_batches(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / 'latency'
            out = base / 'campaigns'
            self.write_batch(root, 'A', [10, 11, 12, 13, 14])
            self.write_batch(root, 'B', [20, 21, 22, 23, 24])

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    '--root', str(root),
                    '--out', str(out),
                    '--device-label', 'Acer Nitro 5',
                    '--seed', '42',
                    '--runs-per-batch', '5',
                ],
                capture_output=True, text=True, check=True,
            )
            result = json.loads(proc.stdout)
            self.assertTrue(result['frozen'])
            self.assertEqual(result['batch_count'], 2)
            self.assertEqual(result['total_samples'], 10)
            self.assertTrue(Path(result['archive']).exists())
            self.assertGreater(result['batch_p95_range_ms'], 0)
            self.assertGreater(result['pooled_p95_ms'], result['pooled_p50_ms'])


if __name__ == '__main__':
    unittest.main()