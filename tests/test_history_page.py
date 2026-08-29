"""P0 历史分页：load_messages_before + history_page。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.server import HISTORY_PAGE, HISTORY_WINDOW, EmbodimentServer
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_load_messages_before_orders_and_limits(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    await db.initialize()
    base = datetime(2026, 8, 1, 12, 0, 0)
    ids: list[int] = []
    for i in range(10):
        # save_message uses now(); patch via direct insert
        conn = db._require_conn()
        cur = await conn.execute(
            """
            INSERT INTO messages (timestamp, role, content, emotion_context, tone)
            VALUES (?, ?, ?, NULL, NULL)
            """,
            (
                (base + timedelta(minutes=i)).isoformat(timespec="seconds"),
                "user" if i % 2 == 0 else "qi",
                f"m{i}",
            ),
        )
        await conn.commit()
        ids.append(int(cur.lastrowid))

    before = ids[7]
    older = await db.load_messages_before(before, limit=3)
    assert [r["content"] for r in older] == ["m4", "m5", "m6"]
    assert all(r["id"] < before for r in older)

    page = await db.load_messages_before(ids[0], limit=5)
    assert page == []

    await db.close()


@pytest.mark.asyncio
async def test_send_history_before_packet():
    brain = MagicMock()
    db = MagicMock()
    db.load_messages_before = AsyncMock(
        return_value=[
            {
                "id": 3,
                "role": "user",
                "content": "早",
                "timestamp": "2026-08-01T10:00:00",
                "tone": "",
            },
            {
                "id": 4,
                "role": "qi",
                "content": "嗯",
                "timestamp": "2026-08-01T10:01:00",
                "tone": "",
            },
        ]
    )
    brain._db = db
    server = EmbodimentServer(brain)
    sent: list[str] = []

    class WS:
        async def send(self, raw: str) -> None:
            sent.append(raw)

    await server._send_history_before(WS(), before_id=10)
    db.load_messages_before.assert_awaited_once_with(10, limit=HISTORY_PAGE)
    assert sent
    import json

    packet = json.loads(sent[0])
    assert packet["type"] == "history_page"
    assert packet["payload"]["has_more"] is False
    assert len(packet["payload"]["messages"]) == 2
    assert packet["payload"]["messages"][0]["id"] == "db-3"


@pytest.mark.asyncio
async def test_history_command_routes_before():
    brain = MagicMock()
    server = EmbodimentServer(brain)
    server._send_history = AsyncMock()
    server._send_history_before = AsyncMock()

    await server._handle_client_message(
        {"type": "command", "payload": {"text": "/history_before", "before_id": 42}},
        websocket=object(),
    )
    server._send_history_before.assert_awaited_once()
    assert server._send_history_before.await_args.args[1] == 42
    server._send_history.assert_not_awaited()


def test_history_constants():
    assert HISTORY_WINDOW == 200
    assert HISTORY_PAGE == 50
