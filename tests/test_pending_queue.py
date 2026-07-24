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
async def test_queue_drops_oldest_when_full():
    brain = Brain({}, MagicMock())

    async def fake_heartbeat() -> str | None:
        # 不消费队列，模拟只入队后被打断的极端情况
        return None

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]

    for i in range(PENDING_QUEUE_MAX):
        await brain.receive_user_message(f"m{i}")
    assert list(brain._pending_queue) == [f"m{i}" for i in range(PENDING_QUEUE_MAX)]

    await brain.receive_user_message("overflow")
    assert "m0" not in brain._pending_queue
    assert brain._pending_queue[-1] == "overflow"
    assert len(brain._pending_queue) == PENDING_QUEUE_MAX


@pytest.mark.asyncio
async def test_background_heartbeat_cannot_steal_uncommitted_message():
    """锁外写 pending 时后台可能先清空；锁内入队则调用方必能消费到自己的消息。"""
    brain = Brain({}, MagicMock())
    processed: list[str | None] = []
    delivered: list[str] = []

    async def fake_heartbeat() -> str | None:
        pending = brain._pending_queue.popleft() if brain._pending_queue else None
        processed.append(pending)
        if pending:
            brain._pending_speech = _PendingSpeech(
                pending, datetime(2026, 7, 25, 12, 0, 0), proactive=False
            )
        await asyncio.sleep(0.02)
        return pending

    async def fake_deliver(text: str, now: datetime, *, proactive: bool = False) -> None:
        delivered.append(text)

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]

    async def background() -> None:
        async with brain._heartbeat_lock:
            await brain._heartbeat()

    bg = asyncio.create_task(background())
    await asyncio.sleep(0.005)
    with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
        reply = await brain.receive_user_message("你好")
    await bg

    assert reply == "你好"
    assert "你好" in processed
    assert delivered == ["你好"]


@pytest.mark.asyncio
async def test_user_reply_think_pause_outside_lock():
    """生成在锁内，停顿在锁外——停顿期间锁应可被其他任务拿到。"""
    brain = Brain({}, MagicMock())
    lock_held_during_pause = False

    async def fake_heartbeat() -> str | None:
        pending = brain._pending_queue.popleft() if brain._pending_queue else None
        if pending:
            brain._pending_speech = _PendingSpeech(
                pending, datetime(2026, 7, 25, 12, 0, 0), proactive=False
            )
        return pending

    async def fake_deliver(text: str, now: datetime, *, proactive: bool = False) -> None:
        return None

    async def pause(_seconds: float) -> None:
        nonlocal lock_held_during_pause
        lock_held_during_pause = brain._heartbeat_lock.locked()
        # 停顿期间应能抢到锁
        async with brain._heartbeat_lock:
            pass

    brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]

    with patch("qi.core.brain.asyncio.sleep", side_effect=pause):
        assert await brain.receive_user_message("想了想") == "想了想"
    assert lock_held_during_pause is False
