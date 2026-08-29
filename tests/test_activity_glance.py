"""方向 D：轻量动向旁白。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.activity_glance import (
    activity_glance_payload,
    format_activity_line,
    gather_activity_glance,
)


def test_format_lines_by_source():
    assert format_activity_line(kind="独白", source="journal") == "她刚在心里写了一点字。"
    assert format_activity_line(kind="梦", source="journal") == "她刚做了一个梦。"
    assert format_activity_line(kind="第一次", source="journal") == "她刚记下了一次第一次。"
    assert format_activity_line(kind="创作", source="creation") == "她刚递出一篇创作。"
    assert format_activity_line(kind="见闻", source="explore") == "她刚带回一点见闻。"


def test_payload_empty():
    p = activity_glance_payload(None)
    assert p["line"] == ""


@pytest.mark.asyncio
async def test_gather_picks_newest(db):
    from datetime import timedelta

    await db.save_consciousness("一点念头")
    item = await gather_activity_glance(db)
    assert item is not None
    assert item["source"] == "journal"
    assert "心里" in item["line"]

    cid = await db.save_creation("一首小诗", "note", None)
    await db.mark_creation_shared(cid, now=datetime.now() + timedelta(seconds=5))
    item2 = await gather_activity_glance(db)
    assert item2 is not None
    assert item2["source"] == "creation"
    assert "创作" in item2["line"]


@pytest.mark.asyncio
async def test_send_activity_glance_command():
    from qi.embodiment.server import EmbodimentServer

    brain = MagicMock()
    brain._db = None
    server = EmbodimentServer(brain)
    ws = MagicMock()
    ws.send = AsyncMock()
    await server._handle_client_message(
        {"type": "command", "payload": {"text": "/activity_glance"}},
        ws,
    )
    assert ws.send.await_count == 1
    packet = json.loads(ws.send.await_args.args[0])
    assert packet["type"] == "activity_glance"
    assert packet["payload"]["line"] == ""


@pytest.mark.asyncio
async def test_notify_journal_also_pushes_glance():
    from qi.embodiment.server import EmbodimentServer

    server = EmbodimentServer(brain=None)  # type: ignore[arg-type]
    server.broadcast = AsyncMock()
    await server.notify_journal_entry({"kind": "独白", "text": "一点念头", "at": 1})
    types = [c.args[0]["type"] for c in server.broadcast.await_args_list]
    assert "journal_entry" in types
    assert "activity_glance" in types
