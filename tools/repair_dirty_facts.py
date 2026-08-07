"""一次性数据修复：作废 active 脏 identity 事实（人名门控漏网）。

背景
----
包 19 收紧 looks_like_person_name 后，用新门控动态扫描 active identity：
片段经 identity_name_fragment 取出后不再像人名 → retire（superseded_by=自身）。
不写死 id；预演须保留真名「潘纪振」类合法条目。

- 预演（默认）：列出命中与判定理由，不改库。
- --apply：retire，不硬删。

用法
----
    python tools/repair_dirty_facts.py
    python tools/repair_dirty_facts.py --apply
    python tools/repair_dirty_facts.py --db PATH
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

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qi.memory.facts import (  # noqa: E402
    identity_name_fragment,
    looks_like_person_name,
)

DEFAULT_DB = "data/qi.db"
_KEEP_NAME = "潘纪振"


def find_dirty_identity(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    """返回 (清退清单, 保留的合法 identity)。"""
    cur = conn.execute(
        "SELECT id, fact_type, content, confidence, stability "
        "FROM user_facts WHERE superseded_by IS NULL AND fact_type = 'identity' "
        "ORDER BY id"
    )
    retire: list[dict] = []
    keep: list[dict] = []
    for r in cur.fetchall():
        row = dict(r)
        content = row["content"] or ""
        frag = identity_name_fragment(content)
        if frag is None:
            # 无名字片段的 identity（如叙事句）不在本脚本清退范围
            keep.append({**row, "reason": "无名字片段，跳过"})
            continue
        if looks_like_person_name(frag):
            keep.append({**row, "frag": frag, "reason": f"门控放行 frag={frag!r}"})
            continue
        retire.append(
            {
                **row,
                "frag": frag,
                "reason": f"门控拒收 frag={frag!r}（looks_like_person_name=False）",
            }
        )
    return retire, keep


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
        retire, keep = find_dirty_identity(conn)
    finally:
        conn.close()

    keep_named = [
        k
        for k in keep
        if _KEEP_NAME in (k.get("content") or "")
        or k.get("frag") == _KEEP_NAME
    ]
    if not keep_named:
        # 活库可能已无 id1；预演仍提示，不硬失败（测试库除外）
        print(f"[警告] 未在 active identity 中见到应保留名 {_KEEP_NAME!r}。")
    else:
        print(f"[保留断言] 见到 {_KEEP_NAME!r} ×{len(keep_named)}：")
        for k in keep_named:
            print(f"  id={k['id']}  {k['content']}  ({k.get('reason')})")

    if not retire:
        print("[OK] 未发现需作废的 dirty identity。")
        return 0

    print(f"[预演] 将清退 {len(retire)} 条 dirty identity：")
    for h in retire:
        print(
            f"  id={h['id']:>4}  {h['content']}  "
            f"| {h['reason']}"
        )

    if not args.apply:
        print("\n[提示] 这是预演，未改动库。确认无误后加 --apply 执行 retire。")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        for h in retire:
            fid = int(h["id"])
            conn.execute(
                "UPDATE user_facts SET superseded_by = ? WHERE id = ?",
                (fid, fid),
            )
        conn.commit()
        print(f"[OK] 已 retire {len(retire)} 条。")
        # 复查剩余 active identity
        left = conn.execute(
            "SELECT id, content FROM user_facts "
            "WHERE superseded_by IS NULL AND fact_type = 'identity' ORDER BY id"
        ).fetchall()
        print(f"[复查] 剩余 active identity {len(left)} 条：")
        for r in left:
            print(f"  id={r['id']}  {r['content']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
