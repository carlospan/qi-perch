"""「忆」Tab 实时推送：单条 journal_entry 通道与第一次挂钩。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qi.core.emotion import EmotionState
from qi.embodiment.server import EmbodimentServer
from qi.inner_life import InnerLife, _journal_entry
from qi.memory.first_time import FirstTimeMemory
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_notify_journal_entry_broadcasts_payload():
    server = EmbodimentServer(brain=None)  # type: ignore[arg-type]
    server.broadcast = AsyncMock()
    entry = {"kind": "独白", "text": "一点念头", "at": 123}
    await server.notify_journal_entry(entry)
    types = [c.args[0]["type"] for c in server.broadcast.await_args_list]
    assert "journal_entry" in types
    assert server.broadcast.await_args_list[0].args[0] == {
        "type": "journal_entry",
        "payload": entry,
    }


@pytest.mark.asyncio
async def test_presence_change_broadcasts_to_listeners():
    """在场变化时广播，供桌宠「你回来了」微存在；同值不重复推。"""

    class _Perc:
        def set_user_presence(self, online: bool) -> None:
            self.online = online

    class _Brain:
        def __init__(self) -> None:
            self.user_online = True
            self.perception = _Perc()

    server = EmbodimentServer(brain=_Brain())  # type: ignore[arg-type]
    server.broadcast = AsyncMock()

    await server._handle_client_message(
        {"type": "presence", "payload": {"online": False}}
    )
    server.broadcast.assert_awaited_once_with(
        {"type": "presence", "payload": {"online": False}}
    )

    server.broadcast.reset_mock()
    await server._handle_client_message(
        {"type": "presence", "payload": {"online": False}}
    )
    server.broadcast.assert_not_awaited()

    await server._handle_client_message(
        {"type": "presence", "payload": {"online": True}}
    )
    server.broadcast.assert_awaited_once_with(
        {"type": "presence", "payload": {"online": True}}
    )


@pytest.mark.asyncio
async def test_first_time_sets_last_recorded():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        ft = FirstTimeMemory(db, llm=None)
        assert ft.last_recorded is None

        mult, event = await ft.check("晚安", EmotionState())
        assert mult == 3.0
        assert event == "first_goodnight"
        assert ft.last_recorded is not None
        assert ft.last_recorded["kind"] == "第一次"
        assert ft.last_recorded["text"].strip()
        assert isinstance(ft.last_recorded["at"], int)
        await db.close()


@pytest.mark.asyncio
async def test_inner_life_collects_journal_from_returns():
    from qi.core.emotion import ConsciousnessMode

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        class _LLM:
            async def call(self, **kwargs):
                return "独处时闪过一点念头。"

        life = InnerLife(db, _LLM(), config={})  # type: ignore[arg-type]
        life.consciousness.maybe_generate = AsyncMock(return_value="独白内容")  # type: ignore[method-assign]
        life.consciousness.maybe_meta = AsyncMock(return_value="元认知一句")  # type: ignore[method-assign]
        life.dreams.maybe_dream = AsyncMock(return_value="一段梦")  # type: ignore[method-assign]
        life.creativity.maybe_create = AsyncMock(return_value=None)  # type: ignore[method-assign]

        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)
        now = datetime(2026, 7, 23, 12, 0)
        await life.tick(emotion, now, now, "friend")
        kinds = {e["kind"] for e in life.last_journal_entries}
        texts = {e["text"] for e in life.last_journal_entries}
        assert "独白" in kinds
        assert "梦" in kinds
        assert "独白内容" in texts
        assert "元认知一句" in texts
        assert "一段梦" in texts
        await db.close()


def test_journal_entry_helper_shape():
    entry = _journal_entry("梦", "  碎片  ", datetime(2026, 7, 23, 12, 0))
    assert entry["kind"] == "梦"
    assert entry["text"] == "碎片"
    assert isinstance(entry["at"], int)
