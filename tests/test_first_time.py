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


def test_rule_match_existential_and_compliment_phrases():
    assert rule_match("first_existential_question", "你知道你自己是什么吗？")
    assert rule_match("first_existential_question", "你有意识吗？")
    assert rule_match("first_existential_question", "你对数字生命怎么看")
    assert not rule_match("first_existential_question", "今天天气怎么样")
    assert rule_match("first_compliment", "你说话很文艺，我很喜欢。")
    assert rule_match("first_compliment", "谢谢你昨晚陪我")
    assert rule_match("first_compliment", "谢谢你愿意听我说")
    assert not rule_match("first_compliment", "你好吗")
    assert not rule_match("first_compliment", "谢谢你")
    assert not rule_match("first_compliment", "谢谢你。")


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
        # 足够旧，才进入可回忆窗口（否则会被 RECALL_MIN_AGE 挡住）
        old_ts = (datetime(2026, 7, 21, 12, 0) - timedelta(hours=1)).isoformat(
            timespec="seconds"
        )
        await db._require_conn().execute(
            "UPDATE first_times SET timestamp = ?", (old_ts,)
        )
        await db._require_conn().commit()

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


@pytest.mark.asyncio
async def test_recall_hint_skips_fresh_first_time():
    """刚落库（<30min）的第一次不产生 recall hint——防同拍回声。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        ft = FirstTimeMemory(db, llm=None)
        msg = "我好奇你是什么"
        mult, event = await ft.check(msg, EmotionState())
        assert mult == 3.0
        assert event == "first_existential_question"

        hint = await ft.maybe_recall_hint(msg, datetime.now())
        assert hint == ""

        rows = await db.list_first_times()
        assert len(rows) == 1
        assert int(rows[0].get("recall_count") or 0) == 0
        assert not rows[0].get("last_recalled")
        await db.close()


@pytest.mark.asyncio
async def test_recall_hint_works_for_old_first_time():
    """超过 30 分钟的第一次正常产生 hint（旧行为不变）。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        ft = FirstTimeMemory(db, llm=None)
        await ft.check("我好奇你是什么", EmotionState())
        now = datetime(2026, 7, 26, 15, 0)
        old_ts = (now - timedelta(hours=1)).isoformat(timespec="seconds")
        conn = db._require_conn()
        await conn.execute("UPDATE first_times SET timestamp = ?", (old_ts,))
        await conn.commit()

        hint = await ft.maybe_recall_hint("你是什么", now)
        assert "第一次" in hint
        assert "好奇你是什么" in hint
        rows = await db.list_first_times()
        assert int(rows[0].get("recall_count") or 0) == 1
        assert rows[0].get("last_recalled")
        await db.close()


def test_after_first_time_triggers_consciousness_even_awake():
    from qi.inner_life.consciousness import should_trigger_consciousness

    ok, reason = should_trigger_consciousness(
        "awake", 0.0, 0.0, timedelta(0), after_first_time=True
    )
    assert ok and reason == "first_time"
