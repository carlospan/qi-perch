"""WorldModel：多预测域聚合（包 9 在线节律 + 包 9b 情绪轨迹）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qi.world.emotion_trajectory import EmotionTrajectory
from qi.world.online_rhythm import OnlineRhythm


class WorldModel:
    """内生世界模型入口；update 只读写 body_memory，不依赖 LLM。"""

    def __init__(self) -> None:
        self.online = OnlineRhythm()
        self.emotion_trajectory = EmotionTrajectory()
        self.domains: dict[str, Any] = {
            "online_rhythm": self.online,
            "emotion_trajectory": self.emotion_trajectory,
        }

    async def update(self, brain: Any, *, now: datetime) -> None:
        db = getattr(brain, "_db", None)
        online = bool(getattr(brain, "user_online", False))
        await self.online.record(db, online=online, now=now)
        await self.emotion_trajectory.record(brain, now=now)

    def snapshot(self, *, now: datetime) -> dict[str, Any]:
        return {
            "online_rhythm": self.online.snapshot(now),
            "emotion_trajectory": self.emotion_trajectory.snapshot(now),
        }
