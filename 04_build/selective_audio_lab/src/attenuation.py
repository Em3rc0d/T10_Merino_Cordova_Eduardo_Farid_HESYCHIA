from __future__ import annotations
import numpy as np
from audio_core import EPS, SR, N_FFT, HOP, stft_complex, istft_complex, si_sdr
from policy import PolicyDecision

def oracle_irm(target: np.ndarray, rest: np.ndarray) -> np.ndarray:
    s_t = stft_complex(target)
    s_rest = stft_complex(rest)
    mask = np.abs(s_t) / (np.abs(s_t) + np.abs(s_rest) + EPS)
    return np.clip(mask, 0.0, 1.0).astype(np.float32)

def apply_selective_attenuation(
    protected: np.ndarray,
    target: np.ndarray,
    background: np.ndarray,
    policy: PolicyDecision,
    alpha: float = 1.0,
):
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be within [0, 1]")

    raw_mix = protected + target + background
    scale = (np.max(np.abs(raw_mix)) + EPS) / 0.95
    p = protected / scale
    tg = target / scale
    bg = background / scale
    mixture = p + tg + bg

    x = stft_complex(mixture)
    irm = oracle_irm(tg, p + bg)

    if policy.decision == "BLOCK":
        gain = np.ones_like(irm, dtype=np.float32)
        # True digital bypass: no STFT/iSTFT roundtrip on blocked audio.
        output = mixture.copy()
        p_out, tg_out = p.copy(), tg.copy()
    elif policy.decision == "ALLOW":
        g_min = 10 ** (-policy.cap_db / 20.0)
        gain = np.maximum(1.0 - alpha * irm, g_min).astype(np.float32)
        output = istft_complex(gain * x, len(mixture))
        p_out = istft_complex(gain * stft_complex(p), len(p))
        tg_out = istft_complex(gain * stft_complex(tg), len(tg))
    else:
        raise ValueError("Invalid policy decision")

    metrics = {
        "A_target_db": float(
            10 * np.log10((np.sum(tg**2) + EPS) / (np.sum(tg_out**2) + EPS))
        ),
        "A_protected_db": float(
            10 * np.log10((np.sum(p**2) + EPS) / (np.sum(p_out**2) + EPS))
        ),
        "SI_SDRi_protected_db": float(si_sdr(output, p) - si_sdr(mixture, p)),
        "SI_SDRi_target_db": float(si_sdr(output, tg) - si_sdr(mixture, tg)),
        "mask_mean": float(np.mean(irm)),
        "mask_max": float(np.max(irm)),
        "gain_min": float(np.min(gain)),
        "gain_max": float(np.max(gain)),
        "duration_s": float(len(mixture) / SR),
        "sr": SR,
        "n_fft": N_FFT,
        "hop": HOP,
        "policy_decision": policy.decision,
        "policy_reason": policy.reason,
        "target_label": policy.target_label,
        "protected_set": list(policy.protected_set),
        "baseline_type": "oracle_IRM_stem_demo",
    }
    return (
        mixture.astype(np.float32),
        output.astype(np.float32),
        p.astype(np.float32),
        tg.astype(np.float32),
        bg.astype(np.float32),
        irm.astype(np.float32),
        gain.astype(np.float32),
        metrics,
    )
