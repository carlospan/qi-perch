"""learning-progress 好奇信号（轻量代理，零重依赖）。

合成世界模型 surprise + open_loop 积压 + 情绪层 curiosity（含 anomaly），
写回 emotion.curiosity，并可作为 GWS 竞争者入场（contender 入场已回退，2026-08-08，见解堵包）。

动机加成每拍重算：先剥去上拍加成再叠本拍信号，避免 curiosity 单调顶满。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qi.core.emotion import clamp
from qi.core.trace import Contender

_DEFAULT_W_WORLD = 0.5
_DEFAULT_W_LOOP = 0.3
_OPEN_LOOP_CAP = 5.0
_BOOST_ATTR = "_curiosity_motive_boost"


class CuriositySignal:
    """每拍更新 curiosity；不依赖 LLM。"""

    def __init__(self, config: dict | None = None) -> None:
        cfg = ((config or {}).get("motivation") or {}).get("curiosity") or {}
        self.w_world = float(cfg.get("w_world", _DEFAULT_W_WORLD))
        self.w_loop = float(cfg.get("w_loop", _DEFAULT_W_LOOP))
        self._last_value = 0.0

    async def update(self, brain: Any, *, now: datetime) -> float:
        """计算本拍 curiosity 并写回 brain.emotion.curiosity。"""
        del now  # 接口预留；代理信号暂不依赖绝对时刻

        prev_boost = float(getattr(brain, _BOOST_ATTR, 0.0) or 0.0)
        raw = float(getattr(brain.emotion, "curiosity", 0.6) or 0.0)
        intrinsic = clamp(raw - prev_boost, 0.0, 1.0)

        surprise = 0.0
        world = getattr(brain, "last_world", None)
        if isinstance(world, dict):
            rhythm = world.get("online_rhythm") or {}
            try:
                surprise = float(rhythm.get("surprise") or 0.0)
            except (TypeError, ValueError):
                surprise = 0.0

        loop_n = 0
        try:
            loops = await brain._load_open_loops()
            loop_n = len(loops)
        except Exception:
            loop_n = 0
        loop_norm = min(1.0, float(loop_n) / _OPEN_LOOP_CAP)

        # surprise 常见 0~约 3；压到 0–1 再加权
        surprise_n = clamp(surprise / 3.0, 0.0, 1.0)
        boost = self.w_world * surprise_n + self.w_loop * loop_norm
        value = clamp(intrinsic + boost, 0.0, 1.0)

        setattr(brain, _BOOST_ATTR, boost)
        brain.emotion.curiosity = value
        self._last_value = value
        return value

    def salience(self, curiosity: float | None = None) -> float:
        v = self._last_value if curiosity is None else float(curiosity)
        return clamp(v, 0.0, 1.0)

    def contender(self, *, now: datetime | None = None) -> Contender:
        del now
        return Contender(
            kind="curiosity",
            salience=self.salience(),
            reason="learning-progress 好奇",
        )
