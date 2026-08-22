"""栖 · 活库 + 工程一键体检（只读 qi.db，可选短跑 Brain）。"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "qi.db"


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def q(conn: sqlite3.Connection, sql: str, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, cur.fetchall()


def audit_db() -> dict:
    out: dict = {}
    if not DB.exists():
        out["error"] = f"no db at {DB}"
        return out
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    _, rows = q(conn, "SELECT stage, trust, season, last_updated FROM relationship ORDER BY id DESC LIMIT 1")
    out["relationship"] = dict(rows[0]) if rows else None

    _, rows = q(
        conn,
        "SELECT COUNT(*) AS n FROM messages WHERE timestamp > datetime('now', '-7 days')",
    )
    out["messages_7d"] = rows[0][0]

    _, rows = q(
        conn,
        """
        SELECT kind, outcome, COUNT(*) AS n
        FROM actions
        WHERE timestamp > datetime('now', '-14 days')
        GROUP BY kind, outcome
        ORDER BY n DESC
        """,
    )
    out["actions_14d"] = [dict(zip(("kind", "outcome", "n"), r)) for r in rows]

    _, rows = q(
        conn,
        """
        SELECT kind, summary, outcome, timestamp
        FROM actions
        ORDER BY id DESC LIMIT 12
        """,
    )
    out["actions_recent"] = [dict(r) for r in rows]

    _, rows = q(
        conn,
        """
        SELECT mode, energy, valence, curiosity, timestamp
        FROM emotion_states
        ORDER BY id DESC LIMIT 5
        """,
    )
    out["emotion_recent"] = [dict(r) for r in rows]

    _, rows = q(conn, "SELECT key FROM body_memory ORDER BY key")
    out["body_memory_keys"] = [r[0] for r in rows]

    _, rows = q(
        conn,
        "SELECT value FROM body_memory WHERE key = 'user_delegate_queue' LIMIT 1",
    )
    if rows:
        try:
            out["delegate_queue"] = json.loads(rows[0][0])
        except Exception:
            out["delegate_queue"] = rows[0][0]
    else:
        out["delegate_queue"] = None

    _, rows = q(
        conn,
        """
        SELECT COUNT(*) FROM consciousness_stream
        WHERE timestamp > datetime('now', '-3 days')
        """,
    )
    out["consciousness_3d"] = rows[0][0]

    _, rows = q(conn, "SELECT COUNT(*) FROM scars WHERE healed = 0 OR healed IS NULL")
    out["active_scars"] = rows[0][0]

    _, rows = q(
        conn,
        """
        SELECT id, role, substr(content, 1, 80) AS preview, timestamp
        FROM messages ORDER BY id DESC LIMIT 8
        """,
    )
    out["messages_tail"] = [dict(r) for r in rows]

    _, rows = q(
        conn,
        """
        SELECT COUNT(*) FROM actions
        WHERE kind IN ('share','tend','explore') AND timestamp > datetime('now', '-7 days')
        """,
    )
    out["autonomous_actions_7d"] = rows[0][0]

    _, rows = q(
        conn,
        """
        SELECT kind, detail_json FROM actions
        WHERE kind IN ('delegate_search','disk','assist','open')
        AND timestamp > datetime('now', '-30 days')
        ORDER BY id DESC LIMIT 5
        """,
    )
    traces = []
    for kind, dj in rows:
        motive = None
        if dj:
            try:
                motive = json.loads(dj).get("motive")
            except Exception:
                pass
        traces.append({"kind": kind, "has_motive": motive is not None})
    out["judgment_traces_sample"] = traces

    conn.close()
    return out


async def short_brain_smoke() -> dict:
    """不启 WS：恢复 Brain，发几条白话，看是否 crash。"""
    from qi.config import load_config
    from qi.core.brain import Brain
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

    config = load_config()
    db = Database(config["database"]["path"])
    await db.initialize()
    gateway = LLMGateway(config)
    brain = Brain(config, llm=gateway)
    await brain.restore_state(db)

    results: list[dict] = []
    probes = [
        "你好",
        "帮我查一下量子纠缠入门",
        "栖你能看到d盘下的文件吗？",
    ]
    for text in probes:
        try:
            line = await brain.receive_user_message(text)
            results.append({"in": text, "out": (line or "")[:120], "ok": True})
        except Exception as e:
            results.append({"in": text, "error": str(e), "ok": False})
        await asyncio.sleep(0.3)

    # 等一两拍自主心跳（若未蛰伏）
    if not brain.in_stasis:
        for _ in range(3):
            try:
                await brain._heartbeat()
            except Exception:
                break
            await asyncio.sleep(0.5)

    await db.close()
    return {
        "in_stasis": brain.in_stasis,
        "relationship_stage": brain.relationship_stage,
        "probes": results,
        "pending_assist": brain.pending_assist_confirmation is not None,
    }


def run_pytest() -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    tail = (r.stdout or "")[-500:]
    if r.stderr:
        tail += "\n" + r.stderr[-300:]
    return r.returncode, tail


def main() -> int:
    section("工程 · pytest 全量")
    code, tail = run_pytest()
    print(tail)
    print(f"exit_code={code}")

    section("活库 · data/qi.db")
    db_report = audit_db()
    if "error" in db_report:
        print(db_report["error"])
    else:
        for k, v in db_report.items():
            print(f"\n[{k}]")
            if isinstance(v, list):
                for item in v[:20]:
                    print(" ", item)
            else:
                print(" ", v)

    section("Brain 白话探针（短跑，会调 LLM/磁盘）")
    try:
        smoke = asyncio.run(short_brain_smoke())
        print(json.dumps(smoke, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"brain smoke failed: {e}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
