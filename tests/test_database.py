"""数据库初始化与情绪持久化测试。"""

import tempfile
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
