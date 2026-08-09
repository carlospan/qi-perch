"""阶段二·包 8：自操作 + explore 真读闭环。"""

from __future__ import annotations

import gc
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.action.budget import ActionBudget
from qi.action.explore import ExploreAction
from qi.action.layer import ActionLayer
from qi.action.self_ops import SelfOps
from qi.action.volition import action_intentions
from qi.core.emotion import EmotionState
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import VectorStore
from qi.sensing import collect


@pytest.mark.asyncio
async def test_archive_changes_search_results(db):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        chroma = str(Path(tmp) / "chroma")
        vs = VectorStore(persist_dir=chroma)
        narrative = NarrativeMemory(db, vs)
        content = "一段不重要的闲话，几乎不会再想起"
        mid = await narrative.save(
            content=content,
            importance=0.2,
            emotional_intensity=0.1,
            tags=["stale"],
        )
        ops = SelfOps(db)
        budget = ActionBudget({"action": {"autonomous_daily_limit": 2}})
        result = await ops.archive_stale_memories(budget, now=datetime.now())
        assert result is not None
        assert mid in result["archived_ids"]
        row = await db.get_narrative_memory(mid)
        assert int(row["archived"]) == 1
        found = await narrative.search("闲话", top_k=5)
        assert all(m["id"] != mid for m in found)
        vs.close()
        gc.collect()


@pytest.mark.asyncio
async def test_budget_tune_shifts_explore_priority(db):
    _ = db
    now = datetime(2026, 7, 27, 12, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    emotion = EmotionState(curiosity=0.9, energy=0.7, valence=0.2)
    before = action_intentions(
        mode="solitary",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.2,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
        energy=0.7,
    )
    pri_before = next(i.priority for i in before if i.kind == "explore")
    ops = SelfOps(db)
    tuned = await ops.tune_budget(budget, emotion, now=now)
    assert tuned is not None
    assert budget.kind_weights["explore"] > 1.0
    # 调预算占了一次日限；换新预算日限或新 day 测权重效果
    budget2 = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    budget2.kind_weights = dict(budget.kind_weights)
    after = action_intentions(
        mode="solitary",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.2,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget2,
        now=now,
        season_scale=1.0,
        energy=0.7,
    )
    pri_after = next(i.priority for i in after if i.kind == "explore")
    assert pri_after > pri_before


@pytest.mark.asyncio
async def test_explore_reads_journal_narratives(db):
    await db.save_narrative_memory(
        "午后的光把影子拉长，我想起你说话时的停顿。", importance=0.6
    )
    explore = ExploreAction(db, base_probability=1.0)
    result = await explore.drift(
        0.9, EmotionState(curiosity=0.9), "spring", force=True
    )
    assert result is not None
    assert result["source"] == "journal"
    assert result["speak"] is True
    assert result["found"] is not None
    assert result["found"]["source"] == "journal"
    titles = [e["title"] for e in result["found"]["entries"]]
    assert any("影子" in t or "停顿" in t for t in titles)
    assert "远方" not in result["summary"]


@pytest.mark.asyncio
async def test_explore_no_narratives_found_none(db):
    explore = ExploreAction(db, base_probability=1.0)
    result = await explore.drift(
        0.9, EmotionState(curiosity=0.9), "spring", force=True
    )
    assert result is not None
    assert result["source"] == "journal"
    assert result["speak"] is True
    assert result["found"] is None
    assert "没有" in result["summary"]


@pytest.mark.asyncio
async def test_self_ops_respects_daily_budget(db):
    ops = SelfOps(db)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 1}})
    now = datetime(2026, 7, 27, 15, 0)
    await db.save_narrative_memory("可归档", importance=0.1)
    first = await ops.archive_stale_memories(budget, now=now)
    assert first is not None
    second = await ops.archive_stale_memories(budget, now=now)
    assert second is None
    journal = await ops.write_inner_journal(
        budget, EmotionState(), sensing=collect(heartbeat_count=1), now=now
    )
    assert journal is None


@pytest.mark.asyncio
async def test_sensing_and_archive_without_llm(db):
    """拔管：无 LLM 仍可传感与归档。"""
    snap = collect(heartbeat_count=3)
    assert snap.uptime_seconds >= 0
    await db.save_narrative_memory("轻记忆", importance=0.15)
    layer = ActionLayer(db, {"action": {"autonomous_daily_limit": 2}})
    result = await layer.execute_kind(
        "archive",
        EmotionState(),
        "friend",
        "spring",
        datetime(2026, 7, 27, 16, 0),
        mode="solitary",
        sensing=snap,
    )
    assert result is not None
    assert result["type"] == "self_archive"
    assert layer.last_closed_loop is not None
    assert layer.last_closed_loop["op"] == "archive"


@pytest.mark.asyncio
async def test_journal_writes_consciousness(db):
    ops = SelfOps(db)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 1}})
    result = await ops.write_inner_journal(
        budget,
        EmotionState(curiosity=0.5, valence=0.1),
        sensing=collect(heartbeat_count=9),
        now=datetime(2026, 7, 27, 17, 0),
    )
    assert result is not None
    rows = await db.load_recent_consciousness(
        limit=5, hours=48, stream_type="self_journal"
    )
    assert any(r["id"] == result["stream_id"] for r in rows)
