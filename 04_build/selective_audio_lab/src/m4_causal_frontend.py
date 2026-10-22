"""WOLA causal de REFERENCIA para design gate M4; no CNN, captura ni latencia E2E."""
from __future__ import annotations
import numpy as np

SR = 16000
N_FFT = 512
HOP = 160
EPS = 1e-10


class CausalWOLA:
    """Consume únicamente el hop actual, entrega segmento y su posición lógica."""
    def __init__(self, n_fft: int = N_FFT, hop: int = HOP):
        if n_fft < hop or hop <= 0 or n_fft % 2:
            raise ValueError("require even n_fft and 0 < hop <= n_fft")
        self.n_fft, self.hop = n_fft, hop
        # Ventana sqrt Hann periódica y normalización por la suma WOLA.
        self.window = np.sqrt(np.hanning(n_fft + 1)[:-1])
        self.history = np.zeros(n_fft)
        self.ola = np.zeros(n_fft)
        self.weight = np.zeros(n_fft)
        self.frames = 0

    def push(self, hop_samples: np.ndarray, gain: np.ndarray | None = None) -> tuple[int, np.ndarray]:
        current = np.asarray(hop_samples, dtype=np.float64)
        if current.ndim != 1 or len(current) != self.hop or not np.isfinite(current).all():
            raise ValueError(f"expected finite mono hop length {self.hop}")
        self.history[:-self.hop] = self.history[self.hop:].copy()
        self.history[-self.hop:] = current
        spectrum = np.fft.rfft(self.history * self.window)
        if gain is not None:
            gain = np.asarray(gain, dtype=np.float64)
            if (gain.shape != spectrum.shape or not np.isfinite(gain).all()
                    or np.min(gain) < 0 or np.max(gain) > 1):
                raise ValueError("expected finite mask in [0,1] of shape (n_fft//2+1,)")
            spectrum *= gain
        self.ola += np.fft.irfft(spectrum, n=self.n_fft) * self.window
        self.weight += self.window ** 2
        block = np.divide(self.ola[:self.hop], self.weight[:self.hop],
                          out=np.zeros(self.hop), where=self.weight[:self.hop] > EPS)
        start = (self.frames + 1) * self.hop - self.n_fft
        self.ola[:-self.hop] = self.ola[self.hop:].copy()
        self.ola[-self.hop:] = 0
        self.weight[:-self.hop] = self.weight[self.hop:].copy()
        self.weight[-self.hop:] = 0
        self.frames += 1
        return start, block.astype(np.float32)


def process_offline_as_stream(audio: np.ndarray,
                              gain: np.ndarray | None = None) -> np.ndarray:
    """Prueba de referencia causal, NO prueba de streaming físico ni de E2E."""
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("mono finite audio required")
    padded = np.pad(x, (0, (-len(x)) % HOP))
    wola = CausalWOLA()
    output = np.zeros(len(x), dtype=np.float32)
    flush = int(np.ceil(N_FFT / HOP)) + 1
    for hop_samples in list(padded.reshape(-1, HOP)) + [np.zeros(HOP)] * flush:
        start, block = wola.push(hop_samples, gain)
        left, right = max(0, start), min(len(x), start + HOP)
        if left < right:
            output[left:right] = block[left - start:right - start]
    return output
