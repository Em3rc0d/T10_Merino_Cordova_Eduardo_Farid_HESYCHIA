"""Class-conditioned deterministic DSP baseline for HESYCHIA confirmatory evaluation.

Fairness contract:
- CNN and DSP receive only the mixture waveform + target_id at inference.
- Neither method receives clean confirmatory-test stems.
- DSP uses the EXACT scientific M4 frontend/synthesis geometry.
- Class templates are fitted only from the admissible training pool.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import torch

try:
    from .m4_scientific.model import (
        BINS,
        HOP,
        N_FFT,
        SR,
        frontend_contract,
        spectrum,
    )
except ImportError:  # direct module use from selective_audio_lab root
    from m4_scientific.model import (
        BINS,
        HOP,
        N_FFT,
        SR,
        frontend_contract,
        spectrum,
    )

EPS = 1e-9
CONTRACT = "hesychia.dsp-class-template.v2"


def _scientific_spectrum(x: np.ndarray) -> torch.Tensor:
    wave = torch.from_numpy(np.asarray(x, dtype=np.float32))
    if wave.ndim != 1 or wave.numel() < 1 or not torch.isfinite(wave).all():
        raise ValueError("Expected finite nonempty mono waveform")
    return spectrum(wave)[0]  # [frames, bins], exact M4 scientific frontend


def _normalized_psd(x: np.ndarray) -> np.ndarray:
    spec = _scientific_spectrum(x)
    psd = spec.abs().square().mean(dim=0).cpu().numpy().astype(np.float64)
    denom = float(np.sum(psd)) + EPS
    return (psd / denom).astype(np.float32)


def fit_class_templates(
    clips_by_class: Mapping[int, Sequence[np.ndarray]],
    *,
    class_ids: Iterable[int] | None = None,
) -> Dict[int, np.ndarray]:
    """Estimate one deterministic spectral-ratio mask per target class."""
    ids = sorted(class_ids if class_ids is not None else clips_by_class.keys())
    profiles: Dict[int, list[np.ndarray]] = {}
    for cid in ids:
        clips = clips_by_class.get(cid, ())
        if not clips:
            raise ValueError(f"No training clips for class_id={cid}")
        profiles[cid] = [_normalized_psd(x) for x in clips]

    templates: Dict[int, np.ndarray] = {}
    for cid in ids:
        target = np.median(np.stack(profiles[cid], axis=0), axis=0)
        rest_profiles = [p for other in ids if other != cid for p in profiles[other]]
        if not rest_profiles:
            raise ValueError("At least two target classes are required")
        rest = np.median(np.stack(rest_profiles, axis=0), axis=0)
        mask = target / (target + rest + EPS)
        mask = np.clip(mask, 0.0, 1.0).astype(np.float32)
        if mask.shape != (BINS,):
            raise ValueError("Template bins differ from scientific frontend")
        templates[cid] = mask
    return templates


def save_templates(
    path: str | Path,
    templates: Mapping[int, np.ndarray],
    metadata: Mapping,
) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        f"class_{int(k)}": np.asarray(v, dtype=np.float32)
        for k, v in sorted(templates.items())
    }
    meta = dict(metadata)
    meta.update(
        {
            "contract": CONTRACT,
            "frontend": frontend_contract(),
            "aggregation": "median_of_per_clip_l1_normalized_mean_power_spectrum",
            "mask_formula": "T_c/(T_c+R_c+eps)",
            "temporal_behavior": "static_frequency_mask_broadcast_over_scientific_frames",
            "test_stems_used": False,
        }
    )
    arrays["metadata_json"] = np.array(
        json.dumps(meta, ensure_ascii=False, sort_keys=True)
    )
    np.savez_compressed(path, **arrays)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ClassTemplateDSP:
    templates: Mapping[int, np.ndarray]
    metadata: Mapping

    @classmethod
    def from_npz(cls, path: str | Path) -> "ClassTemplateDSP":
        data = np.load(Path(path), allow_pickle=False)
        meta = json.loads(str(data["metadata_json"].item()))
        if meta.get("contract") != CONTRACT:
            raise ValueError("Unsupported DSP baseline contract")
        if meta.get("frontend") != frontend_contract():
            raise ValueError("DSP template frontend does not match scientific M4 frontend")
        templates = {
            int(k.split("_", 1)[1]): np.asarray(data[k], dtype=np.float32)
            for k in data.files
            if k.startswith("class_")
        }
        if not templates:
            raise ValueError("No class templates in baseline artifact")
        if any(v.shape != (BINS,) for v in templates.values()):
            raise ValueError("DSP template frequency dimension mismatch")
        return cls(templates=templates, metadata=meta)

    def predict(self, mixture: np.ndarray, target_id: int) -> np.ndarray:
        """Return [frames,bins] mask on exactly the same STFT grid as M4 CNN."""
        if target_id not in self.templates:
            raise ValueError(f"Unsupported target_id={target_id}")
        spec = _scientific_spectrum(mixture)
        profile = np.asarray(self.templates[target_id], dtype=np.float32)
        mask = np.repeat(profile[None, :], spec.shape[0], axis=0)
        if (
            mask.shape != (spec.shape[0], BINS)
            or not np.isfinite(mask).all()
            or np.min(mask) < 0
            or np.max(mask) > 1
        ):
            raise ValueError("Invalid DSP mask")
        return mask.astype(np.float32)

    @staticmethod
    def gain(mask: np.ndarray, cap_db: float = 12.0) -> np.ndarray:
        """Use the same mask-to-gain rule as the M4 model."""
        floor = 10 ** (-float(cap_db) / 20.0)
        return np.maximum(1.0 - np.asarray(mask, dtype=np.float32), floor).astype(
            np.float32
        )
