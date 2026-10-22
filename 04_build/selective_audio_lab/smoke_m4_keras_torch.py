"""Synthetic engineering-only smoke test for HESYCHIA M4 Keras causal CNN.

Not a scientific trial, not trained with real speech or sirens, not streaming,
and not evidence of a safe real-world sound attenuation system.
"""
from __future__ import annotations
import os
os.environ['KERAS_BACKEND'] = 'torch'
import argparse
import json
import platform
from pathlib import Path

import keras
import numpy as np
from scipy import signal
import soundfile as sf
import torch

SR, N_FFT, HOP, FRAMES, BINS = 16000, 512, 160, 32, 257
SAMPLES = (FRAMES - 1) * HOP
EPS = 1e-8


def make_scene(rng, *, include_stems=False):
    t = np.arange(SAMPLES, dtype=np.float32) / SR
    f = float(rng.uniform(180, 250))
    protected = (0.12 * np.sin(2 * np.pi * f * t) +
                 0.06 * np.sin(2 * np.pi * 2 * f * t + 0.2) +
                 0.035 * np.sin(2 * np.pi * 3 * f * t + 0.4))
    sweep_start = float(rng.uniform(700, 950))
    sweep_end = float(rng.uniform(1250, 1650))
    target = (0.22 * signal.chirp(t, f0=sweep_start, f1=sweep_end,
                                  t1=t[-1], method='linear') *
              (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t)))
    noise = rng.standard_normal(SAMPLES) * 0.015
    mixture = protected + target + noise
    # Centered boundary=zeros: this is OFFLINE STFT, not the causal WOLA contract.
    def mag(data):
        return np.abs(signal.stft(data, fs=SR, window='hann', nperseg=N_FFT,
                                  noverlap=N_FFT-HOP, nfft=N_FFT,
                                  boundary='zeros', padded=False)[2])
    xm, tm, rm = mag(mixture), mag(target), mag(protected + noise)
    assert xm.shape == (BINS, FRAMES)
    oracle = tm / (tm + rm + EPS)
    features = np.log1p(20 * xm.T).astype(np.float32)
    label = oracle.T.astype(np.float32)
    if include_stems:
        return features, label, (mixture, protected, target, noise)
    return features, label


def build_model():
    magnitude = keras.Input(shape=(FRAMES, BINS), name='log_mix_mag')
    target = keras.Input(shape=(1,), dtype='int32', name='target_class')
    emb = keras.layers.Embedding(input_dim=10, output_dim=16, name='target_embedding')(target)
    emb = keras.layers.Flatten()(emb)
    emb = keras.layers.RepeatVector(FRAMES)(emb)
    x = keras.layers.Concatenate()([magnitude, emb])
    for dilation in (1, 2, 4):
        x = keras.layers.Conv1D(128, 3, padding='causal', dilation_rate=dilation,
                                activation='relu', name=f'causal_d{dilation}')(x)
    masks = keras.layers.Dense(BINS, activation='sigmoid', name='target_mask')(x)
    return keras.Model([magnitude, target], masks, name='hesychia_m4_smoke')


def run(outdir, epochs=6, n_train=24, n_val=8, seed=42):
    if epochs < 1 or n_train < 2 or n_val < 1:
        raise ValueError('epochs>=1, n_train>=2, n_val>=1 required')
    torch.set_num_threads(2)
    keras.utils.set_random_seed(seed)
    rng = np.random.default_rng(seed)
    scenes = [make_scene(rng) for _ in range(n_train + n_val)]
    x = np.asarray([pair[0] for pair in scenes])
    y = np.asarray([pair[1] for pair in scenes])
    labels = np.full((len(x), 1), 8, dtype=np.int32)  # siren id (single class)
    model = build_model()
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=0.003), loss='mse')
    # IMPORTANT: MSE is a gradient smoke-test objective; this is NOT PI7 L0.
    initial = model.evaluate([x[:n_train], labels[:n_train]], y[:n_train], verbose=0)
    before = [np.copy(v.numpy()) for v in model.trainable_variables]
    hist = model.fit([x[:n_train], labels[:n_train]], y[:n_train],
                     validation_data=([x[n_train:], labels[n_train:]], y[n_train:]),
                     batch_size=8, epochs=epochs, verbose=0, shuffle=True)
    final = model.evaluate([x[:n_train], labels[:n_train]], y[:n_train], verbose=0)
    preds = model.predict([x[n_train:], labels[n_train:]], verbose=0)
    changed = any(not np.array_equal(w, v.numpy()) for w, v in zip(before, model.trainable_variables))
    result = {
        'type': 'synthetic_engineering_smoke_not_scientific_result',
        'platform': platform.platform(), 'keras_version': keras.__version__,
        'backend': keras.backend.backend(), 'torch_version': torch.__version__,
        'device': 'cpu', 'seed': seed, 'train_scenes': n_train, 'val_scenes': n_val,
        'epochs': epochs, 'sample_rate': SR, 'n_fft': N_FFT, 'hop': HOP,
        'frames': FRAMES, 'fft_bins': BINS, 'model_parameters': model.count_params(),
        'training_loss': {'before': float(initial), 'after': float(final)},
        'validation_loss_last': float(hist.history['val_loss'][-1]),
        'finite_prediction': bool(np.isfinite(preds).all()),
        'prediction_in_range': bool(np.min(preds) >= 0 and np.max(preds) <= 1),
        'weights_changed': bool(changed),
        'training_loss_decreased': bool(final < initial),
        'no_stems_input_at_inference': True,
        'limitations': ['toy synthetic sine/chirp stems', 'MSE smoke loss not PI7 L0',
                         'offline STFT not causal/WOLA', 'single target class',
                         'no TFLite export', 'no real-world validation'],
    }
    # Offline audio demo: reconstruct from mixture and model mask, not stems.
    demo_x, _, (demo_mix, _, _, _) = make_scene(
        np.random.default_rng(seed + 101), include_stems=True)
    demo_mask = model.predict(
        [demo_x[None, ...], np.asarray([[8]], dtype=np.int32)], verbose=0
    )[0].T
    _, _, complex_mix = signal.stft(
        demo_mix, fs=SR, window='hann', nperseg=N_FFT,
        noverlap=N_FFT - HOP, nfft=N_FFT, boundary='zeros', padded=False
    )
    gain = np.maximum(1.0 - demo_mask, 10 ** (-12.0 / 20.0))
    _, reconstructed = signal.istft(
        gain * complex_mix, fs=SR, window='hann', nperseg=N_FFT,
        noverlap=N_FFT - HOP, nfft=N_FFT, boundary=True
    )
    if not np.isfinite(reconstructed).all():
        raise AssertionError('Nonfinite reconstructed audio')
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / 'smoke_input.wav', demo_mix.astype(np.float32), SR)
    sf.write(out / 'smoke_output.wav', reconstructed[:len(demo_mix)].astype(np.float32), SR)
    result['offline_audio_reconstruction_finite'] = True
    result['audio_artifacts'] = ['smoke_input.wav', 'smoke_output.wav']
    result['limitations'].append('offline centered Hann/STFT; not streaming causal')
    (out / 'm4_cnn_smoke_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not (changed and result['training_loss_decreased'] and result['finite_prediction'] and result['prediction_in_range']):
        raise AssertionError('CNN gradient smoke FAILED')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', default='outputs/m4_cnn_smoke')
    p.add_argument('--epochs', type=int, default=6)
    p.add_argument('--train-scenes', type=int, default=24)
    p.add_argument('--val-scenes', type=int, default=8)
    args = p.parse_args()
    run(args.out, epochs=args.epochs, n_train=args.train_scenes, n_val=args.val_scenes)
