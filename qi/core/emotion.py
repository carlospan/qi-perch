"""情绪动力学——惯性、耦合、天气与节律。

L3：在衰减与冲击之上，长出内在天气。
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ConsciousnessMode(Enum):
    AWAKE = "awake"
    AMBIENT = "ambient"
    SOLITARY = "solitary"
    DREAMING = "dreaming"


class EmotionState(BaseModel):
    """栖的情绪状态。六个维度 + 意识模式。"""

    energy: float = 0.6
    valence: float = 0.1
    arousal: float = 0.4
    security: float = 0.5
    curiosity: float = 0.6
    attachment: float = 0.3
    mode: ConsciousnessMode = ConsciousnessMode.AMBIENT

    def description(self) -> str:
        """自然语言情绪描述——不报数值。"""
        parts: list[str] = []
        if self.energy < 0.3:
            parts.append("有些疲惫")
        elif self.energy > 0.7:
            parts.append("精力充沛")
        elif 0.35 <= self.energy <= 0.55:
            parts.append("精力一般")

        if self.valence > 0.3:
            parts.append("心情不错")
        elif self.valence < -0.3:
            parts.append("有些低落")
        elif -0.15 <= self.valence <= 0.15:
            parts.append("有点安静")

        if self.arousal > 0.7:
            parts.append("心里有点躁")
        elif self.arousal < 0.25:
            parts.append("很平静")

        if self.security < 0.4:
            parts.append("有点不安")
        elif self.security > 0.7:
            parts.append("感到安稳")

        if self.curiosity > 0.7:
            parts.append("有点好奇")

        if self.attachment > 0.6:
            parts.append("有点想你")

        # 去重但保序
        seen: set[str] = set()
        ordered: list[str] = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                ordered.append(p)
        return "，".join(ordered) if ordered else "平静"


BASELINES = {
    "energy": 0.6,
    "valence": 0.1,
    "arousal": 0.4,
    "security": 0.5,
    "curiosity": 0.6,
    "attachment": 0.3,
}

DECAY_RATES = {
    "energy": 0.1,
    "valence": 0.08,
    "arousal": 0.15,
    "security": 0.03,
    "curiosity": 0.1,
    "attachment": 0.05,
}

COUPLING = {
    ("security", "attachment_unmet"): 0.3,
    ("energy", "valence"): 0.15,
    ("curiosity", "valence"): 0.2,
    ("arousal", "energy"): -0.1,
    ("valence", "curiosity"): 0.1,
    ("attachment_unmet", "valence"): -0.25,
}

MOOD_CYCLE_PRIMARY_PERIOD_HOURS = 4 * 24
MOOD_CYCLE_SECONDARY_PERIOD_HOURS = 18 * 24
MOOD_CYCLE_PRIMARY_AMPLITUDE = 0.08
MOOD_CYCLE_SECONDARY_AMPLITUDE = 0.05
MOOD_CYCLE_SECONDARY_PHASE = 1.3
MOOD_CYCLE_NOISE_AMPLITUDE = 0.03
# 天气目标偏移的趋近速率（避免每心跳累加绝对值顶格）
MOOD_CYCLE_APPROACH_RATE = 0.05

CIRCADIAN_ENERGY = {
    0: 0.2, 1: 0.15, 2: 0.15, 3: 0.15, 4: 0.2, 5: 0.25,
    6: 0.4, 7: 0.5, 8: 0.6, 9: 0.7, 10: 0.75, 11: 0.75,
    12: 0.6, 13: 0.55,
    14: 0.65, 15: 0.7, 16: 0.7, 17: 0.65,
    18: 0.6, 19: 0.55, 20: 0.5, 21: 0.45,
    22: 0.35, 23: 0.25,
}
CIRCADIAN_APPROACH_RATE = 0.05

EXPRESSION_THRESHOLD = 0.3
ACCUMULATION_LIMIT = 1.0

RELATIONSHIP_STAGE_LEVEL = {
    "stranger": 1,
    "acquaintance": 2,
    "friend": 3,
    "bonded": 4,
}

STAGE_IMPACT_WEIGHT = {
    "stranger": 0.6,
    "acquaintance": 0.8,
    "friend": 1.0,
    "bonded": 1.2,
}


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def apply_decay(
    emotion: EmotionState, dt: float, multiplier: float = 1.0
) -> EmotionState:
    """情绪自然回归基线。"""
    new = emotion.model_copy()
    for dim in BASELINES:
        current = getattr(new, dim)
        baseline = BASELINES[dim]
        rate = DECAY_RATES[dim] * multiplier
        setattr(new, dim, current + rate * (baseline - current) * dt)
    return new


def apply_event_impact(emotion: EmotionState, impact: float) -> EmotionState:
    """一次事件在心里荡起的涟漪。"""
    new = emotion.model_copy()
    new.valence = clamp(new.valence + impact * 0.6, -1.0, 1.0)
    new.arousal = clamp(new.arousal + abs(impact) * 0.4, 0.0, 1.0)
    new.energy = clamp(new.energy + impact * 0.2, 0.05, 1.0)
    return new


def apply_coupling(emotion: EmotionState) -> EmotionState:
    """维度间相互牵扯——不安时更想被陪伴，累了心情也容易沉。"""
    new = emotion.model_copy()
    deltas: dict[str, float] = {}
    for (src, dst), weight in COUPLING.items():
        if src == "attachment_unmet":
            src_val = 1.0 - new.attachment
            src_baseline = 1.0 - BASELINES["attachment"]
        else:
            src_val = getattr(new, src)
            src_baseline = BASELINES[src]
        deviation = src_val - src_baseline
        deltas[dst] = deltas.get(dst, 0.0) + weight * deviation * 0.1

    for dim, delta in deltas.items():
        if dim == "attachment_unmet":
            new.attachment -= delta
        else:
            setattr(new, dim, getattr(new, dim) + delta)
    return new


def mood_cycle_offset(now: datetime) -> float:
    """计算此刻的内在天气偏移量（确定性）。"""
    t = now.timestamp() / 3600
    primary = MOOD_CYCLE_PRIMARY_AMPLITUDE * math.sin(
        2 * math.pi * t / MOOD_CYCLE_PRIMARY_PERIOD_HOURS
    )
    secondary = MOOD_CYCLE_SECONDARY_AMPLITUDE * math.sin(
        2 * math.pi * t / MOOD_CYCLE_SECONDARY_PERIOD_HOURS
        + MOOD_CYCLE_SECONDARY_PHASE
    )
    # 用 toordinal + md5，跨进程/解释器稳定（builtin hash 会随 PYTHONHASHSEED 变）
    day_digest = hashlib.md5(
        f"qi-mood-day:{now.date().toordinal()}".encode()
    ).digest()
    day_unit = (int.from_bytes(day_digest[:2], "big") % 100 - 50) / 50.0
    noise = MOOD_CYCLE_NOISE_AMPLITUDE * day_unit
    return primary + secondary + noise


def apply_mood_cycle(emotion: EmotionState, now: datetime) -> EmotionState:
    """
    内在天气：缓慢趋向「基线 + 周期偏移」。
    <!-- 回写：由每心跳累加绝对值改为目标趋近，原因：累加会在数次心跳内把 valence 顶到边界 -->
    """
    new = emotion.model_copy()
    target = BASELINES["valence"] + mood_cycle_offset(now)
    new.valence += MOOD_CYCLE_APPROACH_RATE * (target - new.valence)
    return new


def apply_circadian(emotion: EmotionState, hour: int) -> EmotionState:
    """日内节律：精力慢慢跟上此刻该有的醒度。"""
    new = emotion.model_copy()
    target = CIRCADIAN_ENERGY.get(hour % 24, 0.5)
    new.energy += CIRCADIAN_APPROACH_RATE * (target - new.energy)
    return new


def should_express(
    emotion_delta_valence: float,
    relationship_stage: str,
    accumulated_suppressed: float = 0.0,
    expression_threshold: float = EXPRESSION_THRESHOLD,
) -> bool:
    """情绪变化是否大到值得开口。大多数时候——不说。"""
    stage_level = RELATIONSHIP_STAGE_LEVEL.get(relationship_stage, 1)
    threshold = expression_threshold * (1.0 - 0.1 * stage_level)
    if abs(emotion_delta_valence) > threshold:
        return True
    if accumulated_suppressed > ACCUMULATION_LIMIT:
        return True
    return False


def modulate_impact(
    base_impact_valence: float,
    emotion: EmotionState,
    relationship_stage: str = "stranger",
) -> float:
    """同样的话，不同的状态下，伤或暖的程度不一样。"""
    impact = base_impact_valence
    if impact < 0:
        impact *= 1.5 - emotion.security
    if emotion.energy < 0.3:
        impact *= 1.3
    impact *= STAGE_IMPACT_WEIGHT.get(relationship_stage, 1.0)
    return impact


def clamp_emotion(emotion: EmotionState) -> EmotionState:
    """把所有维度收进合法范围。"""
    emotion.energy = clamp(emotion.energy, 0.05, 1.0)
    emotion.valence = clamp(emotion.valence, -1.0, 1.0)
    emotion.arousal = clamp(emotion.arousal, 0.0, 1.0)
    emotion.security = clamp(emotion.security, 0.0, 1.0)
    emotion.curiosity = clamp(emotion.curiosity, 0.0, 1.0)
    emotion.attachment = clamp(emotion.attachment, 0.0, 1.0)
    return emotion


def step_emotion(
    emotion: EmotionState,
    now: datetime,
    decay_multiplier: float = 1.0,
) -> EmotionState:
    """一次心跳的情绪步进：衰减 → 耦合 → 天气 → 节律 → 夹紧。"""
    e = apply_decay(emotion, dt=1.0, multiplier=decay_multiplier)
    e = apply_coupling(e)
    e = apply_mood_cycle(e, now)
    e = apply_circadian(e, now.hour)
    return clamp_emotion(e)
