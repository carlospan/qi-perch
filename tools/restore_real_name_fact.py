"""一次性数据修复：恢复被脏事实链顶掉的用户真名。

背景
----
包 19 验收实测发现（2026-08-04）：user_facts id=1「他叫阿振」在
7/30 时期被脏事实 id=18「他希望被叫做过去拿」supersede 顶掉；包 16
清退了 id=18 自身，但真名未恢复——当前 active identity 中无任何姓名
事实，栖冷启动后将不记得用户真名。附带损伤：id=15「他觉得自己聪明」
也被脏事实 id=24 supersede 顶掉。

本脚本把被脏事实链顶掉的真值条目恢复为 active（superseded_by=NULL）。
按内容匹配定位（不写死 id），仅恢复与预期内容完全一致的条目。

- 预演（默认）：列出待恢复条目
- --apply：置 superseded_by=NULL

用法
----
    python tools/restore_real_name_fact.py
    python tools/restore_real_name_fact.py --apply
    python tools/restore_real_name_fact.py --db PATH
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "data/qi.db"

# 待恢复条目：(fact_type, content) —— 内容完全匹配才恢复，防误改
_RESTORE_TARGETS = [
    ("identity", "他叫阿振"),        # 真名（必恢复）
    ("identity", "他觉得自己聪明"),     # 被脏事实 #24 顶掉的附带损伤
]


def find_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    hits: list[sqlite3.Row] = []
    for fact_type, content in _RESTORE_TARGETS:
        row = conn.execute(
            "SELECT id, fact_type, content, superseded_by FROM user_facts "
            "WHERE fact_type = ? AND content = ?",
            (fact_type, content),
        ).fetchone()
        if row is not None:
            hits.append(row)
    return hits


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
        rows = find_rows(conn)
        if not rows:
            print("[错误] 未找到任何预期条目（库内容与预期不符，中止）。", file=sys.stderr)
            return 2

        to_restore = [r for r in rows if r["superseded_by"] is not None]
        print(f"[预演] 预期条目 {len(rows)} 条，其中待恢复 {len(to_restore)} 条：")
        for r in rows:
            status = (
                "已 active，跳过"
                if r["superseded_by"] is None
                else f"retired(by={r['superseded_by']}) → 待恢复"
            )
            print(f"  id={r['id']}  content={r['content']!r}  {status}")

        if not to_restore:
            print("[OK] 全部预期条目已是 active，无需恢复。")
            return 0

        # 安全断言：真名条目必须存在且仅一条
        real_names = [r for r in rows if r["content"] == "他叫阿振"]
        if len(real_names) != 1:
            print("[错误] 真名条目数量异常，中止。", file=sys.stderr)
            return 2

        if not args.apply:
            print("\n[提示] 预演未改库。确认后加 --apply：置 superseded_by=NULL。")
            return 0

        for r in to_restore:
            conn.execute(
                "UPDATE user_facts SET superseded_by = NULL WHERE id = ?",
                (r["id"],),
            )
        conn.commit()

        # 复查
        actives = conn.execute(
            "SELECT id, content FROM user_facts "
            "WHERE fact_type = 'identity' AND superseded_by IS NULL ORDER BY id"
        ).fetchall()
        print(f"[OK] 已恢复 {len(to_restore)} 条。当前 active identity：")
        for r in actives:
            print(f"  id={r['id']}  {r['content']}")
        if not any(r["content"] == "他叫阿振" for r in actives):
            print("[错误] 复查失败：真名仍不在 active！", file=sys.stderr)
            return 2
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
