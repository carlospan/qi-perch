"""身体记忆注入：阶段闸 + 整段进 placeholder。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.llm.prompt_builder import PromptBuilder
from qi.memory.manager import MemoryManager
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_body_rhythm_hint_stranger_empty():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        mem = MemoryManager(db, config={})
        await db.set_body_memory(
            "usual_active_hours",
            {"start": 20, "end": 23, "samples": 10},
        )
        assert await mem.body_rhythm_hint("stranger") == ""
        await db.close()


@pytest.mark.asyncio
async def test_body_rhythm_hint_needs_samples():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        mem = MemoryManager(db, config={})
        await db.set_body_memory(
            "usual_active_hours",
            {"start": 20, "end": 23, "samples": 3},
        )
        assert await mem.body_rhythm_hint("acquaintance") == ""
        await db.close()


@pytest.mark.asyncio
async def test_body_rhythm_hint_injected_with_ban():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        mem = MemoryManager(db, config={})
        await db.set_body_memory(
            "usual_active_hours",
            {"start": 20, "end": 23, "samples": 10},
        )
        hint = await mem.body_rhythm_hint("acquaintance")
        assert hint.startswith("【他的身体节奏】")
        assert "不要主动评论他的作息" in hint
        assert "20" in hint and "23" in hint

        builder = PromptBuilder()
        messages = builder.build_conversation_prompt(
            user_message="你好",
            emotion=EmotionState(),
            now=datetime.now(),
            inner_extras={"body_hint": hint},
        )
        system = messages[0]["content"]
        assert "【他的身体节奏】" in system
        assert "不要主动评论他的作息" in system

        empty = builder.build_conversation_prompt(
            user_message="你好",
            emotion=EmotionState(),
            now=datetime.now(),
            inner_extras={},
        )
        assert "【他的身体节奏】" not in empty[0]["content"]
        await db.close()
