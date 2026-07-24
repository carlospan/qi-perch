"""数据库初始化与情绪持久化测试。"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database


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
