"""用户在线节律：按 (weekday, hour) 桶的贝塔后验预测。

持久化复用 body_memory（key=world.online_rhythm），零 schema 改动。
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

BODY_KEY = "world.online_rhythm"
_ALPHA = 1.0
_BETA = 1.0
_EPS = 1e-6
_SURPRISE_MAX = 20.0


def _bucket_key(now: datetime) -> str:
    return f"{now.weekday()}_{now.hour}"


class OnlineRhythm:
    """计数 + 拉普拉斯平滑贝塔后验；预测误差作世界模型 surprise。"""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, int]] = {}
        self._loaded = False
        self._last_surprise: float = 0.0
        self._last_predicted: float = 0.5
        self._last_bucket: str = ""

    async def _ensure_loaded(self, db: Any | None) -> None:
        if self._loaded:
            return
        self._loaded = True
        if db is None:
            return
        raw = await db.get_body_memory(BODY_KEY)
        if isinstance(raw, dict):
            buckets = raw.get("buckets")
            if isinstance(buckets, dict):
                cleaned: dict[str, dict[str, int]] = {}
                for k, v in buckets.items():
                    if not isinstance(v, dict):
                        continue
                    cleaned[str(k)] = {
                        "s": int(v.get("s", 0) or 0),
                        "f": int(v.get("f", 0) or 0),
                    }
                self._buckets = cleaned

    async def _persist(self, db: Any | None) -> None:
        if db is None:
            return
        await db.set_body_memory(BODY_KEY, {"buckets": self._buckets})

    def _counts(self, now: datetime) -> tuple[int, int]:
        cell = self._buckets.get(_bucket_key(now)) or {}
        return int(cell.get("s", 0) or 0), int(cell.get("f", 0) or 0)

    def predict(self, now: datetime) -> float:
        """P(在线 | 当前桶) = (α+s)/(α+β+n)；无样本 → 0.5。"""
        s, f = self._counts(now)
        n = s + f
        if n == 0:
            return 0.5
        return (_ALPHA + s) / (_ALPHA + _BETA + n)

    def surprise(self, online: bool, now: datetime) -> float:
        """对数预测误差：基于更新前的 predict。"""
        p = self.predict(now)
        p = min(1.0 - _EPS, max(_EPS, p))
        raw = -math.log(p) if online else -math.log(1.0 - p)
        return float(min(_SURPRISE_MAX, max(0.0, raw)))

    async def record(self, db: Any | None, *, online: bool, now: datetime) -> float:
        """先算 surprise，再对当前桶 s/f +1 并持久化；返回本拍 surprise。"""
        await self._ensure_loaded(db)
        predicted = self.predict(now)
        surp = self.surprise(online, now)
        key = _bucket_key(now)
        cell = self._buckets.setdefault(key, {"s": 0, "f": 0})
        if online:
            cell["s"] = int(cell.get("s", 0)) + 1
        else:
            cell["f"] = int(cell.get("f", 0)) + 1
        self._last_predicted = predicted
        self._last_surprise = surp
        self._last_bucket = key
        await self._persist(db)
        return surp

    def snapshot(self, now: datetime) -> dict[str, Any]:
        """旁路字段：优先用最近一次 record 的预测/惊喜；否则现算预测。"""
        bucket = self._last_bucket or _bucket_key(now)
        if self._last_bucket:
            predicted = self._last_predicted
            surp = self._last_surprise
        else:
            predicted = self.predict(now)
            surp = 0.0
        return {
            "predicted_online": round(float(predicted), 6),
            "surprise": round(float(surp), 6),
            "bucket": bucket,
        }
