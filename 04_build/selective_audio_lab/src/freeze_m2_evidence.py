from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REQUIRED = (
    'semantic_summary.json',
    'validation_models.csv',
    'confusion_matrix_test_fold10.csv',
    'predictions_test_fold10.csv',
    'benchmark_manifest.json',
)


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


def main():
    ap = argparse.ArgumentParser(description='Freeze real M2 evidence bundle')
    ap.add_argument('--run-dir', default='outputs/m2_urbansound8k')
    ap.add_argument('--out', default='outputs/m2_frozen')
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    out_root = Path(args.out).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)

    missing = [name for name in REQUIRED if not (run_dir / name).exists()]
    model_files = sorted(run_dir.glob('*_selected.joblib'))
    if missing:
        raise FileNotFoundError('Missing M2 evidence: ' + ', '.join(missing))
    if len(model_files) != 1:
        raise RuntimeError(
            f'Expected exactly one selected model, found {len(model_files)}'
        )

    summary = json.loads((run_dir / 'semantic_summary.json').read_text(encoding='utf-8'))
    if int(summary.get('dataset_rows', -1)) != 8732:
        raise RuntimeError('semantic_summary.json is not the full official dataset run')
    if summary.get('selected_model') != 'svm_rbf':
        raise RuntimeError('Unexpected selected model for frozen 2026-10-12 baseline')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    bundle = out_root / f'M2-US8K-BASELINE-001_{stamp}'
    bundle.mkdir(parents=True, exist_ok=False)

    files = [run_dir / name for name in REQUIRED] + model_files
    copied = []
    for src in files:
        dst = bundle / src.name
        shutil.copy2(src, dst)
        copied.append(dst)

    repo_root = Path(__file__).resolve().parents[3]
    manifest = {
        'run_id': summary.get('run_id'),
        'dataset': summary.get('dataset'),
        'dataset_rows': summary.get('dataset_rows'),
        'selected_model': summary.get('selected_model'),
        'test_macro_f1': summary.get('test', {}).get('macro_f1'),
        'rnf03_target_macro_f1': summary.get('rnf03_target_macro_f1'),
        'rnf03_met': summary.get('rnf03_met'),
        'metadata_sha256': summary.get('metadata_sha256'),
        'selected_model_sha256': summary.get('selected_model_sha256'),
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
        'run_id': manifest['run_id'],
        'test_macro_f1': manifest['test_macro_f1'],
        'rnf03_met': manifest['rnf03_met'],
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()