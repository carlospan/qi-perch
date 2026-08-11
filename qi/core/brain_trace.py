"""心跳决策痕迹——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")


async def record_trace(
    brain: Brain,
    *,
    pending: str | None,
    want_express: bool,
    kind: str | None,
    action_type: str | None,
    impact: float | None,
    now: datetime,
) -> None:
    """心跳决策痕迹——给人排障；压缩标签可进身份快照，不进对话流水账。"""
    trace = {
        "at": now.isoformat(timespec="seconds"),
        "mode": brain.emotion.mode.value,
        "pending": bool(pending),
        "want_express": bool(want_express),
        "proactive_kind": kind,
        "gate_blocked": kind is None and bool(want_express) and pending is None,
        "action": action_type,
        "impact": round(impact, 3) if impact is not None else None,
    }
    brain._traces.append(trace)
    if brain._db is None:
        return
    try:
        await brain._db.set_body_memory("last_heartbeat_trace", trace)
        day = now.strftime("%Y-%m-%d")
        if brain._trace_day != day:
            brain._trace_day = day
            await brain._db.set_body_memory("day_first_trace", trace)
    except Exception:
        logger.debug("写入决策痕迹失败", exc_info=True)

    # 包 6：并行落 broadcast_traces（只加痕迹，不改行为）
    try:
        from qi.core.trace import persist_broadcast

        await persist_broadcast(
            brain,
            pending=pending,
            want_express=want_express,
            kind=kind,
            action_type=action_type,
            now=now,
        )
    except Exception:
        logger.debug("写入广播痕迹失败", exc_info=True)


async def format_why(brain: Brain, limit: int = 8) -> str:
    """格式化最近心跳痕迹，供排障/测试（原 CLI /why）。"""
    lines: list[str] = []
    recent = list(brain._traces)[-limit:]
    if recent:
        lines.append(f"最近 {len(recent)} 拍（内存）：")
        for t in recent:
            lines.append(
                f"  {t.get('at')} mode={t.get('mode')} "
                f"pending={t.get('pending')} want={t.get('want_express')} "
                f"kind={t.get('proactive_kind')} gate_blocked={t.get('gate_blocked')} "
                f"action={t.get('action')} impact={t.get('impact')}"
            )
    else:
        lines.append("内存里还没有心跳痕迹。")

    if brain._db is not None:
        try:
            last = await brain._db.get_body_memory("last_heartbeat_trace")
            day_first = await brain._db.get_body_memory("day_first_trace")
            if last:
                lines.append(f"落盘 last：{last}")
            if day_first:
                lines.append(f"今日首拍 day_first：{day_first}")
        except Exception:
            logger.debug("读取决策痕迹失败", exc_info=True)
    return "\n".join(lines)
