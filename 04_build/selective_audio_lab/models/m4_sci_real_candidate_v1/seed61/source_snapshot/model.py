"""Small causal, class-conditioned mask CNN. No time-global normalization."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

SR, N_FFT, HOP, BINS = 16000, 512, 160, 257
LEFT = N_FFT - HOP
TAIL = int(np.ceil(LEFT / HOP))


def spectrum(wave):
    """Past-anchored frames including a declared zero tail for complete synthesis."""
    if wave.ndim == 1:
        wave = wave[None]
    if wave.ndim != 2 or wave.shape[-1] < 1 or not torch.isfinite(wave).all():
        raise ValueError("Expected finite nonempty [batch,samples]")
    padded = F.pad(wave, (LEFT, (-wave.shape[-1]) % HOP + TAIL * HOP))
    window = torch.hann_window(N_FFT, device=wave.device, dtype=wave.dtype).sqrt()
    return torch.fft.rfft(padded.unfold(-1, N_FFT, HOP) * window, dim=-1)


def synthesize(spec, length):
    """WOLA reference for scientific offline evaluation; no physical latency claim."""
    window = torch.hann_window(N_FFT, device=spec.device, dtype=spec.real.dtype).sqrt()
    frames = torch.fft.irfft(spec, n=N_FFT, dim=-1) * window
    width = (spec.shape[-2] - 1) * HOP + N_FFT
    kwargs = dict(output_size=(1, width), kernel_size=(1, N_FFT), stride=(1, HOP))
    out = F.fold(frames.transpose(1, 2), **kwargs)[:, 0, 0]
    weight = F.fold(window.square()[None, :, None].expand(1, -1, spec.shape[-2]),
                    **kwargs)[0, 0, 0]
    return (out / weight.clamp_min(1e-8))[:, LEFT:LEFT + length]


def features(spec):
    return torch.log1p(20. * spec.abs())


@dataclass(frozen=True)
class ModelConfig:
    channels: int = 96
    classes: int = 2
    dilations: tuple = (1, 2, 4, 8)
    embedding: int = 24
    cap_db: float = 12.
    architecture: str = "temporal"


class ResidualBlock(nn.Module):
    def __init__(self, channels, embedding, dilation):
        super().__init__()
        self.dilation = dilation
        self.conv = nn.Conv1d(channels, channels, 3, dilation=dilation)
        # Per-frame channel normalization is causal; BatchNorm over time is excluded.
        self.norm = nn.LayerNorm(channels)
        self.film = nn.Linear(embedding, channels * 2)
        self.project = nn.Conv1d(channels, channels, 1)

    def forward(self, x, embedding):
        y = self.conv(F.pad(x, (2 * self.dilation, 0))).transpose(1, 2)
        scale, bias = self.film(embedding).chunk(2, dim=-1)
        y = F.silu(self.norm(y) * (1 + .1 * scale[:, None]) + bias[:, None])
        return x + .5 * self.project(y.transpose(1, 2))


class MaskCNN(nn.Module):
    def __init__(self, config=ModelConfig()):
        super().__init__()
        self.config = config
        self.embedding = nn.Embedding(config.classes, config.embedding)
        self.input = nn.Conv1d(BINS, config.channels, 1)
        self.blocks = nn.ModuleList(ResidualBlock(config.channels, config.embedding, d)
                                    for d in config.dilations)
        self.mask_head = nn.Conv1d(config.channels, BINS, 1)
        nn.init.constant_(self.mask_head.bias, -1.5)

    @property
    def receptive_frames(self):
        return 1 + 2 * sum(self.config.dilations)

    def forward(self, x, labels):
        emb = self.embedding(labels)
        z = F.silu(self.input(x.transpose(1, 2)))
        for block in self.blocks:
            z = block(z, emb)
        return torch.sigmoid(self.mask_head(z)).transpose(1, 2)

    def gain(self, mask):
        return (1. - mask).clamp_min(10 ** (-self.config.cap_db / 20))


class SpectralBlock(nn.Module):
    """Local frequency patterns and strictly past temporal context, separable CNN."""
    def __init__(self, channels, embedding, dilation):
        super().__init__()
        self.dilation = dilation
        self.depthwise = nn.Conv2d(channels, channels, (5, 3),
                                   dilation=(1, dilation), groups=channels)
        self.mix = nn.Conv2d(channels, channels, 1)
        self.norm = nn.LayerNorm(channels)
        self.film = nn.Linear(embedding, channels * 2)

    def forward(self, x, embedding):
        y = self.depthwise(F.pad(x, (2 * self.dilation, 0, 2, 2)))
        y = self.norm(y.permute(0, 2, 3, 1))
        scale, bias = self.film(embedding).chunk(2, dim=-1)
        y = F.silu(y * (1 + .1 * scale[:, None, None]) + bias[:, None, None])
        return x + .5 * self.mix(y.permute(0, 3, 1, 2))


class SpectralCNN(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.embedding = nn.Embedding(config.classes, config.embedding)
        self.input = nn.Conv2d(1, config.channels, (5, 1), padding=(2, 0))
        self.blocks = nn.ModuleList(SpectralBlock(config.channels, config.embedding, d)
                                    for d in config.dilations)
        # Global spectral context is computed independently for EACH frame.
        self.global_context = nn.Linear(BINS, config.channels)
        self.head = nn.Conv2d(config.channels, 1, 1)
        nn.init.constant_(self.head.bias, -1.5)

    @property
    def receptive_frames(self):
        return 1 + 2 * sum(self.config.dilations)

    def forward(self, x, labels):
        embedding = self.embedding(labels)
        z = F.silu(self.input(x.transpose(1, 2)[:, None]))
        context = self.global_context(x).transpose(1, 2)[:, :, None]
        z = z + .1 * context
        for block in self.blocks:
            z = block(z, embedding)
        return torch.sigmoid(self.head(z)[:, 0].transpose(1, 2))

    def gain(self, mask):
        return (1. - mask).clamp_min(10 ** (-self.config.cap_db / 20))


def build_model(config):
    if config.architecture == "temporal":
        return MaskCNN(config)
    if config.architecture == "spectral":
        return SpectralCNN(config)
    raise ValueError("Unknown CNN architecture")


def frontend_contract():
    return dict(sample_rate=SR, n_fft=N_FFT, hop=HOP, bins=BINS,
                window="sqrt-periodic-Hann", left_padding=LEFT, tail_hops=TAIL,
                feature="log1p(20*abs(STFT))", normalization="fixed-pointwise",
                model_lookahead_frames=0, synthesis="normalized-WOLA-offline-reference")


def load_checkpoint(path):
    obj = torch.load(path, map_location="cpu", weights_only=True)
    if obj["frontend"] != frontend_contract():
        raise ValueError("Checkpoint frontend incompatible")
    cfg = ModelConfig(**obj["model_config"])
    model = build_model(cfg)
    model.load_state_dict(obj["state_dict"], strict=True)
    return model.eval(), obj
