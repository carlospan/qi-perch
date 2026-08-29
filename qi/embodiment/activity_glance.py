"""方向 D：轻量动向——存在页一行真事件旁白（非 speech）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _iso_to_ms(ts_raw: str) -> int | None:
    try:
        return int(datetime.fromisoformat(ts_raw).timestamp() * 1000)
    except ValueError:
        return None


def format_activity_line(*, kind: str, source: str) -> str:
    """第三人称短旁白；不内联正文。"""
    if source == "journal":
        if kind == "梦":
            return "她刚做了一个梦。"
        if kind == "第一次":
            return "她刚记下了一次第一次。"
        return "她刚在心里写了一点字。"
    if source == "creation":
        return "她刚递出一篇创作。"
    if source == "explore":
        return "她刚带回一点见闻。"
    return ""


def _candidate(source: str, kind: str, at: int, key: str) -> dict:
    line = format_activity_line(kind=kind, source=source)
    return {
        "source": source,
        "kind": kind,
        "at": at,
        "key": key,
        "line": line,
    }


def _parse_detail(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return raw


async def _latest_explore_at(db: Any) -> dict | None:
    if not hasattr(db, "list_recent_explore_card_actions"):
        return None
    try:
        rows = await db.list_recent_explore_card_actions(limit=8)
    except Exception:
        return None
    for r in rows:
        ts_raw = str(r.get("timestamp") or "")
        at = _iso_to_ms(ts_raw) or 0
        if at <= 0:
            continue
        detail = _parse_detail(r.get("detail_json"))
        if not isinstance(detail, dict):
            continue
        found = detail.get("found")
        if not isinstance(found, dict):
            continue
        entries = found.get("entries")
        source = str(detail.get("source") or found.get("source") or "")
        if source not in ("web", "journal", "web_delegate"):
            continue
        if not isinstance(entries, list) or not entries:
            continue
        return _candidate(
            "explore",
            "见闻",
            at,
            f"e-{int(r.get('id') or 0)}",
        )
    return None


async def gather_activity_glance(db: Any) -> dict | None:
    """从日记/梦、已递出创作、见闻中取时间最新一条；无则 None。"""
    if db is None:
        return None

    candidates: list[dict] = []

    if hasattr(db, "load_journal_entries"):
        try:
            entries = await db.load_journal_entries(limit=1)
        except Exception:
            entries = []
        for e in entries:
            at = int(e.get("at") or 0)
            text = str(e.get("text") or "").strip()
            if at <= 0 or not text:
                continue
            kind = str(e.get("kind") or "独白")
            candidates.append(
                _candidate("journal", kind, at, str(e.get("id") or f"j-{at}"))
            )

    if hasattr(db, "list_recent_shared_creations"):
        try:
            rows = await db.list_recent_shared_creations(limit=1)
        except Exception:
            rows = []
        for r in rows:
            content = str(r.get("content") or "").strip()
            ts = str(r.get("shared_at") or "")
            at = _iso_to_ms(ts) or 0
            if not content or at <= 0:
                continue
            candidates.append(
                _candidate(
                    "creation",
                    "创作",
                    at,
                    f"c-{int(r.get('id') or 0)}",
                )
            )

    explore = await _latest_explore_at(db)
    if explore is not None:
        candidates.append(explore)

    if not candidates:
        return None
    best = max(candidates, key=lambda c: int(c["at"]))
    if not best.get("line"):
        return None
    return best


def activity_glance_payload(item: dict | None) -> dict:
    if not item:
        return {"line": "", "source": "", "kind": "", "at": 0, "key": ""}
    return {
        "line": str(item.get("line") or ""),
        "source": str(item.get("source") or ""),
        "kind": str(item.get("kind") or ""),
        "at": int(item.get("at") or 0),
        "key": str(item.get("key") or ""),
    }
