"""数据库初始化与情绪持久化测试。"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database, _sql_is_write
from qi.storage.errors import StorageWriteError


@pytest.mark.asyncio
async def test_database_save_and_load_emotion():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "qi.db")
        db = Database(db_path)
        await db.initialize()

        emotion = EmotionState(
            energy=0.72,
            valence=0.35,
            arousal=0.55,
            security=0.61,
            curiosity=0.7,
            attachment=0.4,
            mode=ConsciousnessMode.AWAKE,
        )
        await db.save_emotion(emotion)

        loaded = await db.load_emotion()
        assert loaded is not None
        assert loaded.energy == pytest.approx(0.72)
        assert loaded.valence == pytest.approx(0.35)
        assert loaded.mode == ConsciousnessMode.AWAKE

        await db.save_message("user", "你好")
        await db.save_message("qi", "嗯。你好呀。")
        recent = await db.load_recent_messages(10)
        assert len(recent) == 2
        assert recent[0]["role"] == "user"
        assert recent[1]["role"] == "qi"

        all_msgs = await db.load_messages(limit=None)
        assert len(all_msgs) == 2
        assert all_msgs[0]["id"] is not None
        assert all_msgs[1]["content"] == "嗯。你好呀。"

        await db.close()


@pytest.mark.asyncio
async def test_database_indexes_created():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        conn = db._require_conn()
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ) as cur:
            names = {row[0] for row in await cur.fetchall()}
        assert "idx_messages_timestamp" in names
        assert "idx_emotion_states_timestamp" in names
        assert "idx_raw_events_processed" in names
        assert "idx_consciousness_stream_timestamp" in names
        assert "idx_user_facts_active" in names
        assert "idx_narrative_archived" in names
        assert "idx_actions_timestamp" in names
        await db.close()


@pytest.mark.asyncio
async def test_load_recent_emotions_time_window():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        conn = db._require_conn()
        old_ts = (datetime.now() - timedelta(hours=48)).isoformat(timespec="seconds")
        new_ts = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
        for ts, energy in ((old_ts, 0.5), (new_ts, 0.9)):
            await conn.execute(
                """
                INSERT INTO emotion_states
                    (timestamp, energy, valence, arousal, security, curiosity, attachment, mode)
                VALUES (?, ?, 0.1, 0.4, 0.5, 0.6, 0.3, 'awake')
                """,
                (ts, energy),
            )
        await conn.commit()

        recent = await db.load_recent_emotions(since_hours=24, limit=200)
        assert len(recent) == 1
        assert recent[0]["energy"] == pytest.approx(0.9)

        all_rows = await db.load_recent_emotions(limit=10)
        assert len(all_rows) == 2
        await db.close()


@pytest.mark.asyncio
async def test_load_journal_entries_merges_kinds():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        await db.save_consciousness("今晚有点安静。", trigger="stream")
        await db.save_dream("梦见一棵树。", retention=0.8)
        await db.save_dream("快忘干净的梦。", retention=0.1)
        await db.save_first_time(
            "first_name",
            "他说：「小潘」。",
            inner_experience="心里被轻轻叫了一声。",
        )

        entries = await db.load_journal_entries(limit=80)
        kinds = {e["kind"] for e in entries}
        assert kinds == {"独白", "梦", "第一次"}
        assert all(e["text"] for e in entries)
        assert all(isinstance(e["at"], int) for e in entries)
        # 褪尽的梦不入忆
        assert not any("快忘干净" in e["text"] for e in entries)
        # 第一次优先用内在体验
        ft = next(e for e in entries if e["kind"] == "第一次")
        assert "轻轻叫" in ft["text"]
        # 倒序：最新在前
        assert entries[0]["at"] >= entries[-1]["at"]
        await db.close()


@pytest.mark.asyncio
async def test_user_facts_body_memory_actions_traces_roundtrip():
    """关键表往返：user_facts / body_memory / actions / broadcast_traces。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        now = datetime(2026, 8, 8, 12, 0, 0)

        fid = await db.insert_user_fact(
            "identity",
            "他叫小测。",
            0.9,
            "stable",
            "unit",
            0.5,
            now=now,
        )
        assert fid > 0
        facts = await db.list_active_user_facts("identity")
        assert len(facts) == 1
        assert facts[0]["content"] == "他叫小测。"

        await db.set_body_memory("unit_key", {"n": 1})
        assert await db.get_body_memory("unit_key") == {"n": 1}

        aid = await db.insert_action(
            "tend",
            "整理了一下栖枝",
            target="self",
            outcome="ok",
            season="spring",
            now=now,
        )
        assert aid > 0
        actions = await db.list_recent_actions(5)
        assert actions[0]["kind"] == "tend"
        assert "栖枝" in actions[0]["summary"]

        tid = await db.insert_broadcast_trace(
            beat=1,
            timestamp=now,
            winner_kind="respond",
            winner_salience=0.8,
            candidates=[{"kind": "respond", "salience": 0.8}],
            motive={"why": "user"},
            outcome="ok",
        )
        assert tid > 0
        traces = await db.list_recent_broadcast_traces(5)
        assert traces[0]["winner_kind"] == "respond"
        assert traces[0]["beat"] == 1

        await db.close()


def test_sql_is_write_detects_dml():
    assert _sql_is_write("INSERT INTO x VALUES (1)")
    assert _sql_is_write("  update foo set bar=1")
    assert not _sql_is_write("SELECT * FROM foo")
    assert not _sql_is_write("PRAGMA table_info(foo)")


@pytest.mark.asyncio
async def test_commit_failure_raises_storage_write_error():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        conn = db._require_conn()
        conn.commit = AsyncMock(side_effect=sqlite3.OperationalError("disk full"))
        with pytest.raises(StorageWriteError, match="记忆库写入失败"):
            await db._commit(conn)
        await db.close()


@pytest.mark.asyncio
async def test_write_execute_failure_raises_storage_write_error():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        conn = db._require_conn()
        conn.execute = AsyncMock(
            side_effect=sqlite3.OperationalError("database is locked")
        )
        with pytest.raises(StorageWriteError, match="记忆库写入失败"):
            await db._execute(
                conn,
                "INSERT INTO messages (timestamp, role, content) VALUES (?, ?, ?)",
                ("t", "user", "hi"),
            )
        await db.close()
