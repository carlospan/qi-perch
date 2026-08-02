"""阶段二·补丁 C：volition mode 分档与日限。"""

from __future__ import annotations

from datetime import datetime

import pytest
from qi.action.budget import ActionBudget
from qi.action.layer import ActionLayer
from qi.action.volition import action_intentions
from qi.core.emotion import EmotionState


def test_awake_allows_self_ops_not_outward():
    now = datetime(2026, 8, 2, 12, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    intents = action_intentions(
        mode="awake",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.3,
        has_undelivered_creation=True,
        tend_occasion="anniversary",
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
        archivable_count=2,
        open_loop_count=1,
        energy=0.8,
    )
    kinds = {i.kind for i in intents}
    assert "archive" in kinds
    assert "journal" in kinds
    assert "share" not in kinds
    assert "explore" not in kinds
    assert "tend" not in kinds


def test_solitary_still_allows_explore():
    now = datetime(2026, 8, 2, 12, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    intents = action_intentions(
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
        archivable_count=0,
        energy=0.7,
    )
    assert any(i.kind == "explore" for i in intents)


def test_autonomous_daily_limit_three():
    now = datetime(2026, 8, 2, 14, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    assert budget.can_autonomous(now)
    budget.record("archive", now)
    budget.record("journal", now)
    budget.record("budget_tune", now)
    assert not budget.can_autonomous(now)


def test_default_budget_limit_is_twenty():
    budget = ActionBudget({})
    assert budget.daily_limit == 20


def test_journal_candidate_at_three_hours_without_open_loop():
    """补丁 D：journal 候选 uptime≥3h，不要求 open_loop。"""
    now = datetime(2026, 8, 2, 15, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    base = dict(
        mode="awake",
        relationship_stage="friend",
        curiosity=0.5,
        valence=0.1,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
        archivable_count=0,
        open_loop_count=0,
        energy=0.6,
    )
    with_uptime = action_intentions(
        **base, sensing_uptime_seconds=3 * 3600 + 1
    )
    assert any(i.kind == "journal" for i in with_uptime)
    short = action_intentions(**base, sensing_uptime_seconds=2 * 3600)
    assert all(i.kind != "journal" for i in short)


@pytest.mark.asyncio
async def test_execute_kind_awake_self_ops_only(db):
    await db.save_narrative_memory("可归档闲话", importance=0.1)
    layer = ActionLayer(db, {"action": {"autonomous_daily_limit": 3}})
    now = datetime(2026, 8, 2, 13, 0)
    emotion = EmotionState()
    archived = await layer.execute_kind(
        "archive",
        emotion,
        "friend",
        "spring",
        now,
        mode="awake",
    )
    assert archived is not None
    assert archived["type"] == "self_archive"

    layer2 = ActionLayer(db, {"action": {"autonomous_daily_limit": 3}})
    explore = await layer2.execute_kind(
        "explore",
        EmotionState(curiosity=0.9),
        "friend",
        "spring",
        now,
        mode="awake",
    )
    assert explore is None
