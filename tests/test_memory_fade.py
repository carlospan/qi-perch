"""方向 D：回顾记忆褪色。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.memory_fade import (
    FADING_WHISPER,
    format_review_memory_item,
    gather_review_memories,
    is_fading,
    memory_opacity,
)
from qi.memory.narrative import FORGET_STRENGTH, RECALL_MIN_STRENGTH


def test_is_fading_bands():
    assert not is_fading(RECALL_MIN_STRENGTH)
    assert is_fading(0.15)
    assert not is_fading(FORGET_STRENGTH - 0.01)


def test_opacity_monotonic():
    assert memory_opacity(0.1) < memory_opacity(0.5) < memory_opacity(1.0)


def test_format_item_whisper_only_when_fading():
    fading = format_review_memory_item(
        {
            "id": 1,
            "content": "雨天",
            "strength": 0.15,
            "created_at": "2026-01-01T00:00:00",
        }
    )
    assert fading["fading"] is True
    assert fading["whisper"] == FADING_WHISPER
    clear = format_review_memory_item(
        {
            "id": 2,
            "content": "晴天",
            "strength": 0.8,
            "created_at": "2026-01-02T00:00:00",
        }
    )
    assert clear["fading"] is False
    assert clear["whisper"] == ""


@pytest.mark.asyncio
async def test_gather_skips_forgotten(db):
    await db.save_narrative_memory("记得", importance=0.5, strength=0.9)
    await db.save_narrative_memory("淡去", importance=0.4, strength=0.12)
    await db.save_narrative_memory("忘了", importance=0.2, strength=0.05)
    items = await gather_review_memories(db)
    texts = [i["content"] for i in items]
    assert "记得" in texts
    assert "淡去" in texts
    assert "忘了" not in texts
    fading = next(i for i in items if i["content"] == "淡去")
    assert fading["whisper"] == FADING_WHISPER


@pytest.mark.asyncio
async def test_send_review_memories_command():
    from qi.embodiment.server import EmbodimentServer

    brain = MagicMock()
    db = MagicMock()
    db.list_review_narratives = AsyncMock(
        return_value=[
            {
                "id": 3,
                "content": "窗边的光",
                "strength": 0.14,
                "created_at": "2026-08-01T12:00:00",
            }
        ]
    )
    brain._db = db

    server = EmbodimentServer(brain)
    ws = MagicMock()
    ws.send = AsyncMock()
    await server._handle_client_message(
        {"type": "command", "payload": {"text": "/review_memories"}},
        ws,
    )
    assert ws.send.await_count == 1
    packet = json.loads(ws.send.await_args.args[0])
    assert packet["type"] == "review_memories"
    assert len(packet["payload"]["items"]) == 1
    assert packet["payload"]["items"][0]["whisper"] == FADING_WHISPER
