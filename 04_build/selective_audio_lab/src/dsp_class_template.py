"""Class-conditioned deterministic DSP baseline for HESYCHIA confirmatory evaluation.

The baseline receives exactly the information allowed to the learned arm at inference:
(1) the mixture waveform and (2) target_id. It never receives clean stems from the test scene.
Class templates are estimated only from the admissible training pool and must be frozen before
unsealing the confirmatory test.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np

from audio_core import EPS, SR, N_FFT, HOP, stft_complex

CONTRACT = "hesychia.dsp-class-template.v1"


def _normalized_psd(x: np.ndarray) -> np.ndarray:
    z = stft_complex(np.asarray(x, dtype=np.float32))
    psd = np.mean(np.abs(z) ** 2, axis=1).astype(np.float64)
    denom = float(np.sum(psd)) + EPS
    return (psd / denom).astype(np.float32)


def fit_class_templates(
    clips_by_class: Mapping[int, Sequence[np.ndarray]],
    *,
    class_ids: Iterable[int] | None = None,
) -> Dict[int, np.ndarray]:
    """Estimate one deterministic spectral-ratio mask per class."""
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
        templates[cid] = np.clip(mask, 0.0, 1.0).astype(np.float32)
    return templates


def save_templates(path: str | Path, templates: Mapping[int, np.ndarray], metadata: Mapping) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {f"class_{int(k)}": np.asarray(v, dtype=np.float32) for k, v in sorted(templates.items())}
    meta = dict(metadata)
    meta.update({
        "contract": CONTRACT,
        "frontend": {"sr": SR, "n_fft": N_FFT, "hop": HOP, "window": "hann"},
        "aggregation": "median_of_per_clip_l1_normalized_mean_psd",
        "mask_formula": "T_c/(T_c+R_c+eps)",
        "test_stems_used": False,
    })
    arrays["metadata_json"] = np.array(json.dumps(meta, ensure_ascii=False, sort_keys=True))
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
        if meta.get("frontend") != {"sr": SR, "n_fft": N_FFT, "hop": HOP, "window": "hann"}:
            raise ValueError("DSP template frontend does not match runtime frontend")
        templates = {
            int(k.split("_", 1)[1]): np.asarray(data[k], dtype=np.float32)
            for k in data.files if k.startswith("class_")
        }
        if not templates:
            raise ValueError("No class templates in baseline artifact")
        return cls(templates=templates, metadata=meta)

    def predict(self, mixture: np.ndarray, target_id: int) -> np.ndarray:
        """Return a test-stem-free mask compatible with the CNN mask contract."""
        if target_id not in self.templates:
            raise ValueError(f"Unsupported target_id={target_id}")
        z = stft_complex(np.asarray(mixture, dtype=np.float32))
        profile = np.asarray(self.templates[target_id], dtype=np.float32)
        if profile.shape != (z.shape[0],):
            raise ValueError("Template frequency dimension mismatch")
        mask = np.repeat(profile[:, None], z.shape[1], axis=1)
        if not np.isfinite(mask).all() or np.min(mask) < 0 or np.max(mask) > 1:
            raise ValueError("Invalid DSP mask")
        return mask.astype(np.float32)
