"""信任动力学——建立慢，损伤快，修复靠持续正向。"""

from __future__ import annotations

TRUST_GROWTH_RANGE = (0.02, 0.05)
TRUST_DAMAGE_RANGE = (0.1, 0.3)
TRUST_DAILY_DECAY = 0.001
TRUST_HEALED_SCAR_BONUS = 0.01
SCAR_CREATION_THRESHOLD = 0.15

# 生人慢、熟人可略快——简化版 consistency（不追踪「说到做到」）
STAGE_TRUST_GROWTH = {
    "stranger": 0.5,
    "acquaintance": 0.7,
    "friend": 1.0,
    "bonded": 1.0,
}


def stage_trust_factor(stage: str) -> float:
    return STAGE_TRUST_GROWTH.get(stage, 1.0)


def apply_positive_interaction(
    trust: float,
    quality: float,
    *,
    stage: str = "friend",
) -> float:
    """
    正向交互加信任。quality∈[0,1] 插值增长率；
    stage 再乘阶段系数（stranger 更慢）。
    """
    quality = max(0.0, min(1.0, quality))
    growth = TRUST_GROWTH_RANGE[0] + quality * (
        TRUST_GROWTH_RANGE[1] - TRUST_GROWTH_RANGE[0]
    )
    growth *= stage_trust_factor(stage)
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
