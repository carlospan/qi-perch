"""L2 记忆系统测试。"""

import gc
import tempfile
from datetime import datetime, timedelta
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

        ok, _ = mm.should_remember("今天天气不错", emotion)
        assert ok is False

        mm.vector_store.close()
        await db.close()
        gc.collect()


@pytest.mark.asyncio
async def test_help_message_is_remembered():
    """求助类对话应被记住——记忆断层实证（2026-07-27 助眠建议漏记）。"""
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
        ok, imp = mm.should_remember(
            "晚上睡不着怎么办，经常半夜两三点睡，8点就要起床上班",
            emotion,
        )
        assert ok is True
        assert imp >= 0.6
        weight = mm.compute_attention_weight(
            "晚上睡不着怎么办，经常半夜两三点睡，8点就要起床上班",
            emotion,
        )
        assert weight > 1.0
        mm.vector_store.close()
        await db.close()
        gc.collect()


def test_weave_batch_prefers_impact_and_caps_size():
    from qi.memory.narrative import NarrativeMemory

    events = [
        {
            "id": 1,
            "timestamp": "2026-07-26T10:00:00",
            "type": "user_message",
            "content": "溢出闲话",
            "emotional_impact": None,
            "attention_weight": 0.5,
        },
        {
            "id": 2,
            "timestamp": "2026-07-26T18:10:48",
            "type": "user_message",
            "content": "晚上睡不着怎么办",
            "emotional_impact": 0.4,
            "attention_weight": 1.35,
        },
        {
            "id": 3,
            "timestamp": "2026-07-26T11:00:00",
            "type": "user_message",
            "content": "另一条溢出",
            "emotional_impact": None,
            "attention_weight": 0.5,
        },
        {
            "id": 4,
            "timestamp": "2026-07-26T12:00:00",
            "type": "user_message",
            "content": "我最近在学吉他",
            "emotional_impact": 0.3,
            "attention_weight": 1.4,
        },
    ]
    # 无 db/llm：只测挑选
    nm = NarrativeMemory(db=None, vector_store=None)  # type: ignore[arg-type]
    batch = nm.select_weave_batch(events, batch_size=2)
    assert len(batch) == 2
    assert {e["id"] for e in batch} == {2, 4}
    # 时间序
    assert batch[0]["id"] == 4
    assert batch[1]["id"] == 2


@pytest.mark.asyncio
async def test_recall_probe_falls_back_to_messages():
    """显式追问且叙事空时，应从 messages 捞回助眠交换。"""
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
        await db.save_message("user", "晚上睡不着怎么办，经常半夜两三点睡")
        await db.save_message(
            "qi",
            "睡不着的时候，不要强迫自己睡，而是允许自己躺着。",
        )
        await db.save_message("user", "我今天晚上试一下")
        # 无关叙事不应挡住追问兜底
        await mm.narrative.save(
            content="秋意沉下来。我把一些东西收进心里。",
            importance=0.7,
            emotional_intensity=0.5,
            tags=["action", "tend"],
        )
        probe = "我上次说过我有时候晚上会睡不着，然后你教了我一个方法，还记得那件事吗？"
        assert MemoryManager.is_recall_probe(probe)
        assert "睡不着" in MemoryManager.recall_keywords(probe)

        found = await mm.retrieve_for_prompt(probe, top_k=3)
        assert found
        blob = "\n".join(m["content"] for m in found)
        assert "睡不着" in blob
        assert "躺着" in blob or "你当时回过" in blob
        assert any(m.get("source") == "messages_recall" for m in found)

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
async def test_silence_anomaly_before_record():
    """沉默异常须在更新 last_interaction 之前检测，否则 gap≈0。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        body = BodyMemory(db)
        await body.update_pattern(
            "silence_tolerance",
            {"gaps": [1.0] * 5, "hours": 2.0, "samples": 5},
        )
        t0 = datetime(2026, 7, 21, 10, 0)
        body._last_interaction = t0
        long_gap = t0 + timedelta(hours=5)  # > 2.0 * 1.5
        anomalies = await body.detect_anomaly(long_gap)
        assert any("安静" in a for a in anomalies)

        # 模拟错误顺序：先 record 再 detect → 不可达
        await body.record_interaction(long_gap, "我回来了")
        after = await body.detect_anomaly(long_gap)
        assert not any("安静" in a for a in after)
        await db.close()


@pytest.mark.asyncio
async def test_manager_silence_anomaly_on_user_message():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        mm = MemoryManager(db, config={})
        await mm.body.update_pattern(
            "silence_tolerance",
            {"gaps": [1.0] * 5, "hours": 2.0, "samples": 5},
        )
        t0 = datetime(2026, 7, 21, 10, 0)
        mm.body._last_interaction = t0
        anomalies = await mm.on_user_message(
            "我回来了", EmotionState(), now=t0 + timedelta(hours=5)
        )
        assert any("安静" in a for a in anomalies)
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
