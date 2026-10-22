"""Causal STFT frontend shared by HESYCHIA training and blockwise inference.

Engineering contract only. This is not proof of device E2E latency or clinical safety.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

from m4_causal_frontend import CausalWOLA, SR, N_FFT, HOP

EPS = 1e-8
BINS = N_FFT // 2 + 1


class CausalSpectrum:
    """One frame per new HOP samples, no access to future samples."""

    def __init__(self) -> None:
        self.history = np.zeros(N_FFT, dtype=np.float64)
        self.window = np.sqrt(np.hanning(N_FFT + 1)[:-1])

    def push(self, samples: np.ndarray) -> np.ndarray:
        block = np.asarray(samples, dtype=np.float64)
        if block.shape != (HOP,) or not np.isfinite(block).all():
            raise ValueError(f"Expected a finite mono block of {HOP} samples")
        self.history[:-HOP] = self.history[HOP:].copy()
        self.history[-HOP:] = block
        return np.fft.rfft(self.history * self.window).astype(np.complex64)


def frames(x: np.ndarray) -> np.ndarray:
    """Causal analysis [T,257], zero-pad ONLY at end to complete a hop."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim != 1 or len(x) == 0 or not np.isfinite(x).all():
        raise ValueError("Audio must be finite, nonempty and mono")
    x = np.pad(x, (0, -len(x) % HOP))
    frontend = CausalSpectrum()
    return np.stack([frontend.push(block) for block in x.reshape(-1, HOP)])


def features(spectra: np.ndarray) -> np.ndarray:
    """Fixed pointwise compression with NO future/whole-clip normalization."""
    return np.log1p(20.0 * np.abs(spectra)).astype(np.float32)


def ideal_mask(target: np.ndarray, protected: np.ndarray,
               background: np.ndarray) -> np.ndarray:
    """Privileged labels for train/metrics only. Never a runtime input."""
    st = np.abs(frames(target))
    sr = np.abs(frames(protected + background))
    return (st / (st + sr + EPS)).astype(np.float32)


def reconstruct_stream(audio: np.ndarray, gain_for_frame: Callable[[np.ndarray], np.ndarray],
                       *, block_decision: str = "ALLOW") -> np.ndarray:
    """Causal frame analysis -> gain callback -> WOLA, offline replay with state.

    gain_for_frame receives ONLY a current frame's 257 log-compressed bins.
    The callback may keep PAST model state and must not read future audio.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError("Expected finite 1D audio")
    if block_decision not in ("ALLOW", "BLOCK"):
        raise ValueError("Unknown policy decision")
    if len(audio) == 0:
        return audio.copy()
    length = len(audio)
    pad = (-length) % HOP
    padded = np.pad(audio, (0, pad))
    frontend, wola = CausalSpectrum(), CausalWOLA()
    result = np.zeros(length, dtype=np.float32)
    steps = math.ceil(N_FFT / HOP) + 1
    total = padded.reshape(-1, HOP)
    for j in range(len(total) + steps):
        block = total[j] if j < len(total) else np.zeros(HOP, dtype=np.float32)
        sp = frontend.push(block)
        if block_decision == "BLOCK":
            gain = np.ones(BINS, dtype=np.float32)
        else:
            gain = np.asarray(gain_for_frame(features(sp)), dtype=np.float32)
            if gain.shape != (BINS,) or not np.isfinite(gain).all() or np.any((gain < 0) | (gain > 1)):
                raise ValueError("Model gain must contain 257 finite values in [0,1]")
        start, output = wola.push(block, gain)
        l, r = max(start, 0), min(start + HOP, length)
        if l < r:
            result[l:r] = output[l - start:r - start]
    return result


def loss_components(mask_pred, irm, mixture_mag, target_mag, protected_mag,
                    *, speech_weight: float = 0.0):
    """Torch variant of PI7 loss with declared denominator floor for absent targets.

    This stability choice needs prospectively approved ADR before scientific use.
    """
    import torch
    mask_mae = (mask_pred - irm).abs().mean()
    target_mean = target_mag.abs().mean(dim=(1, 2))
    mixture_mean = mixture_mag.abs().mean(dim=(1, 2))
    denominator = torch.maximum(target_mean, mixture_mean * 0.01).clamp_min(1e-4)
    target_mae = (mask_pred * mixture_mag - target_mag).abs().mean(dim=(1, 2))
    target_term = (target_mae / denominator).mean()
    removed = ((1.0 - (1.0 - mask_pred).clamp(min=10 ** (-12 / 20))) * protected_mag).mean(dim=(1, 2))
    preserve = (removed / protected_mag.mean(dim=(1, 2)).clamp_min(1e-4)).mean()
    loss = 0.5 * mask_mae + 0.5 * target_term + speech_weight * preserve
    return loss, dict(mask_mae=mask_mae, target_loss=target_term, protected_penalty=preserve)

class StreamingTorchGain:
    """Stateful M4 causal inference with only last 15 feature frames.

    The 15-frame context is exact for 3 Conv1D kernel=3 dilations 1/2/4.
    This is a correctness baseline; it still recomputes the context per hop.
    """
    def __init__(self, model, *, target_id: int = 8, cap_db: float = 12.0, alpha: float = 1.0):
        if not 0 < cap_db <= 60 or not 0 <= alpha <= 1 or not 0 <= target_id <= 9:
            raise ValueError("invalid frozen target/gain policy")
        self.model = model.eval()
        self.target_id = target_id
        self.floor = 10 ** (-cap_db / 20)
        self.alpha = alpha
        self.context: list[np.ndarray] = []

    def __call__(self, current_features: np.ndarray) -> np.ndarray:
        import torch
        if np.shape(current_features) != (BINS,):
            raise ValueError("expected 257-bin current-frame features")
        self.context.append(np.asarray(current_features, dtype=np.float32).copy())
        if len(self.context) > 15:
            self.context.pop(0)
        x = torch.as_tensor(np.stack(self.context)[None,...], dtype=torch.float32)
        label = torch.as_tensor([self.target_id], dtype=torch.long)
        with torch.no_grad():
            mask = self.model(x, label)[0,-1].cpu().numpy()
        return np.maximum(1.0-self.alpha*mask, self.floor).astype(np.float32)
