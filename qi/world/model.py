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

    def export_state(self, *, now: datetime | None = None) -> dict[str, Any]:
        """封存用：完整域状态 + 旁路 view。"""
        now = now or datetime.now()
        return {
            "online_rhythm": self.online.export_state(),
            "emotion_trajectory": self.emotion_trajectory.export_state(),
            "view": self.snapshot(now=now),
        }

    def restore(self, data: dict[str, Any] | None) -> None:
        """从 export_state / checkpoint world 块重建内存域。"""
        if not data:
            return
        online = data.get("online_rhythm")
        if isinstance(online, dict):
            # 兼容仅旁路 snapshot（无 buckets）时尽量恢复缓存字段
            if "buckets" in online or "last_bucket" in online:
                self.online.restore(online)
            else:
                self.online._last_predicted = float(
                    online.get("predicted_online") or 0.5
                )
                self.online._last_surprise = float(online.get("surprise") or 0.0)
                self.online._last_bucket = str(online.get("bucket") or "")
                self.online._loaded = True
        traj = data.get("emotion_trajectory")
        if isinstance(traj, dict):
            if "deltas" in traj or "last" in traj:
                self.emotion_trajectory.restore(traj)
            else:
                surp = traj.get("surprise") or {}
                pred = traj.get("predicted_delta") or {}
                if isinstance(surp, dict):
                    self.emotion_trajectory._last_surprise = {
                        k: float(v) for k, v in surp.items()
                    }
                if isinstance(pred, dict):
                    self.emotion_trajectory._last_predicted = {
                        k: float(v) for k, v in pred.items()
                    }
                self.emotion_trajectory._loaded = True
        self.domains = {
            "online_rhythm": self.online,
            "emotion_trajectory": self.emotion_trajectory,
        }
