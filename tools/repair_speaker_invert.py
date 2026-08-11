# -*- coding: utf-8 -*-
"""一次性数据修复：对照 role_map 纠正叙事/片段里的说话人主宾颠倒。

根因：编织时把栖自己的话（如分享句）织成「你说/你发了…」，而 role_map 仍正确。
修复策略：复用 ``sanitize_woven_narrative`` / ``detect_speaker_inversion``，
**不**对具体文案做黑名单硬编码。

用法
----
    python tools/repair_speaker_invert.py
    python tools/repair_speaker_invert.py --apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qi.memory.weave_guard import (  # noqa: E402
    detect_speaker_inversion,
    sanitize_woven_narrative,
)

DEFAULT_DB = "data/qi.db"


def _first_sentence(text: str, max_len: int = 40) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    for sep in ("。", "！", "？", "\n"):
        i = t.find(sep)
        if 0 < i <= max_len * 2:
            return t[: i + 1][:max_len]
    return t[:max_len]


def _parse_role_map(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _role_map_from_messages(rows: list[sqlite3.Row]) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    user_said: list[str] = []
    qi_said: list[str] = []
    for r in rows:
        text = (r["content"] or "").strip()
        if not text:
            continue
        role = r["role"]
        speaker = "user" if role == "user" else "qi"
        turns.append({"speaker": speaker, "text": text, "event_id": r["id"]})
        if speaker == "user":
            user_said.append(text)
        else:
            qi_said.append(text)
    return {"turns": turns, "user_said": user_said, "qi_said": qi_said}


def scan_episodes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT id, topic, summary, role_map_json, narrative_id FROM episodes ORDER BY id"
    ):
        rm = _parse_role_map(row["role_map_json"])
        if not rm:
            continue
        summary = row["summary"] or ""
        if not detect_speaker_inversion(summary, rm):
            continue
        clean, tags = sanitize_woven_narrative(summary, rm)
        if not tags or clean == summary:
            continue
        hits.append(
            {
                "kind": "episode",
                "id": row["id"],
                "narrative_id": row["narrative_id"],
                "tags": tags,
                "old_summary": summary,
                "new_summary": clean,
                "old_topic": row["topic"] or "",
                "new_topic": _first_sentence(clean, 40),
            }
        )
    return hits


def scan_narratives_via_episodes(
    conn: sqlite3.Connection, episode_hits: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """用片段上的 role_map 清洗关联叙事正文。"""
    hits: list[dict[str, Any]] = []
    seen: set[int] = set()
    for ep in episode_hits:
        nid = ep.get("narrative_id")
        if not nid or nid in seen:
            continue
        seen.add(int(nid))
        row = conn.execute(
            "SELECT id, content FROM narrative_memories WHERE id=?", (nid,)
        ).fetchone()
        if not row:
            continue
        # 取该 episode 的 role_map
        ep_row = conn.execute(
            "SELECT role_map_json FROM episodes WHERE id=?", (ep["id"],)
        ).fetchone()
        rm = _parse_role_map(ep_row["role_map_json"] if ep_row else None)
        content = row["content"] or ""
        if not rm or not detect_speaker_inversion(content, rm):
            continue
        clean, tags = sanitize_woven_narrative(content, rm)
        if not tags or clean == content:
            continue
        hits.append(
            {
                "kind": "narrative",
                "id": row["id"],
                "tags": tags,
                "old": content,
                "new": clean,
            }
        )
    return hits


def scan_qi_messages(conn: sqlite3.Connection, *, window: int = 12) -> list[dict[str, Any]]:
    """近窗对照：栖回复把近聊里只有自己说过的内容说成「你说…」。

    默认偏保守：只收「归因从句」能对上栖近聊独有指纹的命中。
    """
    hits: list[dict[str, Any]] = []
    msgs = list(
        conn.execute("SELECT id, role, content FROM messages ORDER BY id")
    )
    by_id = {m["id"]: i for i, m in enumerate(msgs)}
    for m in msgs:
        if m["role"] != "qi":
            continue
        text = m["content"] or ""
        if "你说" not in text and "你写" not in text and "你发" not in text:
            continue
        idx = by_id[m["id"]]
        prev = msgs[max(0, idx - window) : idx]
        if not prev:
            continue
        rm = _role_map_from_messages(prev)
        if not detect_speaker_inversion(text, rm):
            continue
        clean, tags = sanitize_woven_narrative(text, rm)
        if clean == text or not tags:
            continue
        hits.append(
            {
                "kind": "message",
                "id": m["id"],
                "tags": tags,
                "old": text,
                "new": clean,
            }
        )
    return hits


def preview(
    conn: sqlite3.Connection, *, include_messages: bool = False
) -> dict[str, Any]:
    episodes = scan_episodes(conn)
    narratives = scan_narratives_via_episodes(conn, episodes)
    messages = scan_qi_messages(conn) if include_messages else []
    return {
        "episodes": episodes,
        "narratives": narratives,
        "messages": messages,
    }


def apply(conn: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "episodes": 0,
        "narratives": 0,
        "messages": 0,
        "chroma_upserts": [],
    }
    chroma_payloads: list[tuple[int, str]] = []

    for ep in plan["episodes"]:
        conn.execute(
            "UPDATE episodes SET summary=?, topic=? WHERE id=?",
            (ep["new_summary"], ep["new_topic"], ep["id"]),
        )
        stats["episodes"] += 1

    for narr in plan["narratives"]:
        conn.execute(
            "UPDATE narrative_memories SET content=? WHERE id=?",
            (narr["new"], narr["id"]),
        )
        stats["narratives"] += 1
        chroma_payloads.append((narr["id"], narr["new"]))

    for msg in plan["messages"]:
        conn.execute(
            "UPDATE messages SET content=? WHERE id=?",
            (msg["new"], msg["id"]),
        )
        stats["messages"] += 1

    conn.commit()

    if chroma_payloads:
        try:
            from qi.memory.vector_store import VectorStore

            vs = VectorStore(str(_ROOT / "data" / "chroma"))
            for nid, content in chroma_payloads:
                vs.add(
                    nid,
                    content,
                    metadata={"kind": "narrative", "repaired": "speaker_direction"},
                )
                stats["chroma_upserts"].append(nid)
            vs.close()
        except Exception as e:
            stats["chroma_error"] = str(e)

    # 复扫确认（消息仍按本次是否包含）
    after = preview(conn, include_messages=bool(plan["messages"]))
    stats["remaining_episodes"] = len(after["episodes"])
    stats["remaining_narratives"] = len(after["narratives"])
    stats["remaining_messages"] = len(after["messages"])
    return stats


def _print_plan(plan: dict[str, Any]) -> None:
    print("[预演] 说话人颠倒命中：")
    for ep in plan["episodes"]:
        print(f"  episode#{ep['id']}  tags={ep['tags']}")
        print(f"    topic: {ep['old_topic'][:60]!r}")
        print(f"        -> {ep['new_topic'][:60]!r}")
        print(f"    summary[:80]: {ep['old_summary'][:80]!r}")
        print(f"             -> {ep['new_summary'][:80]!r}")
    for narr in plan["narratives"]:
        print(f"  narrative#{narr['id']}  tags={narr['tags']}")
        print(f"    old[:80]: {narr['old'][:80]!r}")
        print(f"    new[:80]: {narr['new'][:80]!r}")
    for msg in plan["messages"]:
        print(f"  message#{msg['id']}  tags={msg['tags']}")
        print(f"    old[:80]: {msg['old'][:80]!r}")
        print(f"    new[:80]: {msg['new'][:80]!r}")
    if not (plan["episodes"] or plan["narratives"] or plan["messages"]):
        print("  (none)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--messages",
        action="store_true",
        help="同时清洗 messages 表里的主宾颠倒回复（默认只动 episode/narrative）",
    )
    args = ap.parse_args()
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        plan = preview(conn, include_messages=args.messages)
        _print_plan(plan)
        if not args.apply:
            print("\n[提示] 预演未改库。确认后加 --apply。")
            if not args.messages:
                print("[提示] 若要连历史回复一起洗，加 --messages。")
            return 0
        stats = apply(conn, plan)
        print("[完成]", stats)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
