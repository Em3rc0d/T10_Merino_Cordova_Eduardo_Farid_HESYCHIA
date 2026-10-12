from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REQUIRED = ('latency_summary.json', 'latency_samples.csv')


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


def resolve_run_dir(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    base = Path('outputs/latency').resolve()
    candidates = [
        p.parent for p in base.glob('*/latency_summary.json') if p.is_file()
    ]
    if not candidates:
        raise FileNotFoundError('No latency run found under outputs/latency')
    return max(candidates, key=lambda p: (p / 'latency_summary.json').stat().st_mtime)


def main():
    ap = argparse.ArgumentParser(description='Freeze target-device latency evidence')
    ap.add_argument('--run-dir', default=None)
    ap.add_argument('--out', default='outputs/latency_frozen')
    args = ap.parse_args()

    run_dir = resolve_run_dir(args.run_dir)
    out_root = Path(args.out).resolve()
    missing = [name for name in REQUIRED if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError('Missing latency evidence: ' + ', '.join(missing))

    summary = json.loads((run_dir / 'latency_summary.json').read_text(encoding='utf-8'))
    if summary.get('measurement_scope') != 'whole_clip_processing_only':
        raise RuntimeError('Unexpected latency measurement scope')
    if int(summary.get('runs', 0)) < 5:
        raise RuntimeError('Latency run count is too small')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    safe_device = ''.join(
        ch if ch.isalnum() else '_' for ch in summary.get('device_label', 'device')
    ).strip('_') or 'device'
    bundle = out_root / f'LATENCY-{safe_device}_{stamp}'
    bundle.mkdir(parents=True, exist_ok=False)

    copied = []
    for name in REQUIRED:
        src = run_dir / name
        dst = bundle / name
        shutil.copy2(src, dst)
        copied.append(dst)

    repo_root = Path(__file__).resolve().parents[3]
    manifest = {
        'device_label': summary.get('device_label'),
        'runs': summary.get('runs'),
        'seed': summary.get('seed'),
        'measurement_scope': summary.get('measurement_scope'),
        'processing_p50_ms': summary.get('processing_p50_ms'),
        'processing_p95_ms': summary.get('processing_p95_ms'),
        'processing_mean_ms': summary.get('processing_mean_ms'),
        'source_git_commit': git_head(repo_root),
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'files': [
            {'name': p.name, 'sha256': sha256(p), 'bytes': p.stat().st_size}
            for p in copied
        ],
    }
    (bundle / 'FREEZE_MANIFEST.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    archive = shutil.make_archive(str(bundle), 'zip', root_dir=bundle)
    print(json.dumps({
        'frozen': True,
        'bundle_dir': str(bundle),
        'archive': archive,
        'device_label': manifest['device_label'],
        'p50_ms': manifest['processing_p50_ms'],
        'p95_ms': manifest['processing_p95_ms'],
        'mean_ms': manifest['processing_mean_ms'],
        'scope': manifest['measurement_scope'],
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()