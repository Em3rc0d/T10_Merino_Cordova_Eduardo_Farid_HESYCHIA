"""Dependency-free audit for a paired HESYCHIA synthetic CNN experiment."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def as_boolean(raw: str) -> bool:
    if raw not in ('True', 'False'):
        raise ValueError(f'invalid boolean: {raw!r}')
    return raw == 'True'


def audit(folder: str | Path) -> dict:
    root = Path(folder)
    result = json.loads((root/'results.json').read_text(encoding='utf-8'))
    with (root/'paired.csv').open(newline='',encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows or len(rows) != result['test_n']:
        raise ValueError('paired file missing or count mismatch')
    if len({r['scene_id'] for r in rows}) != len(rows):
        raise ValueError('scene_id duplicate')
    if sha256(root/'m4_hard_negative.weights.h5') != result['new_checkpoint_sha256']:
        raise ValueError('trained checkpoint hash mismatch')
    totals = {'old': Counter(), 'new': Counter()}
    groups = {'old': {}, 'new': {}}
    negative_count = 0
    for r in rows:
        family = r['family']
        present = as_boolean(r['target_present'])
        for name in ('old','new'):
            group = groups[name].setdefault(family, Counter())
            joint = r['previous_joint_ok'] if name == 'old' else r['joint_ok']
            prefix = 'previous_' if name == 'old' else ''
            if present:
                if joint not in ('True','False'):
                    raise ValueError('present target missing joint flag')
                target = float(r[f'{prefix}A_target_db'])
                protected = float(r[f'{prefix}A_protected_db'])
                if not math.isfinite(target) or not math.isfinite(protected):
                    raise ValueError('invalid dB metric')
                expected = (target >= 6 and protected <= 1)
                if as_boolean(joint) != expected:
                    raise ValueError('joint flag contradicts thresholds')
                totals[name]['positive'] += 1
                group['positive'] += 1
                if expected:
                    totals[name]['success'] += 1
                    group['success'] += 1
            else:
                if joint:
                    raise ValueError('target absent erroneously scored as success')
                group['negative'] += 1
                totals[name]['negative'] += 1
        if not present:
            negative_count += 1
    for name in ('old','new'):
        expected = result[name]
        if (totals[name]['positive'] != expected['n_positive']
            or totals[name]['negative'] != expected['n_negative']
            or totals[name]['success'] != expected['joint_ok']):
            raise ValueError(f'{name} counts disagree with JSON')
        recorded_groups = result[f'{name}_by_family']
        if set(recorded_groups) != set(groups[name]):
            raise ValueError('family list mismatch')
        for key, observed in groups[name].items():
            declared = recorded_groups[key]
            if (observed['positive'] != declared['positive_n']
                or observed['negative'] != declared['negative_n']
                or observed['success'] != declared['joint_ok']):
                raise ValueError(f'inconsistent family {name}/{key}')
    return {
        'status':'PASS', 'evaluated':len(rows), 'positive':totals['new']['positive'],
        'negative':negative_count, 'previous_success':totals['old']['success'],
        'new_success':totals['new']['success'],
        'gain':totals['new']['success']-totals['old']['success'],
        'checkpoint_sha256':result['new_checkpoint_sha256'],
        'caveat':'Synthetic QA audit only, not scientific validation or real audio proof'
    }


def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder',required=True)
    args=p.parse_args()
    print(json.dumps(audit(args.folder),indent=2))

if __name__=='__main__':
    cli()
