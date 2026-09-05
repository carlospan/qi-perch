"""P0 主动开口信笺：proactive 落库 + speech/history 标记。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.core.brain_delivery import deliver_qi_message, emit_speech, push_proactive_text
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.embodiment.server import EmbodimentServer
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_save_and_load_proactive_flag(tmp_path: Path):
    db = Database(tmp_path / "p.db")
    await db.initialize()
    await db.save_message("qi", "普通回复")
    await db.save_message("qi", "她来过一句", proactive=True)
    rows = await db.load_messages(limit=None)
    assert rows[0]["proactive"] is False
    assert rows[1]["proactive"] is True
    await db.close()


@pytest.mark.asyncio
async def test_migrate_old_db_without_proactive_column(tmp_path: Path):
    path = tmp_path / "old.db"
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            emotion_context TEXT,
            tone TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO messages (timestamp, role, content) VALUES ('2026-01-01T00:00:00', 'qi', '旧句')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    await db.initialize()
    rows = await db.load_messages(limit=None)
    assert len(rows) == 1
    assert rows[0]["proactive"] is False
    await db.save_message("qi", "新主动", proactive=True)
    rows2 = await db.load_messages(limit=None)
    assert rows2[-1]["proactive"] is True
    await db.close()


@pytest.mark.asyncio
async def test_send_speech_includes_proactive():
    brain = MagicMock()
    server = EmbodimentServer(brain)
    server.broadcast = AsyncMock()
    await server.send_speech("hi", emotion="安静", tone="ambient", proactive=True)
    msg = server.broadcast.await_args.args[0]
    assert msg["type"] == "speech"
    assert msg["payload"]["proactive"] is True
    assert msg["payload"]["text"] == "hi"


@pytest.mark.asyncio
async def test_send_speech_omits_proactive_when_false():
    brain = MagicMock()
    server = EmbodimentServer(brain)
    server.broadcast = AsyncMock()
    await server.send_speech("hi", emotion="安静", tone="ambient", proactive=False)
    msg = server.broadcast.await_args.args[0]
    assert "proactive" not in msg["payload"]


@pytest.mark.asyncio
async def test_format_history_carries_proactive():
    brain = MagicMock()
    server = EmbodimentServer(brain)
    out = server._format_history_messages(
        [
            {
                "id": 1,
                "role": "qi",
                "content": "来过",
                "timestamp": "2026-09-06T01:00:00",
                "tone": "",
                "proactive": True,
            },
            {
                "id": 2,
                "role": "qi",
                "content": "回复",
                "timestamp": "2026-09-06T01:01:00",
                "tone": "",
                "proactive": False,
            },
        ]
    )
    assert out[0]["proactive"] is True
    assert out[1]["proactive"] is False


@pytest.mark.asyncio
async def test_push_proactive_emit_marks_speech():
    brain = MagicMock()
    brain.embodiment = MagicMock()
    brain.embodiment.send_speech = AsyncMock()
    brain.embodiment.send_audio = AsyncMock()
    brain.emotion = EmotionState(mode=ConsciousnessMode.AMBIENT)
    brain.tts = None
    brain.proactive_queue = MagicMock()
    brain.proactive_queue.put = AsyncMock()
    brain._emit_speech = AsyncMock()

    await push_proactive_text(brain, "夜里想你")
    brain._emit_speech.assert_awaited_once_with("夜里想你", proactive=True)


@pytest.mark.asyncio
async def test_deliver_qi_message_saves_proactive(tmp_path: Path):
    db = Database(tmp_path / "d.db")
    await db.initialize()
    brain = MagicMock()
    brain.avatar = MagicMock()
    brain.avatar.set_talking = MagicMock()
    brain._sync_avatar = AsyncMock()
    brain._push_proactive_text = AsyncMock()
    brain._emit_speech = AsyncMock()
    brain.memory = None
    brain._db = db
    brain.emotion = EmotionState(mode=ConsciousnessMode.AMBIENT)
    brain.tts = None
    brain.embodiment = None

    from datetime import datetime

    await deliver_qi_message(brain, "主动一句", datetime.now(), proactive=True)
    rows = await db.load_messages(limit=None)
    assert rows[-1]["content"] == "主动一句"
    assert rows[-1]["proactive"] is True
    brain._push_proactive_text.assert_awaited_once()
    await db.close()


@pytest.mark.asyncio
async def test_emit_speech_passes_proactive_flag():
    brain = MagicMock()
    brain.embodiment = MagicMock()
    brain.embodiment.send_speech = AsyncMock()
    brain.emotion = EmotionState(mode=ConsciousnessMode.AWAKE)
    brain.tts = None
    await emit_speech(brain, "x", proactive=True)
    brain.embodiment.send_speech.assert_awaited_once()
    kwargs = brain.embodiment.send_speech.await_args.kwargs
    assert kwargs.get("proactive") is True
