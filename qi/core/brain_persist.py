"""Brain 持久化片段——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.brain_types import EMOTION_SAVE_MIN_INTERVAL

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")


async def maybe_save_emotion(
    brain: Brain, now: datetime, *, force: bool = False
) -> None:
    """空心跳节流落盘；有用户消息或强制时立即写。"""
    if brain._db is None:
        return
    interval = float(
        brain.config.get("emotion", {}).get(
            "save_interval_seconds", EMOTION_SAVE_MIN_INTERVAL
        )
    )
    if (
        not force
        and brain._last_emotion_saved_at is not None
        and (now - brain._last_emotion_saved_at).total_seconds() < interval
    ):
        return
    await brain._db.save_emotion(brain.emotion)
    brain._last_emotion_saved_at = now


async def persist_proactive_gate(brain: Brain) -> None:
    if brain._db is None:
        return
    try:
        await brain._db.set_body_memory("proactive_gate", brain.proactive.snapshot())
    except Exception:
        logger.exception("主动门控持久化失败")


async def persist_action_budget(brain: Brain) -> None:
    if brain.action is None:
        return
    await brain.action.persist_budget()
