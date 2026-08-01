"""信任动力学——建立慢，损伤快，修复靠持续正向；近顶软增速 + 无交互日向阶段舒适区回归。"""

from __future__ import annotations

TRUST_GROWTH_RANGE = (0.02, 0.05)
TRUST_DAMAGE_RANGE = (0.1, 0.3)
TRUST_DAILY_DECAY = 0.001
TRUST_DAILY_DRIFT = 0.015
TRUST_HEALED_SCAR_BONUS = 0.01
SCAR_CREATION_THRESHOLD = 0.15
# 近顶软增速地板：避免完全锁死，仍显著慢于低信任
TRUST_SOFT_FLOOR = 0.15

# 生人慢、熟人可略快——简化版 consistency（不追踪「说到做到」）
STAGE_TRUST_GROWTH = {
    "stranger": 0.5,
    "acquaintance": 0.7,
    "friend": 1.0,
    "bonded": 1.0,
}

# 无交互日均值回归目标——对齐 stages.STAGE_THRESHOLDS 入门门槛附近 / RelationshipState 初值
STAGE_TRUST_COMFORT = {
    "stranger": 0.5,  # RelationshipState 默认
    "acquaintance": 0.55,  # 略高于入门 trust 0.4
    "friend": 0.70,  # 略高于入门 trust 0.6
    "bonded": 0.85,  # 对齐入门 trust 0.8 附近
}


def stage_trust_factor(stage: str) -> float:
    return STAGE_TRUST_GROWTH.get(stage, 1.0)


def soft_ceiling_factor(value: float, floor: float = TRUST_SOFT_FLOOR) -> float:
    """越近 1.0 增速越小；value∈[0,1]。"""
    return max(floor, 1.0 - max(0.0, min(1.0, value)))


def apply_positive_interaction(
    trust: float,
    quality: float,
    *,
    stage: str = "friend",
) -> float:
    """
    正向交互加信任。quality∈[0,1] 插值增长率；
    stage 再乘阶段系数（stranger 更慢）；近顶软增速防顶格锁死。
    """
    quality = max(0.0, min(1.0, quality))
    growth = TRUST_GROWTH_RANGE[0] + quality * (
        TRUST_GROWTH_RANGE[1] - TRUST_GROWTH_RANGE[0]
    )
    growth *= stage_trust_factor(stage)
    growth *= soft_ceiling_factor(trust)
    return min(1.0, trust + growth)


def apply_negative_event(trust: float, severity: float) -> tuple[float, bool]:
    severity = max(0.0, min(1.0, severity))
    damage = TRUST_DAMAGE_RANGE[0] + severity * (
        TRUST_DAMAGE_RANGE[1] - TRUST_DAMAGE_RANGE[0]
    )
    new_trust = max(0.0, trust - damage)
    return new_trust, damage > SCAR_CREATION_THRESHOLD


def apply_daily_decay(
    trust: float,
    had_interaction: bool,
    *,
    stage: str = "stranger",
) -> float:
    """
    无交互日：微衰 + 向阶段信任舒适区均值回归。
    有交互日：不改（正交互路径另有软增速）。
    """
    if had_interaction:
        return trust
    t = max(0.0, trust - TRUST_DAILY_DECAY)
    comfort = STAGE_TRUST_COMFORT.get(stage, STAGE_TRUST_COMFORT["stranger"])
    t = t + TRUST_DAILY_DRIFT * (comfort - t)
    return max(0.0, min(1.0, t))


def apply_scar_healed_bonus(trust: float) -> float:
    return min(1.0, trust + TRUST_HEALED_SCAR_BONUS)
