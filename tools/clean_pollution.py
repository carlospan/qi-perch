# -*- coding: utf-8 -*-
"""清理验收污染与误触 together 软邀消息（带备份）。"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"
MARK = "[验收2026-08-22]"
TOGETHER_LINE = "要不要一起看看？"


def main() -> None:
    if not DB.is_file():
        print("no db")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / "data" / f"backup-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, backup_dir / "qi.db")
    print(f"backup: {backup_dir / 'qi.db'}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    def count(sql: str, params=()) -> int:
        return int(conn.execute(sql, params).fetchone()[0])

    before = {
        "messages": count("SELECT COUNT(*) FROM messages"),
        "actions": count("SELECT COUNT(*) FROM actions"),
        "raw_events": count("SELECT COUNT(*) FROM raw_events"),
        "narrative": count("SELECT COUNT(*) FROM narrative_memories"),
    }

    # 1) 带验收标记的消息（用户句 + 极少数嵌标记的 action 摘要复述）
    n_msg_mark = count(
        "SELECT COUNT(*) FROM messages WHERE content LIKE ?",
        (f"%{MARK}%",),
    )

    # 2) 误触 together 软邀（仅栖、整句匹配）
    n_msg_together = count(
        "SELECT COUNT(*) FROM messages WHERE role='qi' AND content = ?",
        (TOGETHER_LINE,),
    )

    # 3) 验收相关 actions
    n_act_mark = count(
        "SELECT COUNT(*) FROM actions WHERE summary LIKE ? OR detail_json LIKE ?",
        (f"%{MARK}%", f"%{MARK}%"),
    )
    # example.com 仅验收场景用过；open 成功且 target 为 example
    n_act_example = count(
        "SELECT COUNT(*) FROM actions WHERE kind='open' AND summary = 'url:https://example.com'"
    )
    # 验收批次的 delegate_search / list_dir / write 日记污染（时间窗 + 特征）
    n_act_batch = count(
        """
        SELECT COUNT(*) FROM actions WHERE
          timestamp >= '2026-08-22T22:18:00' AND timestamp <= '2026-08-22T23:36:00'
          AND (
            kind IN ('delegate_search', 'list_dir', 'irreversible')
            OR (kind = 'write' AND summary LIKE 'create:D:\\日记-2026-08-22%')
            OR (kind = 'open' AND summary = 'url:https://example.com')
          )
        """
    )

    n_raw = count(
        "SELECT COUNT(*) FROM raw_events WHERE content LIKE ?",
        (f"%{MARK}%",),
    )
    n_narr = count(
        "SELECT COUNT(*) FROM narrative_memories WHERE content LIKE ?",
        (f"%{MARK}%",),
    )

    print("plan delete:")
    print(f"  messages mark: {n_msg_mark}")
    print(f"  messages together invite: {n_msg_together}")
    print(f"  actions mark: {n_act_mark}")
    print(f"  actions example open: {n_act_example}")
    print(f"  actions acceptance batch window: {n_act_batch}")
    print(f"  raw_events: {n_raw}")
    print(f"  narrative: {n_narr}")

    conn.execute("DELETE FROM messages WHERE content LIKE ?", (f"%{MARK}%",))
    conn.execute(
        "DELETE FROM messages WHERE role='qi' AND content = ?",
        (TOGETHER_LINE,),
    )
    conn.execute(
        "DELETE FROM actions WHERE summary LIKE ? OR detail_json LIKE ?",
        (f"%{MARK}%", f"%{MARK}%"),
    )
    conn.execute(
        "DELETE FROM actions WHERE kind='open' AND summary = 'url:https://example.com'"
    )
    conn.execute(
        """
        DELETE FROM actions WHERE
          timestamp >= '2026-08-22T22:18:00' AND timestamp <= '2026-08-22T23:36:00'
          AND (
            kind IN ('delegate_search', 'list_dir', 'irreversible')
            OR (kind = 'write' AND summary LIKE 'create:D:\\日记-2026-08-22%')
          )
        """
    )
    conn.execute("DELETE FROM raw_events WHERE content LIKE ?", (f"%{MARK}%",))
    conn.execute(
        "DELETE FROM narrative_memories WHERE content LIKE ?",
        (f"%{MARK}%",),
    )

    # 验收跑批产生的 qi 回复（无标记）：落在验收用户句时间窗内的短批回复
    # 取带标记用户句的时间戳集合，删同秒内及之后 90s 内 role=qi 且不含标记的消息（保守）
    user_ts = [
        r[0]
        for r in conn.execute(
            "SELECT timestamp FROM messages WHERE content LIKE ? AND role='user'",
            (f"%{MARK}%",),
        ).fetchall()
    ]
    # 已删带标记消息，用备份库取时间戳
    backup = sqlite3.connect(backup_dir / "qi.db")
    user_ts = [
        r[0]
        for r in backup.execute(
            "SELECT timestamp FROM messages WHERE content LIKE ? AND role='user'",
            (f"%{MARK}%",),
        ).fetchall()
    ]
    backup.close()
    extra_qi = 0
    for ts in user_ts:
        cur = conn.execute(
            """
            DELETE FROM messages WHERE role='qi'
              AND content NOT LIKE ?
              AND timestamp >= ?
              AND timestamp <= datetime(?, '+90 seconds')
            """,
            (f"%{MARK}%", ts, ts),
        )
        extra_qi += cur.rowcount
    print(f"  extra qi replies in acceptance windows: {extra_qi}")

    conn.commit()

    after = {
        "messages": count("SELECT COUNT(*) FROM messages"),
        "actions": count("SELECT COUNT(*) FROM actions"),
        "raw_events": count("SELECT COUNT(*) FROM raw_events"),
        "narrative": count("SELECT COUNT(*) FROM narrative_memories"),
    }
    print("before:", before)
    print("after:", after)
    print("removed messages:", before["messages"] - after["messages"])
    print("removed actions:", before["actions"] - after["actions"])

    # 验收报告文件
    removed_reports = 0
    for p in ROOT.glob("data/_acceptance_*"):
        p.unlink()
        removed_reports += 1
    print(f"removed report files: {removed_reports}")

    conn.close()


if __name__ == "__main__":
    main()
