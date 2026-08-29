"""方向 D：回顾页记忆条目（真 strength；非 speech）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qi.memory.narrative import FORGET_STRENGTH, RECALL_MIN_STRENGTH

FADING_WHISPER = "快要记不清了"
REVIEW_MEMORY_LIMIT = 80


def is_fading(strength: float) -> bool:
    s = float(strength)
    return FORGET_STRENGTH <= s < RECALL_MIN_STRENGTH


def memory_opacity(strength: float) -> float:
    """strength 0.1→约 0.32；1.0→1.0。"""
    s = max(FORGET_STRENGTH, min(1.0, float(strength)))
    t = (s - FORGET_STRENGTH) / (1.0 - FORGET_STRENGTH)
    return round(0.32 + 0.68 * t, 3)


def _created_at_ms(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw).strip()
    if not text:
        return 0
    try:
        return int(datetime.fromisoformat(text).timestamp() * 1000)
    except ValueError:
        return 0


def format_review_memory_item(row: dict) -> dict:
    strength = float(row.get("strength") or 0)
    fading = is_fading(strength)
    return {
        "id": int(row["id"]),
        "content": str(row.get("content") or "").strip(),
        "strength": strength,
        "opacity": memory_opacity(strength),
        "fading": fading,
        "whisper": FADING_WHISPER if fading else "",
        "at": _created_at_ms(row.get("created_at")),
    }


async def gather_review_memories(db: Any, *, limit: int = REVIEW_MEMORY_LIMIT) -> list[dict]:
    """strength ≥ 遗忘阈；先新后旧。"""
    if db is None or not hasattr(db, "list_review_narratives"):
        return []
    rows = await db.list_review_narratives(
        min_strength=FORGET_STRENGTH,
        limit=limit,
    )
    items = [format_review_memory_item(r) for r in rows]
    return [i for i in items if i["content"]]
