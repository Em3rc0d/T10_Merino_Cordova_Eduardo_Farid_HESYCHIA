"""Prospective M3b policy for the scientific catalogue, preserving S10-A protection."""
from __future__ import annotations

from policy import MANDATORY_PROTECTED, POLICY_VERSION as BASE_POLICY_VERSION

from .corpus import TARGETS

POLICY_VERSION = "M4-SCI-CANDIDATE-1"
PROTECTED = MANDATORY_PROTECTED | frozenset({"clock_alarm", "alert"})


def resolve(target, *, force_block=False, alert_detected=False, target_detected=True):
    """No protected label can become an attenuable target in the candidate branch."""
    if target not in TARGETS and target not in PROTECTED:
        raise ValueError("Unknown scientific candidate/protected target label")
    if force_block or target in PROTECTED:
        decision, reason = "BLOCK", "mandatory_protection"
    elif alert_detected:
        decision, reason = "BLOCK", "protected_alert_present_or_estimated"
    elif not target_detected:
        decision, reason = "BYPASS_TARGET_NOT_DETECTED", "requested_target_not_detected"
    else:
        decision, reason = "ALLOW", "candidate_target_detected_or_assisted"
    return dict(decision=decision, reason=reason, policy_version=POLICY_VERSION,
                base_protection_version=BASE_POLICY_VERSION,
                catalogue_status="PROSPECTIVE_RESEARCH_CANDIDATE")
