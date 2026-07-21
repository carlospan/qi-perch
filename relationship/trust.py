"""信任动力学——建立慢，损伤快，修复靠持续正向。"""

from __future__ import annotations

TRUST_GROWTH_RANGE = (0.02, 0.05)
TRUST_DAMAGE_RANGE = (0.1, 0.3)
TRUST_DAILY_DECAY = 0.001
TRUST_HEALED_SCAR_BONUS = 0.01
SCAR_CREATION_THRESHOLD = 0.15


def apply_positive_interaction(trust: float, quality: float) -> float:
    quality = max(0.0, min(1.0, quality))
    growth = TRUST_GROWTH_RANGE[0] + quality * (
        TRUST_GROWTH_RANGE[1] - TRUST_GROWTH_RANGE[0]
    )
    return min(1.0, trust + growth)


def apply_negative_event(trust: float, severity: float) -> tuple[float, bool]:
    severity = max(0.0, min(1.0, severity))
    damage = TRUST_DAMAGE_RANGE[0] + severity * (
        TRUST_DAMAGE_RANGE[1] - TRUST_DAMAGE_RANGE[0]
    )
    new_trust = max(0.0, trust - damage)
    return new_trust, damage > SCAR_CREATION_THRESHOLD


def apply_daily_decay(trust: float, had_interaction: bool) -> float:
    if not had_interaction:
        return max(0.0, trust - TRUST_DAILY_DECAY)
    return trust


def apply_scar_healed_bonus(trust: float) -> float:
    return min(1.0, trust + TRUST_HEALED_SCAR_BONUS)
