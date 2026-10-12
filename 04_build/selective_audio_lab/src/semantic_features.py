from __future__ import annotations
from pathlib import Path
import numpy as np
import librosa

SR = 16000
N_MFCC = 20
N_MELS = 64
N_FFT = 512
HOP = 160
DURATION_S = 4.0
RESAMPLE_TYPE = "soxr_hq"
FEATURE_DIM = 2 * N_MFCC + 2 * N_MELS

def load_audio(path: str | Path) -> np.ndarray:
    y, _ = librosa.load(
        str(path),
        sr=SR,
        mono=True,
        duration=DURATION_S,
        res_type=RESAMPLE_TYPE,
    )
    target_len = int(SR * DURATION_S)
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]
    peak = float(np.max(np.abs(y)))
    if peak > 0:
        y = y / peak
    return y.astype(np.float32)

def extract_features(path: str | Path) -> np.ndarray:
    y = load_audio(path)
    mfcc = librosa.feature.mfcc(
        y=y, sr=SR, n_mfcc=N_MFCC, n_fft=N_FFT, hop_length=HOP, n_mels=N_MELS
    )
    mel = librosa.feature.melspectrogram(
        y=y, sr=SR, n_fft=N_FFT, hop_length=HOP, n_mels=N_MELS, power=2.0
    )
    logmel = librosa.power_to_db(mel + 1e-12, ref=np.max)

    # Fixed-size summary for classical baselines.
    feat = np.concatenate([
        mfcc.mean(axis=1),
        mfcc.std(axis=1),
        logmel.mean(axis=1),
        logmel.std(axis=1),
    ])
    if not np.isfinite(feat).all():
        raise ValueError(f"Non-finite feature vector for {path}")
    return feat.astype(np.float32)
