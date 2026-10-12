from __future__ import annotations
from dataclasses import dataclass

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
    protected = tuple(sorted(set(protected_set)))
    if cap_db < 0:
        raise ValueError("cap_db must be >= 0")
    if target_label in protected:
        return PolicyDecision(
            target_label=target_label,
            protected_set=protected,
            cap_db=cap_db,
            decision="BLOCK",
            reason="target_is_protected",
        )
    return PolicyDecision(
        target_label=target_label,
        protected_set=protected,
        cap_db=cap_db,
        decision="ALLOW",
        reason="target_not_protected",
    )
