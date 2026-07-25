"""心跳决策痕迹 + /why 格式化。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.storage.database import Database


class _StubLLM:
    async def call(self, **kwargs):
        return "嗯。"


@pytest.mark.asyncio
async def test_record_trace_memory_and_body_memory():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain({}, llm=_StubLLM())  # type: ignore[arg-type]
        brain._db = db
        now = datetime(2026, 7, 23, 12, 0)
        await brain._record_trace(
            pending="你好",
            want_express=True,
            kind=None,
            action_type=None,
            impact=0.12,
            now=now,
        )
        assert len(brain._traces) == 1
        assert brain._traces[0]["impact"] == 0.12
        assert brain._traces[0]["pending"] is True
        last = await db.get_body_memory("last_heartbeat_trace")
        day_first = await db.get_body_memory("day_first_trace")
        assert last is not None
        assert day_first is not None
        assert last["at"] == day_first["at"]

        later = datetime(2026, 7, 23, 13, 0)
        await brain._record_trace(
            pending=None,
            want_express=False,
            kind=None,
            action_type="explore",
            impact=None,
            now=later,
        )
        last2 = await db.get_body_memory("last_heartbeat_trace")
        day2 = await db.get_body_memory("day_first_trace")
        assert last2["action"] == "explore"
        # 同一天不覆盖 day_first
        assert day2["at"] == day_first["at"]
        await db.close()


@pytest.mark.asyncio
async def test_format_why_includes_traces():
    brain = Brain({}, llm=_StubLLM())  # type: ignore[arg-type]
    brain.emotion = EmotionState()
    now = datetime(2026, 7, 23, 12, 0)
    await brain._record_trace(
        pending=None,
        want_express=True,
        kind=None,
        action_type=None,
        impact=None,
        now=now,
    )
    text = await brain.format_why()
    assert "want=True" in text
    assert "gate_blocked=True" in text
