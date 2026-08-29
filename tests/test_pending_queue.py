"""用户消息短队列：入队在锁内，避免与心跳竞态丢回复。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.core.brain import PENDING_QUEUE_MAX, Brain, _PendingSpeech


@pytest.mark.asyncio
async def test_receive_enqueues_under_lock_and_processes_fifo():
    brain = Brain({}, MagicMock())
    seen: list[str | None] = []
    delivered: list[str] = []

    async def fake_heartbeat() -> str | None:
        pending = brain._pending_queue.popleft() if brain._pending_queue else None
        seen.append(pending)
        if pending:
            brain._pending_speech = _PendingSpeech(
                pending, datetime(2026, 7, 25, 12, 0, 0), proactive=False
            )
        return pending

    async def fake_deliver(text: str, now: datetime, *, proactive: bool = False) -> None:
        delivered.append(text)

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]

    with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
        assert await brain.receive_user_message("  第一句  ") == "第一句"
        assert await brain.receive_user_message("第二句") == "第二句"
    assert seen == ["第一句", "第二句"]
    assert delivered == ["第一句", "第二句"]
    assert len(brain._pending_queue) == 0


@pytest.mark.asyncio
async def test_receive_empty_message_skipped():
    brain = Brain({}, MagicMock())
    called = False

    async def fake_heartbeat() -> str | None:
        nonlocal called
        called = True
        return None

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    assert await brain.receive_user_message("   ") is None
    assert not called


@pytest.mark.asyncio
async def test_queue_rejects_newest_when_full():
    """满则拒收最新，保留队内旧句，并挂起系统态。"""
    brain = Brain({}, MagicMock())

    async def fake_heartbeat() -> str | None:
        # 不消费队列，模拟只入队后被打断的极端情况
        return None

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]

    for i in range(PENDING_QUEUE_MAX):
        await brain.receive_user_message(f"m{i}")
    assert list(brain._pending_queue) == [f"m{i}" for i in range(PENDING_QUEUE_MAX)]

    out = await brain.receive_user_message("overflow")
    assert out is None
    assert "overflow" not in brain._pending_queue
    assert list(brain._pending_queue) == [f"m{i}" for i in range(PENDING_QUEUE_MAX)]
    notice = brain.take_pending_system_notice()
    assert notice is not None
    assert notice["kind"] == "queue_full"
    assert notice["message"]


@pytest.mark.asyncio
async def test_background_heartbeat_cannot_steal_uncommitted_message():
    """后台占锁时 receive 等待；锁内入队后必消费到自己的消息（无墙钟 sleep 竞态）。"""
    brain = Brain({}, MagicMock())
    processed: list[str | None] = []
    delivered: list[str] = []
    bg_in_heartbeat = asyncio.Event()
    release_bg = asyncio.Event()
    receive_acquire_started = asyncio.Event()

    async def fake_heartbeat() -> str | None:
        pending = brain._pending_queue.popleft() if brain._pending_queue else None
        processed.append(pending)
        if pending:
            brain._pending_speech = _PendingSpeech(
                pending, datetime(2026, 7, 25, 12, 0, 0), proactive=False
            )
        if pending is None:
            bg_in_heartbeat.set()
            await release_bg.wait()
        return pending

    async def fake_deliver(text: str, now: datetime, *, proactive: bool = False) -> None:
        delivered.append(text)

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]

    lock = brain._heartbeat_lock
    orig_acquire = lock.acquire

    async def acquire_tracking(*args, **kwargs):
        # 后台已进临界区后，下一次 acquire 即 receive 在等锁
        if bg_in_heartbeat.is_set():
            receive_acquire_started.set()
        return await orig_acquire(*args, **kwargs)

    lock.acquire = acquire_tracking  # type: ignore[method-assign]

    async def background() -> None:
        async with brain._heartbeat_lock:
            await brain._heartbeat()

    bg = asyncio.create_task(background())
    await bg_in_heartbeat.wait()

    with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
        recv = asyncio.create_task(brain.receive_user_message("你好"))
        await receive_acquire_started.wait()
        release_bg.set()
        reply = await recv
    await bg

    assert reply == "你好"
    assert "你好" in processed
    assert delivered == ["你好"]


@pytest.mark.asyncio
async def test_user_reply_no_post_generation_sleep():
    """生成完直接递送，不再 sleep(0.5~1.5)。"""
    brain = Brain({}, MagicMock())
    delivered: list[str] = []

    async def fake_heartbeat() -> str | None:
        pending = brain._pending_queue.popleft() if brain._pending_queue else None
        if pending:
            brain._pending_speech = _PendingSpeech(
                pending, datetime(2026, 7, 25, 12, 0, 0), proactive=False
            )
        return pending

    async def fake_deliver(text: str, now: datetime, *, proactive: bool = False) -> None:
        delivered.append(text)

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]

    sleep_mock = AsyncMock()
    with patch("qi.core.brain.asyncio.sleep", sleep_mock):
        assert await brain.receive_user_message("想了想") == "想了想"
    sleep_mock.assert_not_called()
    assert delivered == ["想了想"]


@pytest.mark.asyncio
async def test_creation_card_delivers_content_with_qi_line():
    """share 递出：qi_line 进语音；正文经 action 广播由前端卡片承载（W2 内联退役）。"""
    brain = Brain({}, MagicMock())
    delivered: list[str] = []
    broadcasts: list[dict] = []

    async def fake_deliver(text, now, proactive=False):
        delivered.append(text)

    async def fake_broadcast(msg):
        broadcasts.append(msg)

    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]
    brain.embodiment = MagicMock()
    brain.embodiment.broadcast = fake_broadcast

    from datetime import datetime

    card = {
        "type": "creation_card",
        "qi_line": "我今天写了个东西……给你。",
        "content": "**凌晨五点**\n\n天还没亮。",
    }
    await brain._deliver_action_result(card, datetime(2026, 7, 31, 12, 0))
    assert delivered == ["我今天写了个东西……给你。"]
    assert "凌晨五点" not in delivered[0]
    assert len(broadcasts) == 1
    assert broadcasts[0]["type"] == "action"
    assert "凌晨五点" in str(broadcasts[0]["payload"].get("content") or "")

    # 无正文时仍只发 qi_line，并广播卡片
    delivered.clear()
    broadcasts.clear()
    await brain._deliver_action_result(
        {"type": "creation_card", "qi_line": "写了一点。", "content": ""},
        datetime(2026, 7, 31, 12, 1),
    )
    assert delivered == ["写了一点。"]
    assert len(broadcasts) == 1
