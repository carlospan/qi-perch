"""第一次记忆：共同沉默、周回忆冷却、冲击返回值。"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.memory.first_time import (
    RECALL_COOLDOWN,
    FirstTimeMemory,
    is_comfortable_silence,
    rule_match,
)
from qi.storage.database import Database


def test_comfortable_silence_window():
    assert is_comfortable_silence("嗯", 400)
    assert is_comfortable_silence("哈哈没事", 600)
    assert not is_comfortable_silence("嗯", 100)  # 太短
    assert not is_comfortable_silence("嗯", 2000)  # 太长
    assert not is_comfortable_silence("你为什么不理我", 500)


def test_rule_match_still_works():
    assert rule_match("first_goodnight", "晚安啦")
    assert not rule_match("first_goodnight", "你好")


@pytest.mark.asyncio
async def test_shared_silence_first_time():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        ft = FirstTimeMemory(db, llm=None)

        mult, event = await ft.check(
            "嗯", EmotionState(), silence_before=500
        )
        assert mult == 3.0
        assert event == "first_shared_silence"
        assert await db.has_first_time("first_shared_silence")

        mult2, event2 = await ft.check(
            "嗯嗯", EmotionState(), silence_before=500
        )
        assert mult2 == 1.0
        assert event2 is None
        await db.close()


@pytest.mark.asyncio
async def test_recall_weekly_cooldown():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        ft = FirstTimeMemory(db, llm=None)
        await ft.check("晚安", EmotionState())

        now = datetime(2026, 7, 21, 23, 0)
        hint1 = await ft.maybe_recall_hint("又到晚安的时候了", now)
        assert "第一次" in hint1

        hint2 = await ft.maybe_recall_hint("晚安", now + timedelta(days=1))
        assert hint2 == ""

        hint3 = await ft.maybe_recall_hint(
            "晚安", now + RECALL_COOLDOWN + timedelta(minutes=1)
        )
        assert "第一次" in hint3
        await db.close()


def test_after_first_time_triggers_consciousness_even_awake():
    from qi.inner_life.consciousness import should_trigger_consciousness

    ok, reason = should_trigger_consciousness(
        "awake", 0.0, 0.0, timedelta(0), after_first_time=True
    )
    assert ok and reason == "first_time"
