"""一次性数据修复：把抽象的施教事实具体化为带方向的存档真值。

背景
----
8-03 19:44 用户纠正「我没教你，是你教我」后，FactNoticer 写入
user_facts：content=「他被对方教导过」。方向正确但太抽象——没说教了什么，
后续检索命中也无法为入睡话题提供方向锚。本脚本将其改写为具体真值
（7-26 #72/74：栖教用户入睡方法），供 anchor_teaching_relation 的
facts 兜底分支使用。

- 预演（默认）：列出命中条目
- --apply：写入具体 content（不改 fact_type/confidence/source）

用法
----
    python tools/repair_teaching_fact.py
    python tools/repair_teaching_fact.py --apply
    python tools/repair_teaching_fact.py --db PATH
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "data/qi.db"

_NEW_CONTENT = (
    "入睡方法这件事：是栖教他的（允许自己躺着、不强迫自己睡），不是他教栖"
)
_SOURCE_MARKER = "我没教你，是你教我"
_OLD_CONTENT_MARKER = "他被对方教导"


def find_hits(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, fact_type, content, source FROM user_facts "
        "WHERE content LIKE ? OR source LIKE ? ORDER BY id",
        (f"%{_OLD_CONTENT_MARKER}%", f"%{_SOURCE_MARKER}%"),
    ).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB, help=f"库路径（默认 {DEFAULT_DB}）")
    ap.add_argument("--apply", action="store_true", help="真正写入；不加只预演")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库文件：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        hits = find_hits(conn)
        if not hits:
            print("[OK] 未发现需具体化的施教事实条目。")
            return 0

        print(f"[预演] 命中 {len(hits)} 条 user_facts：")
        for r in hits:
            print(
                f"  id={r['id']}  type={r['fact_type']}  "
                f"content={r['content']!r}  source={str(r['source'])[:50]!r}"
            )

        if all(r["content"] == _NEW_CONTENT for r in hits):
            print("[OK] 命中条目已是具体真值，无需再改。")
            return 0

        if not args.apply:
            print(
                "\n[提示] 预演未改库。确认后加 --apply：写入具体 content"
                "（不改 fact_type/confidence/source）。"
            )
            return 0

        for r in hits:
            conn.execute(
                "UPDATE user_facts SET content = ? WHERE id = ?",
                (_NEW_CONTENT, r["id"]),
            )
        conn.commit()
        print(f"[OK] 已具体化 {len(hits)} 条施教事实（方向：栖教用户）。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
