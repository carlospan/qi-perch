"""P0 对话流式出字：会话广播与 gateway.stream 分级。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.speech_stream import SpeechStreamSession
from qi.llm.gateway import LLMCallOutcome, LLMGateway


@pytest.mark.asyncio
async def test_speech_stream_delta_done_retract():
    emb = MagicMock()
    emb.broadcast = AsyncMock()
    session = SpeechStreamSession(emb)

    await session.delta("你")
    await session.delta("好")
    assert session.live
    await session.finish("你好", emotion="平静", tone="quiet")
    types = [c.args[0]["type"] for c in emb.broadcast.await_args_list]
    assert types == ["speech_delta", "speech_delta", "speech_done"]
    assert emb.broadcast.await_args_list[0].args[0]["payload"]["delta"] == "你"
    assert emb.broadcast.await_args_list[2].args[0]["payload"]["text"] == "你好"

    emb.broadcast.reset_mock()
    session2 = SpeechStreamSession(emb)
    await session2.delta("半")
    await session2.retract()
    await session2.retract()  # idempotent
    types2 = [c.args[0]["type"] for c in emb.broadcast.await_args_list]
    assert types2 == ["speech_delta", "speech_retract"]
    assert not session2.live


@pytest.mark.asyncio
async def test_speech_stream_retract_before_delta_is_noop():
    emb = MagicMock()
    emb.broadcast = AsyncMock()
    session = SpeechStreamSession(emb)
    await session.retract()
    emb.broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_gateway_stream_missing_key(monkeypatch):
    gw = LLMGateway.__new__(LLMGateway)
    gw.providers = {}
    gw.routing = {"conversation": "x:fast"}
    gw._default_provider = "x"
    gw.last_outcome = LLMCallOutcome(text="", failure=None)

    provider = MagicMock()
    provider.key_missing.return_value = True
    provider.name = "x"
    provider.use_tier.return_value = "m"
    gw.providers["x"] = provider
    gw.routing = {"conversation": "x:fast"}

    chunks = [c async for c in gw.stream("conversation", [{"role": "user", "content": "hi"}])]
    assert chunks == []
    assert gw.last_outcome.failure == "missing_key"


@pytest.mark.asyncio
async def test_gateway_stream_yields_and_sets_ok(monkeypatch):
    gw = LLMGateway.__new__(LLMGateway)
    gw.routing = {"conversation": "x:fast"}
    gw._default_provider = "x"
    gw.last_outcome = LLMCallOutcome(text="", failure=None)

    async def fake_stream(*_a, **_k):
        yield "一"
        yield "二"

    provider = MagicMock()
    provider.key_missing.return_value = False
    provider.name = "x"
    provider.use_tier.return_value = "m"
    provider.stream = fake_stream
    gw.providers = {"x": provider}

    chunks = [c async for c in gw.stream("conversation", [{"role": "user", "content": "hi"}])]
    assert chunks == ["一", "二"]
    assert gw.last_outcome.ok
    assert gw.last_outcome.text == "一二"


@pytest.mark.asyncio
async def test_primary_conversation_streams_to_session():
    from qi.core.expression import Expression

    expr = Expression({}, MagicMock())

    async def fake_stream(*_a, **_k):
        yield "栖"
        yield "在"

    expr.llm.stream = fake_stream
    emb = MagicMock()
    emb.broadcast = AsyncMock()
    session = SpeechStreamSession(emb)

    text = await expr._primary_conversation(
        [{"role": "user", "content": "hi"}],
        speech_stream=session,
    )
    assert text == "栖在"
    assert session.live
    assert emb.broadcast.await_count == 2


@pytest.mark.asyncio
async def test_deliver_streamed_skips_emit_speech_but_saves():
    from datetime import datetime

    from qi.core.brain_delivery import deliver_qi_message

    brain = MagicMock()
    brain.avatar = MagicMock()
    brain.avatar.set_talking = MagicMock()
    brain._sync_avatar = AsyncMock()
    brain.emotion = MagicMock()
    brain.emotion.description.return_value = "平静"
    brain.emotion.mode.value = "quiet"
    brain.emotion.model_dump_json.return_value = "{}"
    brain.tts = None
    brain.memory = MagicMock()
    brain._db = MagicMock()
    brain._db.save_message = AsyncMock()
    brain._emit_speech = AsyncMock()
    brain._push_proactive_text = AsyncMock()

    emb = MagicMock()
    emb.broadcast = AsyncMock()
    session = SpeechStreamSession(emb)
    await session.delta("完")

    await deliver_qi_message(
        brain,
        "完整",
        datetime(2026, 8, 30, 12, 0, 0),
        stream=session,
    )
    brain._emit_speech.assert_not_awaited()
    brain.memory.on_qi_message.assert_called_once_with("完整")
    brain._db.save_message.assert_awaited()
    types = [c.args[0]["type"] for c in emb.broadcast.await_args_list]
    assert "speech_done" in types
