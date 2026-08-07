"""一次性数据修复：清理 consciousness_stream 中被「施教关系反转」污染的错误记录。

背景
----
补丁 A/B 只修了对话回复路径（intention.py 的 recall），漏掉了意识流路径。
ConsciousnessStream.generate 在独白中引用助眠方法时把施教方向记反（真实是栖教用户，
它写成「你教我的方法」），并逐次添补虚构细节（躺着→数呼吸→数到七→安全句子），
每次生成存回 consciousness_stream 形成自我强化的错误记忆。

本脚本只做数据清理（不属于代码包 15 的范围）：
- 预演（默认）：列出命中记录，不改动库。
- 应用（--apply）：删除这些被污染的行。它们本就是 LLM 生成的虚构独白，非事实记忆，
  删除不会改变栖的真实记忆结构。

注意：consciousness_stream 表没有 strength 列，无法「置低 strength」，
唯一安全的去污染手段是直接删除这些已固化的错误行。删除后，意识流路径在包 15
代码修复落地前仍可能因其他碎片重构出错，但不再有这 8 条错误记录反复强化。

用法
----
    python tools/repair_consciousness_stream.py            # 预演，列命中
    python tools/repair_consciousness_stream.py --apply    # 真正删除
    python tools/repair_consciousness_stream.py --db PATH  # 指定库路径
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "data/qi.db"

# 施教关系反转 + 虚构助眠细节的关键词。命中任一即视为污染记录。
_TAUGHT_BY_USER_RE = [
    "你教我的",
    "你教了我",
    "你教过我",
    "你告诉我方法",
    "你教我的那个方法",
]
# 真实对话（messages）里栖教用户的是「躺着、不强迫自己睡、看天花板」，
# 以下细节在真实对话中不存在，属虚构添补。
_FABRICATED_DETAIL_RE = [
    "数呼吸",
    "数到七",
    "数到 7",
    "数到三",
    "数中间那段空隙",
    "安全的句子",
    "从头再来",
    "脚趾",
    "画地图",
    "枕头上放",
]


def _is_contaminated(content: str) -> bool:
    if not content:
        return False
    text = content
    # 方向反转：栖自称「用户教了我」
    if any(k in text for k in _TAUGHT_BY_USER_RE):
        return True
    # 虚构细节：真实对话没有的助眠方法
    if any(k in text for k in _FABRICATED_DETAIL_RE):
        return True
    return False


def find_contaminated(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT id, timestamp, content FROM consciousness_stream ORDER BY id"
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        content = r["content"] or ""
        if _is_contaminated(content):
            out.append(
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "content": content,
                }
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DEFAULT_DB, help=f"库路径（默认 {DEFAULT_DB}）")
    ap.add_argument("--apply", action="store_true", help="真正删除；不加只预演")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"[错误] 找不到库文件：{db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        hits = find_contaminated(conn)
    finally:
        conn.close()

    if not hits:
        print("[OK] 未发现被污染的 consciousness_stream 记录。库已干净。")
        return 0

    print(f"[预演] 命中 {len(hits)} 条被污染的 consciousness_stream 记录：")
    for h in hits:
        snippet = h["content"].replace("\n", " ")[:60]
        print(f"  id={h['id']:>4}  {h['timestamp']}  {snippet}")

    if not args.apply:
        print("\n[提示] 这是预演，未改动库。确认无误后加 --apply 执行删除。")
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        ids = [h["id"] for h in hits]
        placeholders = ",".join("?" * len(ids))
        cur = conn.execute(
            f"DELETE FROM consciousness_stream WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        deleted = cur.rowcount
    finally:
        conn.close()

    print(f"\n[完成] 已删除 {deleted} 条被污染记录。库已干净。")
    print("[下一步] 仍须按包 15 方案落地意识流施教关系锚定（代码修复），"
          "否则未来生成可能再次重构出错。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
