"""自身情绪轨迹预测域（阶段三·包 9b 观察项）。

维护 valence/arousal/energy 的近期 delta 均值与方差；
预测误差作 surprise 旁路信号。复用 body_memory，零新表。
"""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime
from typing import Any

BODY_KEY = "world.emotion_trajectory"
TRACKED_DIMS = ("valence", "arousal", "energy")
_WINDOW = 20
_EPS = 1e-6
_SURPRISE_MAX = 20.0


def _read_dims(emotion: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for dim in TRACKED_DIMS:
        try:
            out[dim] = float(getattr(emotion, dim, 0.0) or 0.0)
        except (TypeError, ValueError):
            out[dim] = 0.0
    return out


def _mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def _std(xs: list[float], mean: float) -> float:
    if len(xs) < 2:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(max(0.0, var))


class EmotionTrajectory:
    """轻量滑动窗口：预测下一拍 delta，偏差即 surprise。"""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._deltas: dict[str, deque[float]] = {
            d: deque(maxlen=_WINDOW) for d in TRACKED_DIMS
        }
        self._loaded = False
        self._last_surprise: dict[str, float] = {d: 0.0 for d in TRACKED_DIMS}
        self._last_predicted: dict[str, float] = {d: 0.0 for d in TRACKED_DIMS}

    async def _ensure_loaded(self, db: Any | None) -> None:
        if self._loaded:
            return
        self._loaded = True
        if db is None:
            return
        raw = await db.get_body_memory(BODY_KEY)
        if not isinstance(raw, dict):
            return
        last = raw.get("last")
        if isinstance(last, dict):
            for dim in TRACKED_DIMS:
                if dim in last:
                    try:
                        self._last[dim] = float(last[dim])
                    except (TypeError, ValueError):
                        pass
        deltas = raw.get("deltas")
        if isinstance(deltas, dict):
            for dim in TRACKED_DIMS:
                seq = deltas.get(dim)
                if isinstance(seq, list):
                    dq: deque[float] = deque(maxlen=_WINDOW)
                    for x in seq[-_WINDOW:]:
                        try:
                            dq.append(float(x))
                        except (TypeError, ValueError):
                            continue
                    self._deltas[dim] = dq

    async def _persist(self, db: Any | None) -> None:
        if db is None:
            return
        payload = {
            "last": dict(self._last),
            "deltas": {d: list(self._deltas[d]) for d in TRACKED_DIMS},
        }
        await db.set_body_memory(BODY_KEY, payload)

    def predict_next(self, dim: str) -> float:
        """基于近期 delta 均值预测下拍方向/量级。"""
        xs = list(self._deltas.get(dim) or [])
        return _mean(xs)

    def surprise(self, dim: str, actual_delta: float) -> float:
        """|actual−mean|/(std+ε)；样本不足则 0。"""
        xs = list(self._deltas.get(dim) or [])
        if len(xs) < 2:
            return 0.0
        mean = _mean(xs)
        std = _std(xs, mean)
        raw = abs(float(actual_delta) - mean) / (std + _EPS)
        return float(min(_SURPRISE_MAX, max(0.0, raw)))

    async def record(self, brain: Any, *, now: datetime) -> dict[str, float]:
        """读 brain.emotion，更新窗口并返回本拍各维 surprise。"""
        del now  # 接口与 OnlineRhythm 对齐；统计不依赖绝对时刻
        db = getattr(brain, "_db", None)
        await self._ensure_loaded(db)
        emotion = getattr(brain, "emotion", None)
        if emotion is None:
            return dict(self._last_surprise)

        current = _read_dims(emotion)
        surprises: dict[str, float] = {}
        predicted: dict[str, float] = {}

        if not self._last:
            # 首拍：只建基线
            self._last = current
            self._last_surprise = {d: 0.0 for d in TRACKED_DIMS}
            self._last_predicted = {d: 0.0 for d in TRACKED_DIMS}
            await self._persist(db)
            return dict(self._last_surprise)

        for dim in TRACKED_DIMS:
            prev = float(self._last.get(dim, current[dim]))
            actual = current[dim] - prev
            # 先用更新前窗口算预测与 surprise，再把本拍 delta 入窗
            pred = self.predict_next(dim)
            surp = self.surprise(dim, actual)
            # 窗口尚短时 surprise()=0；用 |actual−pred| 作可观测弱信号
            if len(self._deltas[dim]) < 2:
                surp = float(min(_SURPRISE_MAX, abs(actual - pred)))
            predicted[dim] = pred
            surprises[dim] = surp
            self._deltas[dim].append(actual)

        self._last = current
        self._last_predicted = predicted
        self._last_surprise = surprises
        await self._persist(db)
        return dict(surprises)

    def snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        del now
        return {
            "tracked_dims": list(TRACKED_DIMS),
            "surprise": {
                d: round(float(self._last_surprise.get(d, 0.0)), 6) for d in TRACKED_DIMS
            },
            "predicted_delta": {
                d: round(float(self._last_predicted.get(d, 0.0)), 6)
                for d in TRACKED_DIMS
            },
        }
