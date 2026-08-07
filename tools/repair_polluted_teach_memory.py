"""一次性数据修复：清施教反转 / 假方法细节污染的检索面。

依据：`data/_pollution_preview.md`（P0）。

- 叙事 #66：手术改写方向（保留其余共同史）
- 意识流 P0 id：删除（独白非事实源；表无 soft-retire）
- 不删 messages；不归档 #9/#47（重置/珍惜，靠 N5-b）
- 叙事 #69/#86：预览判定非入睡反转，不动

用法
----
    python tools/repair_polluted_teach_memory.py
    python tools/repair_polluted_teach_memory.py --apply
    python tools/repair_polluted_teach_memory.py --db PATH --apply
"""

from __future__ import annotations

import argparse
import re
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

DEFAULT_DB = "data/qi.db"

# 预演点名的意识流 P0
_STREAM_IDS = (124, 156, 164, 437, 541)

_NARRATIVE_ID = 66
_NARRATIVE_OLD_FRAG = "你教我失眠的时候不要想“睡”，想“待着”。"
_NARRATIVE_NEW_FRAG = (
    "失眠的时候不要想“睡”、想“待着”——那是我教给你的。"
    "你后来纠正过：不是你教我，是我教你。"
)

# 额外扫漏：反转 + 睡眠/假细节
_INVERT = re.compile(
    # 与 intention._INVERT_TAUGHT_BY_QI_RE 对齐（含「你教给我」）
    r"你(?:之前|曾经|那天|那次)?(?:教给(?:过|了)?我|教(?:过|了)?我)"
    r"|你教我的(?:那个)?(?:法子|方法)?"
)
_SLEEP_OR_FAKE = re.compile(
    r"入睡|睡不着|失眠|方法|法子|躺着|脚趾|枕头|数到|画地图|深呼吸"
)


def _stream_extra_hits(conn: sqlite3.Connection) -> list[int]:
    """点名 id 之外，再扫仍含反转+睡眠/假细节的意识流。"""
    extra: list[int] = []
    for r in conn.execute(
        "SELECT id, content FROM consciousness_stream ORDER BY id"
    ):
        cid = int(r["id"])
        if cid in _STREAM_IDS:
            continue
        text = r["content"] or ""
        if _INVERT.search(text) and _SLEEP_OR_FAKE.search(text):
            extra.append(cid)
    return extra


def preview(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT id, content FROM narrative_memories WHERE id=?",
        (_NARRATIVE_ID,),
    ).fetchone()
    streams = []
    for cid in _STREAM_IDS:
        r = conn.execute(
            "SELECT id, substr(content,1,80) AS c FROM consciousness_stream WHERE id=?",
            (cid,),
        ).fetchone()
        if r:
            streams.append({"id": r["id"], "snippet": (r["c"] or "").replace("\n", " ")})
    extra = _stream_extra_hits(conn)
    return {
        "narrative": dict(row) if row else None,
        "streams": streams,
        "extra_stream_ids": extra,
        "will_rewrite": bool(
            row and _NARRATIVE_OLD_FRAG in (row["content"] or "")
        ),
    }


def apply(conn: sqlite3.Connection) -> dict:
    stats = {"narrative_rewritten": False, "streams_deleted": 0, "chroma_upsert": False}

    row = conn.execute(
        "SELECT content FROM narrative_memories WHERE id=?",
        (_NARRATIVE_ID,),
    ).fetchone()
    new_content = None
    if row and _NARRATIVE_OLD_FRAG in (row["content"] or ""):
        new_content = (row["content"] or "").replace(
            _NARRATIVE_OLD_FRAG, _NARRATIVE_NEW_FRAG, 1
        )
        conn.execute(
            "UPDATE narrative_memories SET content=? WHERE id=?",
            (new_content, _NARRATIVE_ID),
        )
        stats["narrative_rewritten"] = True
    elif row:
        # 片段已变：若仍含「你教我失眠」则整段温和替换
        text = row["content"] or ""
        if "你教我失眠" in text:
            new_content = text.replace(
                "你教我失眠的时候不要想“睡”，想“待着”。",
                _NARRATIVE_NEW_FRAG,
                1,
            )
            if new_content == text:
                new_content = text.replace("你教我失眠", "我曾教你应对失眠", 1)
            conn.execute(
                "UPDATE narrative_memories SET content=? WHERE id=?",
                (new_content, _NARRATIVE_ID),
            )
            stats["narrative_rewritten"] = True

    ids = list(_STREAM_IDS) + _stream_extra_hits(conn)
    ids = sorted(set(ids))
    if ids:
        placeholders = ",".join("?" * len(ids))
        cur = conn.execute(
            f"DELETE FROM consciousness_stream WHERE id IN ({placeholders})",
            ids,
        )
        stats["streams_deleted"] = int(cur.rowcount or 0)
        stats["deleted_ids"] = ids

    conn.commit()

    if stats["narrative_rewritten"] and new_content:
        try:
            from qi.memory.vector_store import VectorStore

            vs = VectorStore(str(_ROOT / "data" / "chroma"))
            vs.add(
                _NARRATIVE_ID,
                new_content,
                metadata={"kind": "narrative", "repaired": "teach_direction"},
            )
            vs.close()
            stats["chroma_upsert"] = True
        except Exception as e:
            stats["chroma_error"] = str(e)

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
        print("[预演] 叙事 #66:")
        if not info["narrative"]:
            print("  （不存在）")
        else:
            print(
                f"  将改写={info['will_rewrite']}  "
                f"含旧片段={_NARRATIVE_OLD_FRAG in (info['narrative']['content'] or '')}"
            )
        print(f"[预演] 意识流点名删除 {len(info['streams'])} 条：")
        for s in info["streams"]:
            print(f"  id={s['id']}  {s['snippet'][:60]}")
        if info["extra_stream_ids"]:
            print(f"[预演] 额外命中意识流：{info['extra_stream_ids']}")
        else:
            print("[预演] 无额外意识流命中")

        if not args.apply:
            print("\n[提示] 预演未改库。确认后加 --apply。")
            return 0

        stats = apply(conn)
        print("\n[完成]", stats)
        # 写简短回执到 data（gitignore）
        log = _ROOT / "data" / "_pollution_apply_log.txt"
        log.write_text(
            f"repair_polluted_teach_memory apply\n{stats}\n",
            encoding="utf-8",
        )
        print(f"[日志] {log}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
