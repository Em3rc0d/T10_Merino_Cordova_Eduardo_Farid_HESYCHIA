from __future__ import annotations
import numpy as np
from scipy.signal import stft, istft, chirp

SR = 16000
DURATION = 4.0
N_FFT = 512
HOP = 160
EPS = 1e-9

def synthesize(seed: int = 42):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * DURATION)) / SR
    envelope = 0.45 + 0.35 * np.sin(2 * np.pi * 2.2 * t) ** 2
    protected = envelope * (
        0.30 * np.sin(2 * np.pi * 180 * t)
        + 0.15 * np.sin(2 * np.pi * 360 * t)
        + 0.07 * np.sin(2 * np.pi * 720 * t)
    )
    target = (
        0.35
        * chirp(t, f0=650, f1=1450, t1=0.8, method="linear")
        * (0.5 + 0.5 * np.sin(2 * np.pi * 1.25 * t))
    )
    noise = rng.normal(0, 0.04, len(t))
    background = np.convolve(noise, np.ones(9) / 9, mode="same")
    return (
        protected.astype(np.float32),
        target.astype(np.float32),
        background.astype(np.float32),
    )

def stft_complex(x: np.ndarray) -> np.ndarray:
    _, _, z = stft(
        x,
        fs=SR,
        window="hann",
        nperseg=N_FFT,
        noverlap=N_FFT - HOP,
        nfft=N_FFT,
        boundary="zeros",
    )
    return z

def istft_complex(z: np.ndarray, length: int) -> np.ndarray:
    _, y = istft(
        z,
        fs=SR,
        window="hann",
        nperseg=N_FFT,
        noverlap=N_FFT - HOP,
        nfft=N_FFT,
        input_onesided=True,
        boundary=True,
    )
    if len(y) < length:
        y = np.pad(y, (0, length - len(y)))
    return y[:length].astype(np.float32)

def si_sdr(est: np.ndarray, ref: np.ndarray) -> float:
    est = est - np.mean(est)
    ref = ref - np.mean(ref)
    scale = np.dot(est, ref) / (np.dot(ref, ref) + EPS)
    s_target = scale * ref
    e_noise = est - s_target
    return float(
        10
        * np.log10(
            (np.sum(s_target**2) + EPS) / (np.sum(e_noise**2) + EPS)
        )
    )
