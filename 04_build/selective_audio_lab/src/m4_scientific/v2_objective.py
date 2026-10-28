"""Differentiable training proxies for class-selective deep-learning attenuation.

Only supervised training may access source stems. The runtime CNN receives
mixture plus requested class. Official acceptance is measured after waveform
reconstruction on independent validation and test scenes, NOT with these proxies.
"""
from __future__ import annotations

import torch
from torch.nn import functional as F


def spectral_attenuation_db(gain, stem, eps=1e-9):
    """Per-sample STFT energy attenuation [B]; silent stems have undefined dB."""
    if gain.shape != stem.shape:
        raise ValueError("Gain/stem shape mismatch")
    energy = stem.abs().square()
    before = energy.sum((-2, -1))
    after = (gain.square() * energy).sum((-2, -1))
    return 10.0 * torch.log10((before + eps) / (after + eps))


def _mean_when(values, valid):
    weights = valid.to(values.dtype)
    return (values * weights).sum() / weights.sum().clamp_min(1.0)


def constrained_selective_loss(model, prediction, batch, cfg, *, swapped_prediction=None):
    """Joint acoustic proxy: target >= 6, voice <= 1, other-class <= 1 dB.

    Add target-absent identity and a correct-vs-swapped-class contrast on the
    same mixture. Reported dB here are spectral proxies, never final RNF metrics.
    """
    for key in ("ideal", "mixture", "target", "protected", "nontarget"):
        if key not in batch:
            raise ValueError(f"V2 missing supervised field: {key}")
        if batch[key].shape != prediction.shape:
            raise ValueError(f"V2 field shape mismatch: {key}")
    if not torch.isfinite(prediction).all() or not all(torch.isfinite(v).all() for v in batch.values()):
        raise ValueError("V2 nonfinite supervised tensor")
    if (prediction < 0).any() or (prediction > 1).any():
        raise ValueError("V2 mask outside [0,1]")

    gain = model.gain(prediction)
    tdb = spectral_attenuation_db(gain, batch["target"])
    vdb = spectral_attenuation_db(gain, batch["protected"])
    ndb = spectral_attenuation_db(gain, batch["nontarget"])
    def present(key):
        return batch[key].abs().square().sum((-2, -1)) > 1e-7
    has_target, has_voice, has_other = present("target"), present("protected"), present("nontarget")
    temp = float(cfg.get("temperature_db", 1.))
    if temp <= 0:
        raise ValueError("temperature_db must be positive")
    target = _mean_when(F.softplus((float(cfg.get("target_db", 6.)) - tdb) / temp) * temp, has_target)
    speech = _mean_when(F.softplus((vdb - float(cfg.get("voice_db", 1.))) / temp) * temp, has_voice)
    other = _mean_when(F.softplus((ndb - float(cfg.get("other_db", 1.))) / temp) * temp, has_other)
    # Target absent: preserve all available sources without guesswork.
    absent = _mean_when(((1. - gain).square() * batch["mixture"].abs().square()).sum((-2, -1)) /
                        batch["mixture"].abs().square().sum((-2, -1)).clamp_min(1e-7), ~has_target)
    mask = (prediction - batch["ideal"]).square().mean()
    class_term = prediction.sum() * 0.
    if float(cfg.get("class_weight", 1.)):
        if swapped_prediction is None or swapped_prediction.shape != prediction.shape:
            raise ValueError("class_weight requires swapped-class prediction")
        swapped_gain = model.gain(swapped_prediction)
        swapped_target = spectral_attenuation_db(swapped_gain, batch["target"])
        swapped_other = spectral_attenuation_db(swapped_gain, batch["nontarget"])
        both = has_target & has_other
        margin = float(cfg.get("class_margin_db", 1.))
        class_term = .5 * (_mean_when(F.softplus((margin - (tdb - swapped_target)) / temp) * temp, both) +
                           _mean_when(F.softplus((margin - (swapped_other - ndb)) / temp) * temp, both))
    defaults = dict(mask=.1, target=1., speech=2., other=1., absent=2., **{"class": 1.})
    weights = {k: float(cfg.get(k + "_weight", d)) for k, d in defaults.items()}
    if any(w < 0 for w in weights.values()):
        raise ValueError("V2 weights must be nonnegative")
    total = (weights["mask"] * mask + weights["target"] * target +
             weights["speech"] * speech + weights["other"] * other +
             weights["absent"] * absent + weights["class"] * class_term)
    return total, dict(mask=mask, target=target, speech=speech, other=other, absent=absent,
                       contrast=class_term, target_db_proxy=_mean_when(tdb, has_target),
                       voice_db_proxy=_mean_when(vdb, has_voice),
                       other_db_proxy=_mean_when(ndb, has_other),
                       eligible_joint_proxy=_mean_when(((tdb >= float(cfg.get("target_db", 6.))) &
                           (vdb <= float(cfg.get("voice_db", 1.)))).to(tdb.dtype), has_target & has_voice))
