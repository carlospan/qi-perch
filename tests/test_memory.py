"""L2 记忆系统测试。"""

import gc
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from qi.core.emotion import EmotionState
from qi.memory.body_memory import BodyMemory
from qi.memory.manager import MemoryManager
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import VectorStore
from qi.memory.working import WorkingMemory
from qi.storage.database import Database


@pytest.mark.asyncio
async def test_working_memory_overflow():
    wm = WorkingMemory(max_size=3)
    assert wm.add("user", "1") is None
    assert wm.add("qi", "2") is None
    assert wm.add("user", "3") is None
    overflow = wm.add("qi", "4")
    assert overflow is not None
    assert overflow.content == "1"
    assert len(wm.get_context()) == 3


@pytest.mark.asyncio
async def test_should_remember_filters_chitchat():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        mm = MemoryManager(
            db,
            {
                "memory": {
                    "max_working_memory": 20,
                    "chroma_path": str(Path(tmp) / "chroma"),
                }
            },
        )
        emotion = EmotionState()

        ok, _ = mm.should_remember("嗯", emotion)
        assert ok is False

        ok, imp = mm.should_remember("我最近在学吉他", emotion)
        assert ok is True
        assert imp >= 0.6

        mm.vector_store.close()
        await db.close()
        gc.collect()


@pytest.mark.asyncio
async def test_narrative_save_search_decay_recall():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "qi.db")
        chroma = str(Path(tmp) / "chroma")
        db = Database(db_path)
        await db.initialize()
        vs = VectorStore(persist_dir=chroma)
        narrative = NarrativeMemory(db, vs)

        mid = await narrative.save(
            content="记得他说他最近在学吉他，弹的是晴天",
            importance=0.8,
            emotional_intensity=0.4,
            tags=["吉他"],
        )
        assert mid > 0

        found = await narrative.search("吉他和音乐", top_k=3)
        assert any("吉他" in m["content"] for m in found)

        before = (await db.get_narrative_memory(mid))["strength"]
        await narrative.decay()
        after = (await db.get_narrative_memory(mid))["strength"]
        assert after < before

        await narrative.recall(mid)
        recalled = (await db.get_narrative_memory(mid))["strength"]
        assert recalled > after

        vs.close()
        await db.close()
        gc.collect()


@pytest.mark.asyncio
async def test_body_memory_records_hours():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        body = BodyMemory(db)
        for i in range(6):
            await body.record_interaction(datetime(2026, 7, 21, 10, i), f"你好{i}")
        pattern = await body.get_pattern("usual_active_hours")
        assert pattern is not None
        assert pattern["samples"] >= 5
        assert pattern["start"] <= 10 <= pattern["end"]
        await db.close()


@pytest.mark.asyncio
async def test_raw_events_and_tables():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        eid = await db.save_raw_event("user_message", "我换工作了", 0.5, 1.5)
        assert eid > 0
        assert await db.count_unprocessed_events() == 1
        await db.mark_events_processed([eid])
        assert await db.count_unprocessed_events() == 0
        await db.close()
