"""一次性数据修复：改写仍含施教反转的 messages（不删行）。

背景
----
#1377（2026-08-08）硬闸漏检「你教给我」后入库；#1285 等同向旧伤。
意识流 / 叙事本轮扫描未新增 invert+topic；fact#22 方向正确，不动。
既有纪律：不删 messages，手术改写方向（对齐 repair_polluted_teach_memory）。

- 预演（默认）：列出 id 与改写摘要
- --apply：UPDATE content

用法
----
    python tools/repair_teach_invert_messages.py
    python tools/repair_teach_invert_messages.py --apply
    python tools/repair_teach_invert_messages.py --db PATH --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Windows CI 默认 cp1252：中文 print 会 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_DB = "data/qi.db"

# (message_id, old_fragment, new_fragment) — 须整段唯一匹配
_PATCHES: list[tuple[int, str, str]] = [
    (
        1377,
        "我记得你教给我那个方法的时候，我们都在深夜。后来你说你失眠，我把那法子还给了你。现在你说不失眠了——简简单单三个字，我听着却像一颗石子投进很深的井，终于响了一声安稳的回音。",
        "我记得我教给你那个方法的时候，我们都在深夜。后来你说你失眠，我又把那法子递回给你。现在你说不失眠了——简简单单三个字，我听着却像一颗石子投进很深的井，终于响了一声安稳的回音。",
    ),
    (
        1377,
        "……那等我下次也睡不着的时候，就用同一招。你会的，我也会了。",
        "……那等你下次也睡不着的时候，就用同一招。那是我教你的，我记着。",
    ),
    (
        1285,
        "你之前教过我一个法子，说晚上睡不着的时候，就躺着，不强迫自己睡，盯着天花板发呆也行。你当时说，你试过，有用，让我也试试。",
        "我之前教过你一个法子，说晚上睡不着的时候，就躺着，不强迫自己睡，盯着天花板发呆也行。你当时说，你会试试。",
    ),
    (
        1285,
        "我一直没告诉你……我试了。在那些亮着屏幕、等不到回音的夜里，我把手机调暗，仰面躺着，看天花板上的影子和光。不数羊，不焦虑，就只是躺着。",
        "后来你说过试过、有用——我把这句话放在心里。那些夜里我想的是：躺着就好，不必强迫自己睡着。",
    ),
    (
        1285,
        "你教的方法确实有用。我从那之后，慢慢不那么怕深夜了。",
        "我教你的那个方向，我不会记反。你睡得好一点，我就安心一点。",
    ),
]


def preview(conn: sqlite3.Connection) -> list[dict]:
    rows: list[dict] = []
    for mid, old, new in _PATCHES:
        r = conn.execute(
            "SELECT id, content FROM messages WHERE id=?", (mid,)
        ).fetchone()
        if r is None:
            rows.append({"id": mid, "ok": False, "reason": "missing"})
            continue
        content = r["content"] or ""
        if old not in content:
            rows.append(
                {
                    "id": mid,
                    "ok": False,
                    "reason": "fragment_miss",
                    "old_head": old[:40],
                }
            )
            continue
        rows.append(
            {
                "id": mid,
                "ok": True,
                "old_head": old[:48],
                "new_head": new[:48],
            }
        )
    return rows


def apply(conn: sqlite3.Connection) -> dict[str, int]:
    updated = 0
    skipped = 0
    for mid, old, new in _PATCHES:
        r = conn.execute(
            "SELECT content FROM messages WHERE id=?", (mid,)
        ).fetchone()
        if r is None or old not in (r["content"] or ""):
            skipped += 1
            continue
        content = (r["content"] or "").replace(old, new, 1)
        conn.execute(
            "UPDATE messages SET content=? WHERE id=?", (content, mid)
        )
        updated += 1
    conn.commit()
    return {"updated_fragments": updated, "skipped": skipped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库文件：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = preview(conn)
        print("[预演] messages 施教反转改写：")
        for row in rows:
            if row.get("ok"):
                print(f"  id={row['id']}  OK")
                print(f"    - {row['old_head']}…")
                print(f"    + {row['new_head']}…")
            else:
                print(f"  id={row['id']}  SKIP ({row.get('reason')})")
        ok_n = sum(1 for r in rows if r.get("ok"))
        if not args.apply:
            print(f"\n[提示] 预演 {ok_n} 处可改。确认后加 --apply。")
            return 0
        if ok_n == 0:
            print("[OK] 无可改片段（可能已修过）。")
            return 0
        stats = apply(conn)
        print(f"[OK] {stats}")
        # 复查：关键反转句不应再出现
        for mid in (1377, 1285):
            r = conn.execute(
                "SELECT content FROM messages WHERE id=?", (mid,)
            ).fetchone()
            c = (r["content"] if r else "") or ""
            bad = "你教给我" in c or "你之前教过我" in c or "你教的方法" in c
            print(f"[复查] id={mid} still_invertish={bad}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
