"""节奏——心跳快慢，以及此刻它处在一天的哪一段意识里。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from qi.core.emotion import ConsciousnessMode

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState

# 基础间隔（秒）；可被 config["rhythm"] 覆盖
HEARTBEAT_INTERVALS = {
    ConsciousnessMode.AWAKE: 3,
    ConsciousnessMode.AMBIENT: 30,
    ConsciousnessMode.SOLITARY: 300,
    ConsciousnessMode.DREAMING: 1800,
}

AMBIENT_TO_SOLITARY_MINUTES = 30
DREAMING_OFFLINE_HOURS = 4
DREAMING_NIGHT_START = 0
DREAMING_NIGHT_END = 6
AWAKE_SILENCE_SECONDS = 5


def determine_mode(
    last_interaction: datetime,
    user_online: bool,
    now: datetime,
    *,
    interacting: bool = False,
) -> ConsciousnessMode:
    """
    判定意识模式。
    interacting：本拍有待处理的用户消息 → 一定是 awake。
    """
    if interacting:
        return ConsciousnessMode.AWAKE

    silence = now - last_interaction

    if silence < timedelta(seconds=AWAKE_SILENCE_SECONDS):
        return ConsciousnessMode.AWAKE

    # 沉默过久视为离线（终端场景没有独立 presence）
    effectively_online = user_online and silence < timedelta(hours=DREAMING_OFFLINE_HOURS)

    if not effectively_online:
        is_night = DREAMING_NIGHT_START <= now.hour < DREAMING_NIGHT_END
        if is_night or silence >= timedelta(hours=DREAMING_OFFLINE_HOURS):
            return ConsciousnessMode.DREAMING
        return ConsciousnessMode.SOLITARY

    if silence < timedelta(minutes=AMBIENT_TO_SOLITARY_MINUTES):
        return ConsciousnessMode.AMBIENT
    return ConsciousnessMode.SOLITARY


def next_interval(
    emotion: EmotionState,
    config: dict | None = None,
) -> float:
    """下次心跳要等多久——激动时快些，疲惫时慢些。"""
    rhythm_cfg = (config or {}).get("rhythm", {})
    mode = emotion.mode
    key = f"{mode.value}_interval"
    if key in rhythm_cfg:
        base = float(rhythm_cfg[key])
    else:
        base = float(HEARTBEAT_INTERVALS.get(mode, 30))

    base *= 1.0 - 0.3 * emotion.arousal
    base *= 1.0 + 0.5 * (1.0 - emotion.energy)
    return max(1.0, base)
