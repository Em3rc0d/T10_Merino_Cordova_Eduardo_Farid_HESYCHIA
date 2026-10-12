from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=repo_root, text=True
        ).strip()
    except Exception:
        return None


def load_batch(run_dir: Path) -> dict:
    summary_path = run_dir / 'latency_summary.json'
    samples_path = run_dir / 'latency_samples.csv'
    if not summary_path.exists() or not samples_path.exists():
        raise FileNotFoundError(f'Incomplete latency run: {run_dir}')
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    with samples_path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    samples = [float(row['elapsed_ms']) for row in rows]
    if len(samples) != int(summary.get('runs', -1)):
        raise RuntimeError(f'Sample count mismatch in {run_dir}')
    if summary.get('measurement_scope') != 'whole_clip_processing_only':
        raise RuntimeError(f'Unexpected scope in {run_dir}')
    return {
        'run_dir': run_dir,
        'summary': summary,
        'samples': samples,
        'summary_sha256': sha256(summary_path),
        'samples_sha256': sha256(samples_path),
    }


def main():
    ap = argparse.ArgumentParser(description='Aggregate repeated target-device latency batches')
    ap.add_argument('--root', default='outputs/latency')
    ap.add_argument('--out', default='outputs/latency_campaigns')
    ap.add_argument('--device-label', default='Acer Nitro 5')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--runs-per-batch', type=int, default=40)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    batches = []
    for summary_path in sorted(root.glob('*/latency_summary.json')):
        batch = load_batch(summary_path.parent)
        s = batch['summary']
        if (
            s.get('device_label') == args.device_label
            and int(s.get('seed', -1)) == args.seed
            and int(s.get('runs', -1)) == args.runs_per_batch
        ):
            batches.append(batch)

    if not batches:
        raise RuntimeError('No matching latency batches found')

    pooled = np.asarray(
        [x for batch in batches for x in batch['samples']], dtype=np.float64
    )
    batch_rows = []
    for idx, batch in enumerate(batches, start=1):
        s = batch['summary']
        batch_rows.append({
            'batch': idx,
            'source_dir': batch['run_dir'].name,
            'p50_ms': float(s['processing_p50_ms']),
            'p95_ms': float(s['processing_p95_ms']),
            'mean_ms': float(s['processing_mean_ms']),
            'summary_sha256': batch['summary_sha256'],
            'samples_sha256': batch['samples_sha256'],
        })

    p95_values = [x['p95_ms'] for x in batch_rows]
    campaign = {
        'device_label': args.device_label,
        'seed': args.seed,
        'runs_per_batch': args.runs_per_batch,
        'batch_count': len(batches),
        'total_samples': int(pooled.size),
        'measurement_scope': 'whole_clip_processing_only',
        'pooled_p50_ms': float(np.percentile(pooled, 50)),
        'pooled_p95_ms': float(np.percentile(pooled, 95)),
        'pooled_mean_ms': float(np.mean(pooled)),
        'batch_p95_min_ms': float(min(p95_values)),
        'batch_p95_max_ms': float(max(p95_values)),
        'batch_p95_mean_ms': float(statistics.fmean(p95_values)),
        'batch_p95_range_ms': float(max(p95_values) - min(p95_values)),
        'batches': batch_rows,
        'note': (
            'Repeated-batch campaign on the same target device. Report the pooled '
            'distribution and batch variability; do not cherry-pick the lowest p95. '
            'This still does not represent p95/hop or end-to-end streaming latency.'
        ),
    }

    out_root = Path(args.out).resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    safe_device = ''.join(
        ch if ch.isalnum() else '_' for ch in args.device_label
    ).strip('_') or 'device'
    bundle = out_root / f'LATENCY-CAMPAIGN-{safe_device}_{stamp}'
    bundle.mkdir(parents=True, exist_ok=False)

    (bundle / 'latency_campaign_summary.json').write_text(
        json.dumps(campaign, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    with (bundle / 'latency_campaign_batches.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(batch_rows[0].keys()))
        writer.writeheader()
        writer.writerows(batch_rows)
    with (bundle / 'latency_campaign_samples.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['sample_index', 'elapsed_ms'])
        for idx, value in enumerate(pooled.tolist(), start=1):
            writer.writerow([idx, value])

    repo_root = Path(__file__).resolve().parents[3]
    freeze_manifest = {
        'source_git_commit': git_head(repo_root),
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'campaign_summary_sha256': sha256(bundle / 'latency_campaign_summary.json'),
        'batches_csv_sha256': sha256(bundle / 'latency_campaign_batches.csv'),
        'samples_csv_sha256': sha256(bundle / 'latency_campaign_samples.csv'),
    }
    (bundle / 'FREEZE_MANIFEST.json').write_text(
        json.dumps(freeze_manifest, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    archive = shutil.make_archive(str(bundle), 'zip', root_dir=bundle)

    print(json.dumps({
        'frozen': True,
        'archive': archive,
        **{k: campaign[k] for k in (
            'batch_count','total_samples','pooled_p50_ms','pooled_p95_ms',
            'pooled_mean_ms','batch_p95_min_ms','batch_p95_max_ms','batch_p95_range_ms'
        )},
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()