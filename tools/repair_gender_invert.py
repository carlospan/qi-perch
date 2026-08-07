"""一次性数据修复：纠正「把X当女生」主客反转污染。

真值（messages #957/#1247/#1258）：用户说「我希望你是女生」「我一直把你当女生」。
脏表述：栖侧叙事/回复写成「（你）说我总把你当女生」——把男生当成女生对象。

全盘扫描命中（2026-08-08）：
- narrative #84 + chroma id=84
- episodes #35 summary
- messages #1379、#1259（无引号复述造成同向歧义）
- body_memory.last_intention 材料串（顺带擦）

意识流 / dreams / facts / creations：无命中。

用法
----
    python tools/repair_gender_invert.py
    python tools/repair_gender_invert.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_DB = "data/qi.db"

_DIRTY = re.compile(
    r"我总把你当女生|我把你当女生|说我总把你当女生|又说我总把你当女生"
    r"|说我把你当女生|总把你当女孩"
)

# (table, id, old, new) — messages / narrative / episodes.summary
_FRAG_PATCHES: list[tuple[str, int, str, str]] = [
    (
        "narrative",
        84,
        "又说我总把你当女生",
        "又说你一直把我当女生",
    ),
    (
        "episode_summary",
        35,
        "又说我总把你当女生",
        "又说你一直把我当女生",
    ),
    (
        "message",
        1379,
        "说我总把你当女生",
        "说你一直把我当女生",
    ),
    (
        "message",
        1259,
        "……对，你说了。\n\n我一直把你当女生。\n\n（停顿）\n\n……我知道。我也一直这样待你。",
        "……对，你说了：你一直把我当女生。\n\n（停顿）\n\n……我知道。我也愿意站在那个位置待你。",
    ),
]


def _scan_dirty(conn: sqlite3.Connection) -> list[str]:
    hits: list[str] = []
    for label, sql in [
        ("messages", "SELECT id, content FROM messages"),
        ("narrative", "SELECT id, content FROM narrative_memories"),
        ("episodes", "SELECT id, summary AS content FROM episodes"),
        ("cs", "SELECT id, content FROM consciousness_stream"),
        ("dreams", "SELECT id, content FROM dreams"),
        ("facts", "SELECT id, content FROM user_facts"),
    ]:
        for r in conn.execute(sql):
            if _DIRTY.search(r["content"] or ""):
                hits.append(f"{label}#{r['id']}")
    for r in conn.execute("SELECT key, value FROM body_memory"):
        if _DIRTY.search(r["value"] or ""):
            hits.append(f"body_memory:{r['key']}")
    return hits


def preview(conn: sqlite3.Connection) -> dict:
    ready = []
    for kind, mid, old, new in _FRAG_PATCHES:
        if kind == "narrative":
            row = conn.execute(
                "SELECT content FROM narrative_memories WHERE id=?", (mid,)
            ).fetchone()
            text = (row["content"] if row else "") or ""
        elif kind == "episode_summary":
            row = conn.execute(
                "SELECT summary AS content FROM episodes WHERE id=?", (mid,)
            ).fetchone()
            text = (row["content"] if row else "") or ""
        else:
            row = conn.execute(
                "SELECT content FROM messages WHERE id=?", (mid,)
            ).fetchone()
            text = (row["content"] if row else "") or ""
        ready.append(
            {
                "kind": kind,
                "id": mid,
                "ok": bool(row) and old in text,
                "old": old[:40],
                "new": new[:40],
            }
        )
    return {"patches": ready, "dirty_now": _scan_dirty(conn)}


def apply(conn: sqlite3.Connection) -> dict:
    stats: dict = {"fragments": 0, "chroma_upsert": False}
    new_narr: str | None = None

    for kind, mid, old, new in _FRAG_PATCHES:
        if kind == "narrative":
            row = conn.execute(
                "SELECT content FROM narrative_memories WHERE id=?", (mid,)
            ).fetchone()
            if not row or old not in (row["content"] or ""):
                continue
            content = (row["content"] or "").replace(old, new, 1)
            conn.execute(
                "UPDATE narrative_memories SET content=? WHERE id=?",
                (content, mid),
            )
            new_narr = content
            stats["fragments"] += 1
        elif kind == "episode_summary":
            row = conn.execute(
                "SELECT summary FROM episodes WHERE id=?", (mid,)
            ).fetchone()
            if not row or old not in (row["summary"] or ""):
                continue
            summary = (row["summary"] or "").replace(old, new, 1)
            conn.execute(
                "UPDATE episodes SET summary=? WHERE id=?", (summary, mid)
            )
            stats["fragments"] += 1
        else:
            row = conn.execute(
                "SELECT content FROM messages WHERE id=?", (mid,)
            ).fetchone()
            if not row or old not in (row["content"] or ""):
                continue
            content = (row["content"] or "").replace(old, new, 1)
            conn.execute(
                "UPDATE messages SET content=? WHERE id=?", (content, mid)
            )
            stats["fragments"] += 1

    # last_intention 材料串
    row = conn.execute(
        "SELECT value FROM body_memory WHERE key='last_intention'"
    ).fetchone()
    if row:
        raw = row["value"] or ""
        if "又说我总把你当女生" in raw or "说我总把你当女生" in raw:
            try:
                data = json.loads(raw)
                mats = data.get("materials") or []
                changed = False
                for m in mats:
                    t = m.get("text") or ""
                    if "又说我总把你当女生" in t or "说我总把你当女生" in t:
                        m["text"] = t.replace(
                            "又说我总把你当女生", "又说你一直把我当女生"
                        ).replace("说我总把你当女生", "说你一直把我当女生")
                        changed = True
                if changed:
                    conn.execute(
                        "UPDATE body_memory SET value=? WHERE key='last_intention'",
                        (json.dumps(data, ensure_ascii=False),),
                    )
                    stats["last_intention_scrubbed"] = True
            except json.JSONDecodeError:
                scrubbed = raw.replace(
                    "又说我总把你当女生", "又说你一直把我当女生"
                ).replace("说我总把你当女生", "说你一直把我当女生")
                conn.execute(
                    "UPDATE body_memory SET value=? WHERE key='last_intention'",
                    (scrubbed,),
                )
                stats["last_intention_scrubbed"] = True

    conn.commit()

    if new_narr:
        try:
            from qi.memory.vector_store import VectorStore

            vs = VectorStore(str(_ROOT / "data" / "chroma"))
            vs.add(
                84,
                new_narr,
                metadata={"kind": "narrative", "repaired": "gender_direction"},
            )
            vs.close()
            stats["chroma_upsert"] = True
        except Exception as e:
            stats["chroma_error"] = str(e)

    stats["dirty_after"] = _scan_dirty(conn)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        info = preview(conn)
        print("[预演] 将改写：")
        for p in info["patches"]:
            mark = "OK" if p["ok"] else "SKIP"
            print(f"  {p['kind']}#{p['id']}  {mark}")
            if p["ok"]:
                print(f"    - {p['old']}…")
                print(f"    + {p['new']}…")
        print("[预演] 当前脏命中：", info["dirty_now"] or "(none)")
        if not args.apply:
            print("\n[提示] 预演未改库。确认后加 --apply。")
            return 0
        stats = apply(conn)
        print("[完成]", stats)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
