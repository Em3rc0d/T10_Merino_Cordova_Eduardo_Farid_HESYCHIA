"""Standalone offline candidate inference, known target and explicit BLOCK priority."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf
import torch

from .common import sha256, write_json
from .corpus import TARGETS, SR
from .model import features, load_checkpoint, spectrum, synthesize
from .policy import resolve


def predict_wave(audio, checkpoint, target, *, block_protected=False,
                 event_checkpoint=None, event_calibration=None):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Expected finite nonempty mono audio")
    policy = resolve(target, force_block=block_protected)
    # Precedence is mandatory, including when weights are missing or corrupt.
    if policy["decision"] == "BLOCK":
        return audio.copy(), {**policy, "model_called": False}
    event_meta = {}
    if bool(event_checkpoint) != bool(event_calibration):
        raise ValueError("Both event checkpoint and validation calibration are required")
    if event_checkpoint is not None:
        from .events import EVENTS, load_events
        detector, calibration = load_events(event_checkpoint, event_calibration)
        with torch.no_grad():
            probs = torch.sigmoid(detector(features(spectrum(torch.from_numpy(audio)))))[0].numpy()
        event_meta = dict(event_probabilities=dict(zip(EVENTS, (float(v) if np.isfinite(v) else None for v in probs))),
                          event_thresholds=calibration["thresholds"],
                          event_checkpoint_sha256=sha256(event_checkpoint))
        if not np.isfinite(probs).all():
            return audio.copy(), dict(decision="BLOCK", reason="nonfinite_event_prediction",
                                       model_called=False, **event_meta)
        index = TARGETS.index(target)
        policy = resolve(target, alert_detected=probs[3] >= calibration["thresholds"][3],
                         target_detected=probs[index] >= calibration["thresholds"][index])
        if policy["decision"] != "ALLOW":
            return audio.copy(), dict(model_called=False, **policy, **event_meta)
    model, obj = load_checkpoint(checkpoint)
    label = 0 if obj["config"].get("conditioning") == "none" else TARGETS.index(target)
    torch.set_num_threads(4)
    with torch.no_grad():
        spec = spectrum(torch.from_numpy(audio))
        gain = model.gain(model(features(spec), torch.tensor([label])))
        if not torch.isfinite(gain).all():
            raise ValueError("Nonfinite model gain; inference aborted")
        output = synthesize(spec * gain, len(audio))[0].numpy()
        if not np.isfinite(output).all():
            raise ValueError("Nonfinite reconstructed audio; inference aborted")
    return output, dict(**policy, model_called=True,
                        checkpoint_sha256=sha256(checkpoint), target=target,
                        mode="offline_integrated_requested_target" if event_checkpoint else "offline_assisted_target",
                        automatic_alert_detection=bool(event_checkpoint),
                        automatic_safety_validated=False, **event_meta)


def predict_file(checkpoint, source, output, target, *, block_protected=False,
                 event_checkpoint=None, event_calibration=None):
    source, output = Path(source), Path(output)
    if output.resolve() == source.resolve() or output.exists():
        raise ValueError("Refusing to overwrite input/existing audio")
    audio, rate = sf.read(source, dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if rate != SR:
        gcd = math.gcd(rate, SR)
        audio = scipy.signal.resample_poly(audio, SR // gcd, rate // gcd).astype(np.float32)
    result, meta = predict_wave(audio, checkpoint, target, block_protected=block_protected,
                                event_checkpoint=event_checkpoint, event_calibration=event_calibration)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, result, SR, subtype="FLOAT")
    meta.update(input_sha256=sha256(source), output_sha256=sha256(output),
                input_sample_rate=rate, output_sample_rate=SR, samples=len(result),
                resampled=rate != SR,
                note="BLOCK preserves decoded mono/resampled audio. Estimated alert detection, when enabled, "
                     "is an experimental offline gate with measured errors, not validated personal protection.")
    write_json(output.with_suffix(".json"), meta)
    return meta
