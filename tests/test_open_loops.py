"""阶段一·包 3：open loops 入队/闭合/积压触发/拔管模板。"""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import pytest
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.inner_life.consciousness import (
    ConsciousnessStream,
    render_template_thought,
    should_trigger_consciousness,
)
from qi.memory.open_loops import MAX_OPEN_LOOPS, OpenLoopQueue, build_concern
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_enqueue_dedupes_same_kind():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        q = OpenLoopQueue(db)
        a = await q.enqueue("waking", seed="「甲」")
        b = await q.enqueue("waking", seed="「乙」")
        assert a["id"] == b["id"]
        assert q.count() == 1
        assert "乙" in b["concern"]
        await db.close()


@pytest.mark.asyncio
async def test_enqueue_cap_five():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        q = OpenLoopQueue(db)
        kinds = [
            "waking",
            "first_time",
            "emotion_surge",
            "silence",
            "season_change",
            "user_drift",
        ]
        for k in kinds:
            await q.enqueue(k, seed=k)
        assert q.count() == MAX_OPEN_LOOPS
        await db.close()


@pytest.mark.asyncio
async def test_persist_across_reload():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        q1 = OpenLoopQueue(db)
        await q1.enqueue("silence")
        q2 = OpenLoopQueue(db)
        await q2.load()
        assert q2.count() == 1
        await db.close()


@pytest.mark.asyncio
async def test_close_sediments_raw_event():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _LLM("还悬着那句话。")
        stream = ConsciousnessStream(db, llm, config={})  # type: ignore[arg-type]
        await stream.loops.enqueue("waking", seed="「创造者」")
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)
        text = await stream.maybe_generate(
            emotion, timedelta(hours=1), prefer_close=True
        )
        assert text and "悬" in text
        assert stream.loops.count() == 0
        events = await db.load_unprocessed_events()
        assert any("[想过]" in (e.get("content") or "") for e in events)
        trace = await db.get_body_memory("last_loop_close")
        assert trace and trace.get("path") == "llm"
        await db.close()


@pytest.mark.asyncio
async def test_template_unplug_closes_loop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _LLM("")
        stream = ConsciousnessStream(db, llm, config={})  # type: ignore[arg-type]
        await stream.loops.enqueue(
            "season_change", seed="从春偏到了夏"
        )
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY, valence=0.3)
        text = await stream.maybe_generate(
            emotion, timedelta(hours=1), prefer_close=True
        )
        assert text
        assert "春" in text or "夏" in text or "季节" in text
        assert "先这样" in text or "答案" in text or "回头" in text
        assert stream.loops.count() == 0
        rows = await db.load_recent_consciousness(limit=1, stream_type="stream")
        assert rows
        await db.close()


def test_template_readable_not_log():
    loop = {
        "concern": build_concern("waking", "「你会累吗」"),
        "fragment": "",
    }
    text = render_template_thought(loop, EmotionState(valence=-0.2))
    assert "还没想完" in text or "醒来" in text
    assert "timestamp" not in text.lower()
    assert "\n" in text


def test_event_surge_still_immediate():
    ok, reason = should_trigger_consciousness(
        "ambient", 0.4, 0.0, timedelta(minutes=1), open_loop_count=0
    )
    assert ok and reason == "emotion_surge"


@pytest.mark.asyncio
async def test_think_count_expires():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        q = OpenLoopQueue(db)
        item = await q.enqueue("silence")
        item["think_count"] = 3
        await q.save()
        await q.expire_stale()
        assert q.count() == 0
        await db.close()


@pytest.mark.asyncio
async def test_overview_excludes_active():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        q = OpenLoopQueue(db)
        a = await q.enqueue("waking", seed="甲")
        await q.enqueue("silence")
        ov = q.overview(exclude_id=a["id"])
        assert "安静" in ov
        assert "甲" not in ov
        await db.close()


@pytest.mark.asyncio
async def test_force_season_enqueue_and_generate():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _LLM("夏天的光有点不一样。")
        stream = ConsciousnessStream(db, llm, config={})  # type: ignore[arg-type]
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)
        text = await stream.maybe_generate(
            emotion,
            timedelta(0),
            force_trigger="season_change",
            force_seed="从春偏到了夏",
        )
        assert text
        rows = await db.load_recent_consciousness(limit=1, stream_type="stream")
        assert rows and rows[0]["trigger"] == "season_change"
        await db.close()


class _LLM:
    def __init__(self, text: str):
        self.text = text
        self.calls: list = []

    async def call(self, purpose, messages, temperature=None):
        self.calls.append({"purpose": purpose, "messages": messages})
        return self.text
