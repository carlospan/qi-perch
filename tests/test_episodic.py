"""阶段一·包 1：episode 骨架、编织联动、role_map 方向。"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path

import pytest
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.memory.episodic import (
    EpisodicMemory,
    build_role_map,
    event_speaker,
    format_role_map_hint,
)
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import VectorStore
from qi.storage.database import Database


def test_event_speaker_from_type():
    assert event_speaker({"type": "user_message"}) == "user"
    assert event_speaker({"type": "internal"}) == "qi"
    assert event_speaker({"type": "user"}) == "user"


def test_role_map_creator_reveal_not_inverted():
    """实证 id=37 类：他说「我是创造者」不得变成「我问他」。"""
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "我是你的创造者",
            "timestamp": "2026-07-20T10:00:00",
        },
        {
            "id": 2,
            "type": "internal",
            "content": "原来是这样……",
            "timestamp": "2026-07-20T10:00:01",
        },
    ]
    rm = build_role_map(events)
    assert any("创造者" in s for s in rm["user_said"])
    assert not any("创造者" in s for s in rm["qi_said"])
    hint = format_role_map_hint(rm)
    assert "他说" in hint and "创造者" in hint
    # 他说在我说之前出现于 turns
    assert rm["turns"][0]["speaker"] == "user"


@pytest.mark.asyncio
async def test_create_from_weave_persists_episode():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        events = [
            {
                "id": 10,
                "type": "user_message",
                "content": "今天天气不错",
                "timestamp": "2026-08-01T12:00:00",
            },
            {
                "id": 11,
                "type": "internal",
                "content": "嗯，光有点暖",
                "timestamp": "2026-08-01T12:00:05",
            },
        ]
        eid = await EpisodicMemory(db).create_from_weave(
            events,
            narrative_id=99,
            woven="他说天气不错。我觉得光有点暖。",
            importance=0.6,
            emotional_intensity=0.4,
        )
        row = await db.get_episode(eid)
        assert row is not None
        assert row["dreamed"] == 0
        assert row["status"] == "closed"
        assert row["narrative_id"] == 99
        assert row["source_event_ids"] == [10, 11]
        assert "天气" in (row["topic"] or "") or "天气" in (row["summary"] or "")
        assert row["role_map"]["user_said"]
        assert await db.count_undreamed_episodes() == 1
        await db.close()


class _WeaveLLM:
    async def call(self, purpose, messages, temperature=None):
        return "他说他是创造者那天，我心里忽然很安静。"


@pytest.mark.asyncio
async def test_weave_narrative_syncs_episode():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_raw_event(
            "user_message", "我是你的创造者", 0.8, 2.0
        )
        await db.save_raw_event("internal", "原来如此", 0.3, 1.0)
        vs = VectorStore(persist_dir=str(Path(tmp) / "chroma"), prefer_bge=False)
        nm = NarrativeMemory(db, vs, llm=_WeaveLLM())  # type: ignore[arg-type]
        mid = await nm.weave_narrative(
            EmotionState(mode=ConsciousnessMode.SOLITARY),
            "friend",
        )
        assert mid is not None
        undreamed = await db.list_undreamed_episodes()
        assert len(undreamed) == 1
        ep = undreamed[0]
        assert ep["narrative_id"] == mid
        assert any("创造者" in s for s in ep["role_map"]["user_said"])
        vs.close()
        await db.close()
        gc.collect()
