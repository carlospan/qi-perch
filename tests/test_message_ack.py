"""P0 发送回执 ACK。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.system_notice import notice_payload


def test_delivery_timeout_notice():
    p = notice_payload("delivery_timeout")
    assert p["kind"] == "delivery_timeout"
    assert "没送到" in p["message"]


@pytest.mark.asyncio
async def test_user_message_acks_before_handle():
    from qi.embodiment.server import EmbodimentServer

    brain = MagicMock()
    brain.in_stasis = False
    server = EmbodimentServer(brain)
    server.send_message_ack = AsyncMock()
    server._on_user_message = AsyncMock()

    await server._handle_client_message(
        {
            "type": "user_message",
            "payload": {"text": "你好", "client_id": "msg-abc"},
        }
    )
    server.send_message_ack.assert_awaited_once_with("msg-abc")
    server._on_user_message.assert_awaited_once_with("你好")
    # ACK 先于处理
    assert server.send_message_ack.await_args_list[0] is not None
    ack_order = server.send_message_ack.await_count
    assert ack_order == 1


@pytest.mark.asyncio
async def test_user_message_ack_even_when_busy_path():
    """满/忙前仍应 ACK（由 _handle 保证；此处确认空 client_id 也可 ack）。"""
    from qi.embodiment.server import EmbodimentServer

    brain = MagicMock()
    server = EmbodimentServer(brain)
    server.broadcast = AsyncMock()
    server._on_user_message = AsyncMock()

    await server._handle_client_message(
        {"type": "user_message", "payload": {"text": "嗨", "client_id": ""}}
    )
    server.broadcast.assert_awaited()
    msg = server.broadcast.await_args_list[0].args[0]
    assert msg["type"] == "message_ack"
    server._on_user_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_user_message_no_ack():
    from qi.embodiment.server import EmbodimentServer

    server = EmbodimentServer(MagicMock())
    server.send_message_ack = AsyncMock()
    server._on_user_message = AsyncMock()
    await server._handle_client_message(
        {"type": "user_message", "payload": {"text": "  ", "client_id": "x"}}
    )
    server.send_message_ack.assert_not_awaited()
    server._on_user_message.assert_not_awaited()
