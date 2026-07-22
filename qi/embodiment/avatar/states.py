"""Avatar 状态定义。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Posture(str, Enum):
    IDLE = "idle"
    TALKING = "talking"
    THINKING = "thinking"
    HAPPY = "happy"
    SLEEPING = "sleeping"


class Expression(str, Enum):
    NEUTRAL = "neutral"
    SOFT_SMILE = "soft_smile"
    HAPPY = "happy"
    QUIET = "quiet"
    SURPRISED = "surprised"
    SLEEPY = "sleepy"
    CURIOUS = "curious"


class Effect(str, Enum):
    NONE = "none"
    DREAM_BUBBLES = "dream_bubbles"
    THINKING_SPARKLES = "thinking_sparkles"
    SEASON_LEAVES = "season_leaves"
    SNOW = "snow"


class AvatarState(BaseModel):
    posture: Posture = Posture.IDLE
    expression: Expression = Expression.NEUTRAL
    effect: Effect = Effect.NONE

    def to_dict(self) -> dict:
        return {
            "posture": self.posture.value,
            "expression": self.expression.value,
            "effect": self.effect.value,
        }
