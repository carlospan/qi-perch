"""具身：进行中轮次可取消。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from qi.embodiment.server import EmbodimentServer


@pytest.mark.asyncio
async def test_turn_control_rephrase_cancels_and_acks():
    brain = MagicMock()
    brain.in_stasis = False
    brain.emotion.description.return_value = "安静"
    brain.on_turn_interrupted = MagicMock()
    brain.take_pending_system_notice = MagicMock(return_value=None)

    async def slow_receive(_text):
        await asyncio.sleep(5)
        return "不该出现"

    brain.receive_user_message = slow_receive

    server = EmbodimentServer(brain)
    server.broadcast = AsyncMock()
    server.send_speech = AsyncMock()
    server.send_typing = AsyncMock()
    server.send_system_notice = AsyncMock()

    await server._on_user_message("你好呀这是原句")
    assert server._turn_in_flight()
    await asyncio.sleep(0.05)
    await server._interrupt_active_turn("rephrase")
    await asyncio.sleep(0.05)

    assert not server._turn_in_flight()
    brain.on_turn_interrupted.assert_called()
    server.send_speech.assert_awaited()
    ack_text = server.send_speech.await_args.args[0]
    assert "重说" in ack_text
    interrupted = [
        c
        for c in server.broadcast.await_args_list
        if c.args and isinstance(c.args[0], dict) and c.args[0].get("type") == "turn_interrupted"
    ]
    assert interrupted
    payload = interrupted[0].args[0]["payload"]
    assert payload["action"] == "rephrase"
    assert payload["prefill"] == "你好呀这是原句"


@pytest.mark.asyncio
async def test_silent_turn_sends_fallback_notice():
    brain = MagicMock()
    brain.in_stasis = False
    brain.take_pending_system_notice = MagicMock(return_value=None)
    brain.receive_user_message = AsyncMock(return_value="")
    brain.llm = MagicMock()
    brain.llm.last_outcome = MagicMock(failure="unreachable")

    server = EmbodimentServer(brain)
    server.broadcast = AsyncMock()
    server.send_speech = AsyncMock()
    server.send_typing = AsyncMock()
    server.send_system_notice = AsyncMock()

    await server._run_user_turn("你好")
    server.send_system_notice.assert_awaited_once()
    payload = server.send_system_notice.await_args.args[0]
    assert payload["kind"] == "unreachable"


@pytest.mark.asyncio
async def test_silent_turn_fallback_empty_when_no_failure():
    brain = MagicMock()
    brain.in_stasis = False
    brain.take_pending_system_notice = MagicMock(return_value=None)
    brain.receive_user_message = AsyncMock(return_value="")
    brain.llm = MagicMock()
    brain.llm.last_outcome = MagicMock(failure=None)

    server = EmbodimentServer(brain)
    server.send_system_notice = AsyncMock()

    await server._run_user_turn("你好")
    payload = server.send_system_notice.await_args.args[0]
    assert payload["kind"] == "empty"


@pytest.mark.asyncio
async def test_pending_notice_skips_fallback():
    from qi.embodiment.system_notice import notice_payload

    brain = MagicMock()
    brain.in_stasis = False
    brain.take_pending_system_notice = MagicMock(
        return_value=notice_payload("missing_key")
    )
    brain.receive_user_message = AsyncMock(return_value="")

    server = EmbodimentServer(brain)
    server.send_system_notice = AsyncMock()

    await server._run_user_turn("你好")
    server.send_system_notice.assert_awaited_once()
    assert server.send_system_notice.await_args.args[0]["kind"] == "missing_key"


@pytest.mark.asyncio
async def test_speech_response_skips_fallback():
    brain = MagicMock()
    brain.in_stasis = False
    brain.take_pending_system_notice = MagicMock(return_value=None)
    brain.receive_user_message = AsyncMock(return_value="嗯，在呢。")

    server = EmbodimentServer(brain)
    server.send_system_notice = AsyncMock()

    await server._run_user_turn("你好")
    server.send_system_notice.assert_not_awaited()
