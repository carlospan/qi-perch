"""一次性数据修复：给施教类 shared_culture 钉 7-26 真值方向。

背景
----
relationship.shared_culture 中有一条 shared_reference，pattern 为用户原话
「…你教了我一个方法…」。用户口中「你」=栖，方向本为栖教用户；但注入 prompt
时第二人称易被栖读反。包 17 在条目上加 teach_direction + note（按 7-26 #72/74
真值），默认不改写 pattern。

- 预演（默认）：列出命中条目
- --apply：写入 teach_direction=qi_teaches_user 与 note

用法
----
    python tools/repair_shared_culture.py
    python tools/repair_shared_culture.py --apply
    python tools/repair_shared_culture.py --db PATH
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "data/qi.db"

_PATTERN_MARKER = "你教了我一个方法"
_NOTE = (
    "真值见 7-26 #72/74：栖教用户『允许自己躺着，看天花板』；非用户教栖"
)
_DIRECTION = "qi_teaches_user"


def _load_culture(conn: sqlite3.Connection) -> list[dict]:
    row = conn.execute(
        "SELECT shared_culture FROM relationship WHERE id = 1"
    ).fetchone()
    if not row:
        return []
    raw = row[0] if not isinstance(row, sqlite3.Row) else row["shared_culture"]
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        data = raw
    return data if isinstance(data, list) else []


def find_hits(culture: list[dict]) -> list[tuple[int, dict]]:
    hits: list[tuple[int, dict]] = []
    for i, item in enumerate(culture):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "shared_reference":
            continue
        pattern = str(item.get("pattern") or "")
        if _PATTERN_MARKER in pattern:
            hits.append((i, item))
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
        culture = _load_culture(conn)
        hits = find_hits(culture)
    finally:
        conn.close()

    if not hits:
        print("[OK] 未发现需校正的施教 shared_reference。")
        return 0

    print(f"[预演] 命中 {len(hits)} 条 shared_reference：")
    for idx, item in hits:
        print(
            f"  index={idx}  teach_direction={item.get('teach_direction')!r}  "
            f"pattern={str(item.get('pattern') or '')[:80]}"
        )

    already = all(item.get("teach_direction") == _DIRECTION for _, item in hits)
    if already and all(item.get("note") == _NOTE for _, item in hits):
        print("[OK] 命中条目已带真值方向字段，无需再改。")
        return 0

    if not args.apply:
        print(
            "\n[提示] 预演未改库。确认后加 --apply："
            f"写入 teach_direction={_DIRECTION} 与 note（不改写 pattern）。"
        )
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        culture = _load_culture(conn)
        hits = find_hits(culture)
        for idx, _ in hits:
            culture[idx] = dict(culture[idx])
            culture[idx]["teach_direction"] = _DIRECTION
            culture[idx]["note"] = _NOTE
        conn.execute(
            "UPDATE relationship SET shared_culture = ? WHERE id = 1",
            (json.dumps(culture, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()

    print(f"[OK] 已校正 {len(hits)} 条（teach_direction={_DIRECTION}）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
