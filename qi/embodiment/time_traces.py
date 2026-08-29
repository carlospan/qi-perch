"""方向 D：时间的痕迹——真统计文案（非 speech）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qi.memory.narrative import FORGET_STRENGTH, RECALL_MIN_STRENGTH

# 记得很少时用软话
SOFT_REMEMBERED_LT = 3


async def gather_time_trace_stats(db: Any, *, now: datetime | None = None) -> dict:
    """从库汇总痕迹数字。"""
    now = now or datetime.now()
    remembered = 0
    fading = 0
    if db is not None and hasattr(db, "count_narrative_by_strength_bands"):
        bands = await db.count_narrative_by_strength_bands(
            recall_min=RECALL_MIN_STRENGTH,
            forget_below=FORGET_STRENGTH,
        )
        remembered = int(bands.get("remembered") or 0)
        fading = int(bands.get("fading") or 0)

    days = 1
    if db is not None and hasattr(db, "first_message_at"):
        first = await db.first_message_at()
        if first is not None:
            try:
                if isinstance(first, str):
                    first_dt = datetime.fromisoformat(first)
                else:
                    first_dt = first
                days = max(1, (now.date() - first_dt.date()).days + 1)
            except (TypeError, ValueError):
                days = 1

    return {
        "remembered": remembered,
        "fading": fading,
        "days_known": days,
    }


def format_time_trace_line(stats: dict) -> str:
    """第三人称旁白；记得很少时软话。"""
    remembered = int(stats.get("remembered") or 0)
    fading = int(stats.get("fading") or 0)
    days = max(1, int(stats.get("days_known") or 1))

    if remembered < SOFT_REMEMBERED_LT:
        if days <= 1:
            return "你们才刚认识，痕迹还很浅。"
        return f"你们认识第 {days} 天了，痕迹还很浅。"

    fading_part = ""
    if fading > 0:
        fading_part = f"，其中 {fading} 件正在慢慢淡去"
    return f"她记得 {remembered} 件事{fading_part}。认识第 {days} 天。"


def presence_status_label(
    *,
    typing: bool,
    thinking: bool,
    mode: str,
    stasis: bool,
) -> str:
    """形象旁短旁白；优先级：回你 > 在想 > 蛰伏 > 做梦 > 独处 > 在场。"""
    if typing:
        return "正在回你"
    if thinking:
        return "在想"
    if stasis or mode == "stasis":
        return "睡着了"
    if mode == "dreaming":
        return "在做梦"
    if mode == "solitary":
        return "自己待着"
    return "在这儿"
