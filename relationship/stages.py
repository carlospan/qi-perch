"""关系阶段——升档锁定，永不回退。"""

from __future__ import annotations

STAGES = ["stranger", "acquaintance", "friend", "bonded"]

STAGE_THRESHOLDS = {
    "acquaintance": (0.3, 0.4),
    "friend": (0.6, 0.6),
    "bonded": (0.85, 0.8),
}


def check_stage_upgrade(current_stage: str, depth: float, trust: float) -> str:
    """满足条件则升入下一阶段；否则维持。无降级逻辑。"""
    if current_stage not in STAGES:
        current_stage = "stranger"
    idx = STAGES.index(current_stage)
    if idx >= len(STAGES) - 1:
        return current_stage
    next_stage = STAGES[idx + 1]
    min_depth, min_trust = STAGE_THRESHOLDS[next_stage]
    if depth > min_depth and trust > min_trust:
        return next_stage
    return current_stage
