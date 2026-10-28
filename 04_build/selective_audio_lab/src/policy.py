from __future__ import annotations
from dataclasses import dataclass
import math

POLICY_VERSION = "S10A-1.0"
# Exact, explicit labels only: no inference that an unrecognized sound is safe.
MANDATORY_PROTECTED = frozenset({
    "siren_synthetic", "siren", "emergency_siren", "fire_alarm",
    "evacuation_alarm", "car_horn", "vehicle_horn", "warning_horn",
    "speech", "speech_like_synthetic",
})
ATTENUABLE_TARGETS = frozenset({"drilling_synthetic"})
KNOWN_LABELS = MANDATORY_PROTECTED | ATTENUABLE_TARGETS
DEMO_TARGETS = ("drilling_synthetic", "siren_synthetic")

@dataclass(frozen=True)
class PolicyDecision:
    target_label: str
    protected_set: tuple[str, ...]
    cap_db: float
    decision: str
    reason: str

def resolve_policy(
    target_label: str,
    protected_set: list[str] | tuple[str, ...],
    cap_db: float,
) -> PolicyDecision:
    if not isinstance(target_label, str) or target_label not in KNOWN_LABELS:
        raise ValueError("target_label is not in the approved research catalogue")
    if not isinstance(cap_db, (int, float)) or not math.isfinite(cap_db) or cap_db < 0:
        raise ValueError("cap_db must be finite and >= 0")
    if not isinstance(protected_set, (list, tuple)):
        raise ValueError("protected_set must be a list or tuple")
    if any(not isinstance(item, str) or item not in KNOWN_LABELS for item in protected_set):
        raise ValueError("protected_set contains unknown labels")

    # User supplied labels can only add protection; they cannot remove mandatory rules.
    protected = tuple(sorted(set(protected_set) | MANDATORY_PROTECTED))
    if target_label in MANDATORY_PROTECTED:
        decision, reason = "BLOCK", "mandatory_protected_signal"
    elif target_label in protected:
        decision, reason = "BLOCK", "target_is_protected"
    else:
        decision, reason = "ALLOW", "approved_attenuable_target"
    return PolicyDecision(target_label, protected, cap_db, decision, reason)
