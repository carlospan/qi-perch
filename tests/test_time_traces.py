"""方向 D：时间的痕迹文案与状态旁白。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.time_traces import (
    format_time_trace_line,
    gather_time_trace_stats,
    presence_status_label,
)


def test_format_soft_when_few_memories():
    assert (
        format_time_trace_line({"remembered": 0, "fading": 0, "days_known": 1})
        == "你们才刚认识，痕迹还很浅。"
    )
    assert (
        format_time_trace_line({"remembered": 2, "fading": 1, "days_known": 5})
        == "你们认识第 5 天了，痕迹还很浅。"
    )


def test_format_full_with_fading():
    line = format_time_trace_line(
        {"remembered": 10, "fading": 3, "days_known": 40}
    )
    assert line == "她记得 10 件事，其中 3 件正在慢慢淡去。认识第 40 天。"


def test_format_full_without_fading():
    line = format_time_trace_line(
        {"remembered": 5, "fading": 0, "days_known": 12}
    )
    assert line == "她记得 5 件事。认识第 12 天。"


def test_presence_status_priority():
    assert (
        presence_status_label(
            typing=True, thinking=True, mode="dreaming", stasis=False
        )
        == "正在回你"
    )
    assert (
        presence_status_label(
            typing=False, thinking=True, mode="ambient", stasis=False
        )
        == "在想"
    )
    assert (
        presence_status_label(
            typing=False, thinking=False, mode="stasis", stasis=True
        )
        == "睡着了"
    )
    assert (
        presence_status_label(
            typing=False, thinking=False, mode="dreaming", stasis=False
        )
        == "在做梦"
    )
    assert (
        presence_status_label(
            typing=False, thinking=False, mode="solitary", stasis=False
        )
        == "自己待着"
    )
    assert (
        presence_status_label(
            typing=False, thinking=False, mode="ambient", stasis=False
        )
        == "在这儿"
    )


@pytest.mark.asyncio
async def test_gather_stats_from_db():
    db = MagicMock()
    db.count_narrative_by_strength_bands = AsyncMock(
        return_value={"remembered": 8, "fading": 2}
    )
    first = (datetime.now() - timedelta(days=9)).isoformat(timespec="seconds")
    db.first_message_at = AsyncMock(return_value=first)
    stats = await gather_time_trace_stats(db)
    assert stats["remembered"] == 8
    assert stats["fading"] == 2
    assert stats["days_known"] == 10


@pytest.mark.asyncio
async def test_send_time_traces_command():
    from qi.embodiment.server import EmbodimentServer

    brain = MagicMock()
    db = MagicMock()
    db.count_narrative_by_strength_bands = AsyncMock(
        return_value={"remembered": 0, "fading": 0}
    )
    db.first_message_at = AsyncMock(return_value=None)
    brain._db = db

    server = EmbodimentServer(brain)
    ws = MagicMock()
    ws.send = AsyncMock()
    await server._handle_client_message(
        {"type": "command", "payload": {"text": "/time_traces"}},
        ws,
    )
    assert ws.send.await_count == 1
    raw = ws.send.await_args.args[0]
    import json

    packet = json.loads(raw)
    assert packet["type"] == "time_traces"
    assert "痕迹还很浅" in packet["payload"]["line"]


@pytest.mark.asyncio
async def test_db_strength_bands_and_first_message(db):
    await db.save_narrative_memory("记得", importance=0.5, strength=0.8)
    await db.save_narrative_memory("淡去", importance=0.4, strength=0.15)
    await db.save_narrative_memory("忘了", importance=0.2, strength=0.05)
    bands = await db.count_narrative_by_strength_bands(
        recall_min=0.2, forget_below=0.1
    )
    assert bands["remembered"] == 1
    assert bands["fading"] == 1

    await db.save_message("user", "你好")
    first = await db.first_message_at()
    assert first is not None
    stats = await gather_time_trace_stats(db)
    assert stats["remembered"] == 1
    assert stats["fading"] == 1
    assert stats["days_known"] >= 1
    line = format_time_trace_line(stats)
    assert "痕迹还很浅" in line
