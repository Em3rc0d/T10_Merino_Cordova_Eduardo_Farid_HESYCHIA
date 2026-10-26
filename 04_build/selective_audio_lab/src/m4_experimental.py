"""PI9/PI10 engineering CNN. Synthetic-only, offline, not scientific validation.

Torch is deliberately lazy: Oracle and mandatory BLOCK work without DL packages.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

from audio_core import SR, N_FFT, HOP, stft_complex

MODEL_ROOT = Path(__file__).resolve().parents[1] / "models" / "m4_drilling_experimental_v1"
CHECKPOINT = "checkpoint.pt"
MANIFEST = "model_manifest.json"
TARGET_ID = 4  # UrbanSound8K drilling identifier, configured, not inferred by M2.
CONTRACT = "pi9-pi10-drilling-offline-v1"


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_model():
    import torch
    from torch import nn
    from torch.nn import functional as F

    class MaskCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(10, 16)
            self.convs = nn.ModuleList([
                nn.Conv1d(273, 128, 3, dilation=1),
                nn.Conv1d(128, 128, 3, dilation=2),
                nn.Conv1d(128, 128, 3, dilation=4),
            ])
            self.output = nn.Linear(128, 257)

        def forward(self, features, target_id):
            emb = self.embedding(target_id).unsqueeze(1).expand(-1, features.shape[1], -1)
            x = torch.cat((features, emb), dim=-1).transpose(1, 2)
            for layer, dilation in zip(self.convs, (1, 2, 4)):
                x = F.relu(layer(F.pad(x, (2 * dilation, 0))))
            return torch.sigmoid(self.output(x.transpose(1, 2)))

    return MaskCNN()


def inspect_model(model_root=MODEL_ROOT):
    """Verify saved provenance; readiness never implies a scientific pass."""
    root = Path(model_root)
    result = {"state": "unavailable", "ready": False,
              "scientific_validation": "pending", "contract": CONTRACT}
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        if manifest["contract"] != CONTRACT or manifest["target_label"] != "drilling_synthetic":
            raise ValueError("Unsupported model manifest contract/target")
        if manifest["frontend"] != {"sr": SR, "n_fft": N_FFT, "hop": HOP,
                                    "feature": "log1p(20*abs(STFT))", "mode": "offline_centered"}:
            raise ValueError("Incompatible model frontend")
        if file_sha(root / CHECKPOINT) != manifest["checkpoint_sha256"]:
            raise ValueError("Checkpoint SHA-256 mismatch")
        for name, digest in manifest["training_artifacts"].items():
            if name not in ("training_history.json", "training_sources.json"):
                raise ValueError("Unsupported training artifact")
            if file_sha(root / name) != digest:
                raise ValueError("Training artifact SHA-256 mismatch")
        result.update(manifest)
        result["history"] = json.loads((root / "training_history.json").read_text())
        result["manifest_sha256"] = file_sha(root / MANIFEST)
        result["runtime_available"] = importlib.util.find_spec("torch") is not None
        result["ready"] = result["runtime_available"]
        result["state"] = "experimental" if result["ready"] else "runtime_missing"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
    return result


class ExperimentalPredictor:
    def __init__(self, model_root=MODEL_ROOT):
        import torch
        self.root = Path(model_root)
        self.info = inspect_model(self.root)
        if not self.info["ready"]:
            raise ValueError(self.info.get("error", "Experimental model unavailable"))
        # Read once, verify the exact bytes loaded; weights_only avoids arbitrary pickle code.
        import io
        data = (self.root / CHECKPOINT).read_bytes()
        if hashlib.sha256(data).hexdigest() != self.info["checkpoint_sha256"]:
            raise ValueError("Checkpoint changed during load")
        torch.set_num_threads(2)
        self.model = build_model()
        self.model.load_state_dict(torch.load(io.BytesIO(data), map_location="cpu", weights_only=True))
        self.model.eval()

    def predict(self, mixture, target_id):
        """Inputs are the mixture and configured label only. No stems or oracle."""
        import torch
        if target_id != TARGET_ID:
            raise ValueError("Experimental checkpoint supports drilling_synthetic only")
        features = np.log1p(20 * np.abs(stft_complex(mixture)).T).astype(np.float32)
        with torch.inference_mode():
            mask = self.model(torch.from_numpy(features[None]), torch.tensor([target_id]))
        result = mask[0].cpu().numpy().T
        if not np.isfinite(result).all() or np.min(result) < 0 or np.max(result) > 1:
            raise ValueError("Invalid CNN mask")
        return result
