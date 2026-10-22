"""HESYCHIA M4 synthetic *engineering* robustness iteration.

Uses HESYCHIA's own 236,833-parameter CNN and previous weights, NOT the event
classifier from any other project. Independent implementation of grouped and
hard-negative stress practices. All sounds are procedural and NOT real audio.

M4 STFT here remains the earlier OFFLINE centered frontend, NOT causal WOLA.
The loss is an exploratory speech-protected surrogate, NOT contractual PI7 L0.
"""
from __future__ import annotations
import os
os.environ['KERAS_BACKEND'] = 'torch'
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import keras
from keras import ops
import numpy as np
from scipy import signal
import soundfile as sf
import torch

from m4_procedural_core import (
    network, build_scene, scene_features, metrics_for_mask, stft,
    SR, FRAMES, SAMPLES, BINS, EPS, TARGET_CLASS
)

# These families are a *development* intervention based on already-observed
# synthetic weaknesses. They are NOT new blind scientific tests.
TRAIN_CASES = (
    'id', 'novel_frequency', 'overlap', 'interference', 'fm_target',
    'pulse_target', 'absent', 'negative_car_alarm', 'negative_reverse_beeper',
    'negative_whistle', 'negative_music_sweep'
)
# PREDECLARED evaluation families for this engineering iteration. Never add to
# training or select/retrain using the evaluation batch outcomes in this run.
EVAL_CASES = (
    'id', 'interference', 'overlap', 'fm_target', 'pulse_target',
    'negative_car_alarm', 'negative_reverse_beeper', 'negative_whistle',
    'ood_dual_target', 'ood_irregular_pulse_target', 'ood_confuser_cluster'
)
TRAIN_SEED_OFFSET = 120_001
VALIDATION_SEED_OFFSET = 220_001
EVAL_SEED_OFFSET = 990_001


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + EPS))


def phase_from_freq(freq):
    return 2 * np.pi * np.cumsum(freq, dtype=np.float64) / SR


def scene(rng: np.random.Generator, family: str):
    """Return mixture, protected, target, interference; target=0 on negatives.

    All random choices derive from passed RNG. The protected signal is a fake
    harmonic voiced surrogate (never call it real speech in a thesis result).
    """
    if family in {'id', 'interference', 'overlap', 'novel_frequency', 'absent'}:
        return build_scene(rng, family)
    t = np.arange(SAMPLES, dtype=np.float64) / SR
    f = float(rng.uniform(175, 360))
    env = .6 + .4 * np.sin(2 * np.pi * float(rng.uniform(1.5, 6)) * t + rng.uniform(-2, 2))**2
    protected = env * (.14*np.sin(2*np.pi*f*t) + .06*np.sin(2*np.pi*2*f*t+.4)
                       + .025*np.sin(2*np.pi*3*f*t+.7))
    if family in {'fm_target', 'pulse_target', 'ood_dual_target', 'ood_irregular_pulse_target'}:
        if family == 'fm_target':
            center = rng.uniform(700, 1500)
            swing = rng.uniform(170, 720)
            tempo = rng.uniform(2.5, 13.0)
            mod = .55 + .45*np.sin(2*np.pi*rng.uniform(2, 9)*t)**2
            inst = center + swing * np.sin(2*np.pi*tempo*t + rng.uniform(0, 6))
            target = np.sin(phase_from_freq(inst)) * mod
        elif family == 'pulse_target':
            freq = np.where(np.sin(2*np.pi*rng.uniform(3, 12)*t)>0,
                            rng.uniform(1200, 2300), rng.uniform(500, 1100))
            target = np.sin(phase_from_freq(freq))
        elif family == 'ood_dual_target':
            first = np.sin(phase_from_freq(700 + 480*np.sin(2*np.pi*6.8*t)))
            second = np.sin(phase_from_freq(1200 + 360*np.sin(2*np.pi*4.2*t+.7)))
            target = (first + .7*second) / 1.7
        else:
            center = rng.uniform(900, 1900)
            # This irregular pulse train is a new, predeclared generator holdout.
            inst = center + 650*np.sin(2*np.pi*(3.8*t + 14*t*t))
            target = np.sin(phase_from_freq(inst)) * (np.sin(2*np.pi*(4.4*t+9*t*t))>-.1)
        target = target * (rms(protected)/(rms(target)+EPS)) * 10**(rng.uniform(-12, 5)/20)
        background = rng.standard_normal(SAMPLES) * rng.uniform(.01, .08)
    else:
        # Explicit absence of target; these are confusers/background, NOT siren.
        target = np.zeros(SAMPLES, dtype=np.float64)
        if family == 'negative_car_alarm':
            f = rng.uniform(300, 650)
            background = (.23*np.sin(2*np.pi*f*t) + .13*np.sin(2*np.pi*2*f*t)) * (
                .25 + .75*(np.sin(2*np.pi*2.2*t)>-.1))
        elif family == 'negative_reverse_beeper':
            f = rng.uniform(900, 1700)
            background = .26*np.sin(2*np.pi*f*t)*(np.sin(2*np.pi*rng.uniform(1,6)*t)>0)
        elif family == 'negative_whistle':
            f = rng.uniform(1200, 3600)
            background = .18*np.sin(phase_from_freq(f + 110*np.sin(2*np.pi*3.2*t)))
        elif family == 'negative_music_sweep':
            f = rng.uniform(350, 1300)
            background = .14*np.sin(phase_from_freq(f + 250*np.sin(2*np.pi*4*t)))
            background += .11*np.sin(phase_from_freq(1.5*f + 150*np.sin(2*np.pi*5*t)))
        elif family == 'ood_confuser_cluster':
            f = rng.uniform(1050, 1800)
            background = .23*np.sin(phase_from_freq(f + 600*np.sin(2*np.pi*4.5*t)))
            background += .20*np.sin(phase_from_freq(1.75*f + 330*np.sin(2*np.pi*6.1*t)))
        else:
            raise ValueError(f'unknown family {family}')
        background = background + rng.standard_normal(SAMPLES) * .013
    return (protected + target + background, protected, target, background)


def dataset(n, seed, cases):
    if n % len(cases) != 0:
        raise ValueError(f'n={n} must be divisible by {len(cases)} scenario families')
    rng = np.random.default_rng(seed)
    x, irm, stems, names, ids = [], [], [], [], []
    for i in range(n):
        family = cases[i % len(cases)]
        s = scene(rng, family)
        features, target_mask = scene_features(s)
        x.append(features)
        irm.append(target_mask)
        stems.append(s)
        names.append(family)
        ids.append(f'proc_v1:{seed}:{i}:{family}')
    if len(set(ids)) != len(ids):
        raise RuntimeError('synthetic identifier collision')
    return (np.stack(x), np.stack(irm), stems, names, ids)


def safe_training_loss(y_true, y_pred):
    """Exploratory voice-protection loss; not PI7 L0.

    y_true concatenates IRM [257] with privileged protected magnitude [257]
    only for TRAINING. This data is never an inference input.
    """
    mask = y_true[..., :BINS]
    protected_mag = y_true[..., BINS:]
    mask_mse = ops.mean(ops.square(y_pred - mask), axis=(1, 2))
    protected_loss = ops.sum(ops.square(y_pred * protected_mag), axis=(1, 2)) / (
        ops.sum(ops.square(protected_mag), axis=(1, 2)) + 1e-7
    )
    return mask_mse + .08 * protected_loss


def labels(n):
    return np.full((n, 1), TARGET_CLASS, dtype=np.int32)


def training_targets(rows):
    x, y, stems, _families, _ids = rows
    clean_protected = np.stack([np.abs(stft(s[1])).T.astype(np.float32) for s in stems])
    return np.concatenate([y, clean_protected], axis=-1)


def audit_model(model, rows, name):
    x, y, stems, families, ids = rows
    predictions = model.predict([x, labels(len(x))], batch_size=64, verbose=0)
    if not np.isfinite(predictions).all() or predictions.min() < 0 or predictions.max() > 1:
        raise AssertionError('invalid predicted masks')
    result = []
    for idx, (p, ref, signal_stems, family, sid) in enumerate(zip(
        predictions, y, stems, families, ids, strict=True
    )):
        metrics = metrics_for_mask(p, signal_stems)
        has_target = metrics['A_target_db'] is not None
        result.append({
            'scene_id': sid, 'index': idx, 'family': family,
            'target_present': has_target, 'model': name,
            'A_target_db': metrics['A_target_db'],
            'A_protected_db': metrics['A_protected_db'],
            'target_ok': bool(metrics['target_ok']),
            'protected_ok': bool(metrics['protected_ok']),
            'joint_ok': bool(metrics['joint_ok']) if has_target else None,
            'mask_mean': float(np.mean(p)),
            'mask_mse': float(np.mean(np.square(p - ref)))
        })
    return result


def summary_by_family(rows):
    out = {}
    for family in sorted(set(x['family'] for x in rows)):
        case = [x for x in rows if x['family'] == family]
        positives = [x for x in case if x['target_present']]
        negatives = len(case) - len(positives)
        out[family] = {
            'n': len(case), 'positive_n': len(positives), 'negative_n': negatives,
            'joint_ok': sum(1 for r in positives if r['joint_ok']),
            'joint_rate': (float(np.mean([r['joint_ok'] for r in positives])) if positives else None),
            'protected_loss_mean_db': float(np.mean([r['A_protected_db'] for r in case])),
            'protected_violation_n': sum(not r['protected_ok'] for r in case),
            'negative_mask_mean': (float(np.mean([r['mask_mean'] for r in case]))
                                   if negatives else None),
            'negative_protected_loss_mean_db':
                (float(np.mean([r['A_protected_db'] for r in case])) if negatives else None),
        }
    return out


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    if args.seed + TRAIN_SEED_OFFSET == args.seed + VALIDATION_SEED_OFFSET:
        raise AssertionError('seed collision')
    torch.set_num_threads(args.threads)
    keras.utils.set_random_seed(args.seed)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    prev = network()
    prev.load_weights(args.previous_weights)
    fresh = network()
    fresh.load_weights(args.previous_weights)
    train = dataset(args.train, args.seed + TRAIN_SEED_OFFSET, TRAIN_CASES)
    val = dataset(args.val, args.seed + VALIDATION_SEED_OFFSET, TRAIN_CASES)
    # Evaluator input built AFTER training. Holdout families never in training.
    start = time.perf_counter()
    fresh.compile(optimizer=keras.optimizers.Adam(learning_rate=args.lr),
                  loss=safe_training_loss)
    history = fresh.fit([train[0], labels(len(train[0]))], training_targets(train),
                        validation_data=([val[0], labels(len(val[0]))], training_targets(val)),
                        batch_size=args.batch, epochs=args.epochs, shuffle=True,
                        verbose=2,
                        callbacks=[keras.callbacks.EarlyStopping(monitor='val_loss',
                            patience=args.patience, restore_best_weights=True)])
    elapsed = time.perf_counter() - start
    checkpoint = output / 'm4_hard_negative.weights.h5'
    fresh.save_weights(checkpoint)
    holdout = dataset(args.test_per_family * len(EVAL_CASES),
                      args.seed + EVAL_SEED_OFFSET, EVAL_CASES)
    a = audit_model(prev, holdout, 'previous')
    b = audit_model(fresh, holdout, 'new')
    pairs = []
    for prev_r, next_r in zip(a, b, strict=True):
        assert prev_r['scene_id'] == next_r['scene_id']
        pairs.append({key: value for key, value in next_r.items() if key != 'model'} |
                     {f'previous_{key}': prev_r[key]
                      for key in ['A_target_db', 'A_protected_db', 'joint_ok', 'mask_mean']})
    with (output / 'paired.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
    with (output / 'learning_curve.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['epoch', 'train_loss', 'val_loss']);w.writeheader()
        w.writerows([{'epoch': k + 1, 'train_loss': float(tr), 'val_loss': float(vl)}
                     for k, (tr, vl) in enumerate(zip(history.history['loss'], history.history['val_loss']))])
    def total(rows):
        positives = [r for r in rows if r['target_present']]
        negatives = [r for r in rows if not r['target_present']]
        return {'n_positive': len(positives),
                'joint_ok': sum(r['joint_ok'] for r in positives),
                'joint_rate': float(np.mean([r['joint_ok'] for r in positives])),
                'n_negative':len(negatives),
                'negative_mask_mean':float(np.mean([r['mask_mean'] for r in negatives])),
                'negative_protected_violation_n':sum(not r['protected_ok'] for r in negatives)}
    # Diagnostics: keep OOD families separate, never hide them in overall mean.
    results = {
        'schema_version': 'hesychia.m4.synthetic_robustness.v1',
        'scope': 'SYNTHETIC_ENGINEERING_ONLY_NOT_REAL_AUDIO_NOT_THESIS_EVIDENCE',
        'trained_families': TRAIN_CASES, 'evaluation_families': EVAL_CASES,
        'previous_checkpoint_sha256': sha(args.previous_weights),
        'new_checkpoint_sha256': sha(checkpoint),
        'train':args.train, 'val':args.val,
        'test_n':len(holdout[0]), 'test_per_family':args.test_per_family,
        'seed': args.seed, 'epochs_completed':len(history.history['loss']),
        'batch_size':args.batch, 'lr':args.lr,
        'training_wall_seconds':elapsed,
        'loss':'MSE mask + 0.08 spectral protected surrogate (NOT PI7 L0)',
        'architecture':'UNCHANGED 3xConv1D 128 d1/2/4, Embedding16, mask257',
        'model_params':fresh.count_params(),
        'old':total(a), 'new':total(b),
        'old_by_family':summary_by_family(a), 'new_by_family':summary_by_family(b),
        'warnings':[
            'Synthetic procedural signals, not sirens or human speech',
            'Previous FM failure already observed and drove training; no blind generalization claim',
            'Evaluation OOD generator is a procedural diagnostic, not untouched acoustic field holdout',
            'Centered offline STFT, NOT a causal streaming frontend',
            'No clinical validation, Android TFLite, real deployment latency or software model certification'
        ]
    }
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    # Synthetic audible example only; no clean source supplied to inference.
    first = 8 * args.test_per_family # index of first OOD dual target from EVAL_CASES
    example = holdout[2][first]
    sf.write(output / 'ood_input.wav', example[0].astype(np.float32), SR)
    mask = fresh.predict([holdout[0][first:first+1], labels(1)], verbose=0)[0]
    processed = metrics_for_mask(mask, example)['output']
    sf.write(output / 'ood_output.wav', processed.astype(np.float32), SR)
    print(json.dumps(results, indent=2), flush=True)
    return results


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-weights', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--train', type=int, default=2200)
    p.add_argument('--val', type=int, default=550)
    p.add_argument('--test-per-family', type=int, default=40)
    p.add_argument('--epochs', type=int, default=18)
    p.add_argument('--patience', type=int, default=5)
    p.add_argument('--batch', type=int, default=32)
    p.add_argument('--lr', type=float, default=.0004)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--threads', type=int, default=2)
    args = p.parse_args()
    run(args)

if __name__ == '__main__':
    cli()
