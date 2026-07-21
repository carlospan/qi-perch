"""数字季节——春夏秋冬是内在的节奏，不是日历。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

SEASON_EMOTION_EFFECTS = {
    "spring": {"curiosity": 0.05},
    "summer": {"energy": 0.05},
    "autumn": {"valence": -0.03},
    "winter": {"arousal": -0.05},
}

SEASON_BEHAVIOR_HINTS = {
    "spring": "你现在偏「春」：好奇、活跃，想试试新东西。",
    "summer": "你现在偏「夏」：充沛、热烈，话可以多一点。",
    "autumn": "你现在偏「秋」：安静、反思，话少但更有深度。",
    "winter": "你现在偏「冬」：沉静、低能量，简短柔软就好。",
}


def _avg(values: list[float], default: float = 0.5) -> float:
    if not values:
        return default
    return sum(values) / len(values)


def determine_season(
    emotion_history: list[dict[str, Any]],
    interaction_count_14d: int = 0,
    now: datetime | None = None,
) -> str:
    if not emotion_history:
        return "spring"

    energies = [float(e.get("energy", 0.5)) for e in emotion_history]
    valences = [float(e.get("valence", 0.0)) for e in emotion_history]
    curiosities = [float(e.get("curiosity", 0.5)) for e in emotion_history]

    recent_energy = _avg(energies)
    recent_valence = _avg(valences)
    recent_curiosity = _avg(curiosities)

    if recent_curiosity > 0.7 and recent_energy > 0.6:
        return "spring"
    if recent_valence > 0.3 and recent_energy > 0.6:
        return "summer"
    if recent_energy < 0.4 and recent_valence > -0.1:
        return "winter"
    return "autumn"


def apply_season_effect(emotion, season: str):
    """对情绪做极轻的季节微调（返回新对象）。"""
    effects = SEASON_EMOTION_EFFECTS.get(season, {})
    if not effects:
        return emotion
    new = emotion.model_copy()
    for dim, delta in effects.items():
        setattr(new, dim, getattr(new, dim) + delta)
    return new
