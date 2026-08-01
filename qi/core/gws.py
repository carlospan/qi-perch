"""全局工作空间仲裁——阶段二·包 7。

动机只大声：按 salience 选最响者；respond 永不被压过。
Shadow 期用可执行子集对照 legacy；gws.enabled 后全量仲裁驱动行为。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from qi.core.trace import Contender

if TYPE_CHECKING:
    from qi.storage.database import Database

logger = logging.getLogger("qi.gws")

GWS_SHADOW_KEY = "gws_shadow"

# 族优先级：平分时用；respond 另有短路径恒胜
_FAMILY_RANK = {
    "respond": 50,
    "close_loop": 40,
    "report": 30,
    "proactive": 20,
    "action": 10,
    "idle": 0,
    "other": -1,
}

_EXECUTABLE_FAMILIES = frozenset({"respond", "proactive", "action"})


def kind_family(kind: str | None) -> str:
    if not kind or kind == "idle":
        return "idle"
    if kind == "respond":
        return "respond"
    if kind == "close_loop":
        return "close_loop"
    if kind == "report":
        return "report"
    if kind.startswith("proactive:"):
        return "proactive"
    if kind.startswith("action:"):
        return "action"
    return "other"


def executable_contenders(contenders: list[Contender]) -> list[Contender]:
    """Shadow 仲裁用：剔除 close_loop/report，冲 legacy 一致率。"""
    return [c for c in contenders if kind_family(c.kind) in _EXECUTABLE_FAMILIES]


def arbitrate(contenders: list[Contender] | None) -> Contender | None:
    """
    按 salience 取最高；respond 直接置顶。
    平分（差值 < 1e-9）按族优先级，同族按 kind 字典序。
    """
    if not contenders:
        return None
    for c in contenders:
        if c.kind == "respond":
            return c

    best = contenders[0]
    for c in contenders[1:]:
        if c.salience > best.salience + 1e-9:
            best = c
        elif abs(c.salience - best.salience) <= 1e-9:
            r_c = _FAMILY_RANK.get(kind_family(c.kind), -1)
            r_b = _FAMILY_RANK.get(kind_family(best.kind), -1)
            if r_c > r_b or (r_c == r_b and c.kind < best.kind):
                best = c
    return best


def shadow_match(legacy_kind: str | None, arb_kind: str | None) -> bool:
    a = legacy_kind or "idle"
    b = arb_kind or "idle"
    return a == b


def shadow_rate(stats: dict[str, Any] | None) -> float:
    if not stats:
        return 0.0
    beats = int(stats.get("beats") or 0)
    if beats <= 0:
        return 0.0
    return float(stats.get("matches") or 0) / float(beats)


def gws_config(config: dict | None) -> dict[str, Any]:
    cfg = (config or {}).get("gws") or {}
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "shadow_beats": int(cfg.get("shadow_beats", 50)),
        "shadow_match_min": float(cfg.get("shadow_match_min", 0.99)),
    }


async def load_shadow_stats(db: Database | None) -> dict[str, Any]:
    if db is None:
        return {"beats": 0, "matches": 0, "ready": False}
    try:
        raw = await db.get_body_memory(GWS_SHADOW_KEY)
        if isinstance(raw, dict):
            return {
                "beats": int(raw.get("beats") or 0),
                "matches": int(raw.get("matches") or 0),
                "ready": bool(raw.get("ready")),
            }
    except Exception:
        logger.debug("读 gws_shadow 失败", exc_info=True)
    return {"beats": 0, "matches": 0, "ready": False}


async def record_shadow_beat(
    db: Database | None,
    *,
    matched: bool,
    config: dict | None,
) -> dict[str, Any]:
    """累加对照拍；返回更新后的 stats。"""
    gcfg = gws_config(config)
    stats = await load_shadow_stats(db)
    stats["beats"] = int(stats["beats"]) + 1
    if matched:
        stats["matches"] = int(stats["matches"]) + 1
    rate = shadow_rate(stats)
    stats["ready"] = bool(
        stats["beats"] >= gcfg["shadow_beats"] and rate >= gcfg["shadow_match_min"]
    )
    if db is not None:
        try:
            await db.set_body_memory(GWS_SHADOW_KEY, stats)
        except Exception:
            logger.debug("写 gws_shadow 失败", exc_info=True)
    return stats
