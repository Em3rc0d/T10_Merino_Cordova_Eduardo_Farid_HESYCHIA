"""Exploratory STFT evidence only; never decide acoustic isolation or corpus admission.

Usage: python src/m4_tonal_screen.py --wav <wav> --expected-sha256 <sha> --out <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import stft

N_FFT = 1024
HOP = 256


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def inspect_wav(path: Path | str, expected_sha256: str = '') -> dict:
    path = Path(path)
    digest = sha256(path)
    if expected_sha256 and digest != expected_sha256.lower():
        raise ValueError('SOURCE_SHA256_MISMATCH')
    info = sf.info(str(path))
    if info.samplerate != 16000 or info.channels != 1 or info.format != 'WAV' or info.subtype != 'PCM_16':
        raise ValueError('NOT_M4_PCM16_MONO_16000')
    y, fs = sf.read(str(path), dtype='float64')
    if len(y) < N_FFT or not np.isfinite(y).all():
        raise ValueError('INVALID_OR_TOO_SHORT_WAV')
    if np.max(np.abs(y)) < 1e-8:
        raise ValueError('SILENT_SIGNAL_CANNOT_HAVE_TONAL_SCREEN')
    freq, time_s, z = stft(y, fs=fs, nperseg=N_FFT, noverlap=N_FFT-HOP, boundary=None)
    power = np.abs(z)**2
    energies = power.sum(axis=0)
    active = energies > .03 * float(energies.max())
    if not np.any(active):
        raise ValueError('NO_ACTIVE_FRAMES')
    power_active = power[:, active]
    flatness = np.exp(np.log(power_active + 1e-15).mean(axis=0)) / (power_active.mean(axis=0) + 1e-15)
    dominant_frequency_hz = freq[np.argmax(power_active, axis=0)]
    return {
        'schema_version': 'hesychia.m4-tonal-screen.v1',
        'file_sha256': digest,
        'sample_rate_hz': fs,
        'channels': 1,
        'subtype': info.subtype,
        'duration_s': round(len(y)/fs, 6),
        'rms': round(float(np.sqrt(np.mean(y*y))), 9),
        'peak_abs': round(float(np.max(np.abs(y))), 9),
        'fraction_near_clip': round(float(np.mean(np.abs(y) >= .999)), 9),
        'stft': {'n_fft': N_FFT, 'hop': HOP, 'window': 'scipy_default_hann',
                 'boundary': None, 'active_rule': 'spectral_energy_gt_3pct_max',
                 'active_frames': int(active.sum()), 'total_frames': int(len(time_s)),
                 'active_interval_s': [round(float(time_s[active][0]), 3), round(float(time_s[active][-1]), 3)],
                 'median_spectral_flatness_active': round(float(np.median(flatness)), 7),
                 'dominant_frequency_hz_5_50_95': [round(float(v), 2) for v in np.percentile(dominant_frequency_hz, [5, 50, 95])]},
        'human_acoustic_review': 'NOT_PERFORMED_BY_THIS_SCRIPT',
        'acoustic_isolation_certification': 'NOT_DETERMINED',
        'corpus_admission': 'NOT_ADMITTED',
        'limitations': ['Spectral flatness and visible harmonics cannot prove source isolation.',
                        'No voice/music/traffic classifier is run.',
                        'Input may be transcoded from a lossy preview.',
                        'This script does not verify external licensing or authenticate a recording origin.']
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--expected-sha256', default='')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = inspect_wav(args.wav, args.expected_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
