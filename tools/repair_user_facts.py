"""一次性数据修复：作废 active 脏 user_facts（人名/地点误抽）。

背景
----
FactNoticer 人名/地点门控漏网，把「他希望被叫做过去拿」「他在写谁的代码」
等误解析写成 active 事实并注入 prompt。包 16 加固门控后，本脚本清理已落库污染。

- 预演（默认）：列出命中，不改库。
- --apply：retire（superseded_by=自身），不硬删。

用法
----
    python tools/repair_user_facts.py            # 预演
    python tools/repair_user_facts.py --apply    # 作废
    python tools/repair_user_facts.py --db PATH
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# 允许从仓库根直接跑
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qi.memory.facts import (  # noqa: E402
    identity_name_fragment,
    looks_like_person_name,
    looks_like_real_location,
)

DEFAULT_DB = "data/qi.db"


def find_bogus_active(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT id, fact_type, content, confidence, stability "
        "FROM user_facts WHERE superseded_by IS NULL ORDER BY id"
    )
    hits: list[dict] = []
    for r in cur.fetchall():
        ftype = r["fact_type"] or ""
        content = r["content"] or ""
        bad = False
        if ftype == "identity":
            frag = identity_name_fragment(content)
            if frag is not None and not looks_like_person_name(frag):
                bad = True
            elif frag is None and content.startswith(
                ("他叫", "他姓", "他希望被叫做")
            ):
                bad = True
        elif ftype == "location" and not looks_like_real_location(content):
            bad = True
        if bad:
            hits.append(dict(r))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB, help=f"库路径（默认 {DEFAULT_DB}）")
    ap.add_argument("--apply", action="store_true", help="真正 retire；不加只预演")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库文件：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        hits = find_bogus_active(conn)
    finally:
        conn.close()

    if not hits:
        print("[OK] 未发现需作废的 active 脏 user_facts。")
        return 0

    print(f"[预演] 命中 {len(hits)} 条 active 脏事实：")
    for h in hits:
        print(
            f"  id={h['id']:>4}  {h['fact_type']}/{h['stability']}  "
            f"c={h['confidence']}  {h['content']}"
        )

    if not args.apply:
        print("\n[提示] 这是预演，未改动库。确认无误后加 --apply 执行 retire。")
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        for h in hits:
            fid = int(h["id"])
            conn.execute(
                "UPDATE user_facts SET superseded_by = ? WHERE id = ?",
                (fid, fid),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 已 retire {len(hits)} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
