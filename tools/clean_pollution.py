# -*- coding: utf-8 -*-
"""清理验收 / 相处批跑 / 工程试聊污染（带备份）。

默认删：
- 含 `[验收` 标记的 messages / actions / raw_events / narrative
- 2026-08-22 22:18 起至 2026-08-24 前的试聊 messages（验收批 + coexist + 改码试跑）
- 同时段内 L7 试跑 actions（list_dir / delegate_search / open example / together 等）
- data/_acceptance_*、data/_coexist_* 报告与临时运行时配置
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"

ACCEPTANCE_MARK = "[验收"
TOGETHER_LINE = "要不要一起看看？"

# 验收批 + 08-23 改码 coexist / 试聊时间窗（不含更早真实相处）
POLLUTION_START = "2026-08-22T21:45:00"
POLLUTION_END = "2026-08-24T00:00:00"

# 试跑产生的 action kinds（窗口内整类删；budget_tune / look 多为心跳附带，一并清）
POLLUTION_ACTION_KINDS = (
    "list_dir",
    "delegate_search",
    "open",
    "together",
    "irreversible",
    "write",
    "archive",
)

REPORT_GLOBS = (
    "data/_acceptance_*",
    "data/_coexist_*",
    "data/_peek_*",
    "data/_msgs.json",
    "data/_acceptance_runtime_settings.yaml",
    "data/_coexist_runtime_settings.yaml",
)


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

    n_msg_mark = count(
        "SELECT COUNT(*) FROM messages WHERE content LIKE ?",
        (f"%{ACCEPTANCE_MARK}%",),
    )
    n_msg_window = count(
        """
        SELECT COUNT(*) FROM messages
        WHERE timestamp >= ? AND timestamp < ?
        """,
        (POLLUTION_START, POLLUTION_END),
    )
    n_msg_together = count(
        "SELECT COUNT(*) FROM messages WHERE role='qi' AND content = ?",
        (TOGETHER_LINE,),
    )

    kinds_sql = ",".join(f"'{k}'" for k in POLLUTION_ACTION_KINDS)
    n_act_mark = count(
        "SELECT COUNT(*) FROM actions WHERE summary LIKE ? OR detail_json LIKE ?",
        (f"%{ACCEPTANCE_MARK}%", f"%{ACCEPTANCE_MARK}%"),
    )
    n_act_window = count(
        f"""
        SELECT COUNT(*) FROM actions
        WHERE timestamp >= ? AND timestamp < ?
          AND kind IN ({kinds_sql})
        """,
        (POLLUTION_START, POLLUTION_END),
    )
    n_act_example = count(
        "SELECT COUNT(*) FROM actions WHERE kind='open' AND summary = 'url:https://example.com'"
    )
    n_act_budget_window = count(
        """
        SELECT COUNT(*) FROM actions
        WHERE timestamp >= ? AND timestamp < ?
          AND kind IN ('budget_tune', 'look')
        """,
        (POLLUTION_START, POLLUTION_END),
    )

    n_raw_mark = count(
        "SELECT COUNT(*) FROM raw_events WHERE content LIKE ?",
        (f"%{ACCEPTANCE_MARK}%",),
    )
    n_raw_window = count(
        """
        SELECT COUNT(*) FROM raw_events
        WHERE timestamp >= ? AND timestamp < ?
        """,
        (POLLUTION_START, POLLUTION_END),
    )
    n_narr_mark = count(
        "SELECT COUNT(*) FROM narrative_memories WHERE content LIKE ?",
        (f"%{ACCEPTANCE_MARK}%",),
    )

    print("plan delete:")
    print(f"  messages acceptance mark: {n_msg_mark}")
    print(f"  messages in window {POLLUTION_START}..{POLLUTION_END}: {n_msg_window}")
    print(f"  messages together invite: {n_msg_together}")
    print(f"  actions acceptance mark: {n_act_mark}")
    print(f"  actions L7/window kinds: {n_act_window}")
    print(f"  actions example open (any time): {n_act_example}")
    print(f"  actions budget_tune/look in window: {n_act_budget_window}")
    print(f"  raw_events mark: {n_raw_mark}")
    print(f"  raw_events in window: {n_raw_window}")
    print(f"  narrative mark: {n_narr_mark}")

    conn.execute("DELETE FROM messages WHERE content LIKE ?", (f"%{ACCEPTANCE_MARK}%",))
    conn.execute(
        "DELETE FROM messages WHERE role='qi' AND content = ?",
        (TOGETHER_LINE,),
    )
    conn.execute(
        """
        DELETE FROM messages
        WHERE timestamp >= ? AND timestamp < ?
        """,
        (POLLUTION_START, POLLUTION_END),
    )

    conn.execute(
        "DELETE FROM actions WHERE summary LIKE ? OR detail_json LIKE ?",
        (f"%{ACCEPTANCE_MARK}%", f"%{ACCEPTANCE_MARK}%"),
    )
    conn.execute(
        "DELETE FROM actions WHERE kind='open' AND summary = 'url:https://example.com'"
    )
    conn.execute(
        f"""
        DELETE FROM actions
        WHERE timestamp >= ? AND timestamp < ?
          AND kind IN ({kinds_sql})
        """,
        (POLLUTION_START, POLLUTION_END),
    )
    conn.execute(
        """
        DELETE FROM actions
        WHERE timestamp >= ? AND timestamp < ?
          AND kind IN ('budget_tune', 'look')
        """,
        (POLLUTION_START, POLLUTION_END),
    )

    conn.execute("DELETE FROM raw_events WHERE content LIKE ?", (f"%{ACCEPTANCE_MARK}%",))
    conn.execute(
        """
        DELETE FROM raw_events
        WHERE timestamp >= ? AND timestamp < ?
        """,
        (POLLUTION_START, POLLUTION_END),
    )
    conn.execute(
        "DELETE FROM narrative_memories WHERE content LIKE ?",
        (f"%{ACCEPTANCE_MARK}%",),
    )

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
    print("removed raw_events:", before["raw_events"] - after["raw_events"])
    print("removed narrative:", before["narrative"] - after["narrative"])

    removed_reports = 0
    for pattern in REPORT_GLOBS:
        for p in ROOT.glob(pattern):
            if p.is_file():
                p.unlink()
                removed_reports += 1
                print(f"removed file: {p}")
    print(f"removed report/temp files: {removed_reports}")

    conn.close()


if __name__ == "__main__":
    main()
