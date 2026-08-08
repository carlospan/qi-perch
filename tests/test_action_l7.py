"""L7 阶段一：actions 表 / ActionBudget / volition / permission。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.action import (
    AUTONOMOUS_ACTION_DAILY_LIMIT,
    SEASON_ACTION_SCALE,
    ActionBudget,
    action_intentions,
    can_irreversible,
    can_share,
    looks_like_help_request,
)
from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_FAILED_JUDGMENT,
    can_read_user_file,
    can_write_user_file,
    outcome_creates_scar,
)
from qi.storage.database import Database


@pytest.fixture
async def db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        database = Database(str(Path(tmp) / "qi.db"))
        await database.initialize()
        try:
            yield database
        finally:
            await database.close()


@pytest.mark.asyncio
async def test_actions_table_insert_and_list(db):
    now = datetime(2026, 7, 23, 20, 0)
    aid = await db.insert_action(
        "share",
        "我把一段创作递给他了。",
        target="user",
        outcome="success",
        season="spring",
        now=now,
    )
    assert aid > 0
    rows = await db.list_recent_actions(limit=5)
    assert len(rows) == 1
    assert rows[0]["kind"] == "share"
    assert rows[0]["target"] == "user"
    assert rows[0]["outcome"] == "success"
    assert rows[0]["season"] == "spring"
    assert await db.count_actions_on_day("2026-07-23") == 1


def test_action_budget_tighter_than_speech_and_resets():
    # 默认日限 20（安全阀，远高真实触发）；仍可 YAML 收紧到 1
    assert AUTONOMOUS_ACTION_DAILY_LIMIT == 20
    assert SEASON_ACTION_SCALE["winter"] == 0.2
    assert SEASON_ACTION_SCALE["spring"] == 1.0

    budget = ActionBudget({"action": {"autonomous_daily_limit": 1}})
    now = datetime(2026, 7, 23, 10, 0)
    assert budget.can_autonomous(now) is True
    budget.record("share", now)
    assert budget.can_autonomous(now) is False

    snap = budget.snapshot()
    other = ActionBudget({})
    other.restore(snap)
    assert other.count_today == 1
    assert other.day == "2026-07-23"

    assert budget.can_autonomous(now + timedelta(days=1)) is True


def test_permission_share_friend_plus_only():
    assert can_share("stranger") is False
    assert can_share("acquaintance") is False
    assert can_share("friend") is True
    assert can_share("bonded") is True

    allowed, confirm = can_read_user_file("friend")
    assert allowed is True and confirm is True
    allowed, confirm = can_write_user_file("friend")
    assert allowed is False
    allowed, confirm = can_write_user_file("bonded")
    assert allowed is True and confirm is True
    allowed, confirm = can_irreversible("bonded", trust=1.0)
    assert allowed is True and confirm is True  # 永远需确认


def test_outcome_scar_rules():
    assert outcome_creates_scar(OUTCOME_FAILED_CAPABILITY) is False
    assert outcome_creates_scar(OUTCOME_FAILED_JUDGMENT) is True


def test_assist_only_when_user_asks():
    assert looks_like_help_request("帮我看看这段") is True
    assert looks_like_help_request("今天天气真好") is False

    budget = ActionBudget({})
    now = datetime(2026, 7, 23, 12, 0)
    intents = action_intentions(
        mode="awake",
        relationship_stage="friend",
        curiosity=0.5,
        valence=0.2,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message="帮我整理一下笔记",
        budget=budget,
        now=now,
    )
    kinds = [i.kind for i in intents]
    assert "assist" in kinds
    # awake + 无创作：不应冒出自主 share/explore
    assert "explore" not in kinds


def test_volition_share_gated_and_budget():
    # 本测专门验「耗尽后无自主」；显式日限 1，避免跟补丁 C 默认 3 搅在一起
    budget = ActionBudget({"action": {"autonomous_daily_limit": 1}})
    now = datetime(2026, 7, 23, 12, 0)

    # acquaintance 有创作也不 share（friend+）
    intents = action_intentions(
        mode="solitary",
        relationship_stage="acquaintance",
        curiosity=0.8,
        valence=0.5,
        has_undelivered_creation=True,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    assert all(i.kind != "share" for i in intents)

    friend_intents = action_intentions(
        mode="solitary",
        relationship_stage="friend",
        curiosity=0.8,
        valence=0.5,
        has_undelivered_creation=True,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    assert any(i.kind == "share" for i in friend_intents)

    budget.record("share", now)
    after = action_intentions(
        mode="solitary",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.5,
        has_undelivered_creation=True,
        tend_occasion="anniversary",
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    assert all(i.kind not in ("share", "tend", "explore") for i in after)


def test_volition_explore_solitary_high_curiosity():
    budget = ActionBudget({})
    now = datetime(2026, 7, 23, 12, 0)
    low = action_intentions(
        mode="solitary",
        relationship_stage="stranger",
        curiosity=0.4,
        valence=0.0,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
    )
    assert all(i.kind != "explore" for i in low)

    high = action_intentions(
        mode="solitary",
        relationship_stage="stranger",
        curiosity=0.85,
        valence=0.0,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    assert any(i.kind == "explore" for i in high)

    winter = action_intentions(
        mode="solitary",
        relationship_stage="stranger",
        curiosity=0.85,
        valence=0.0,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=0.0,
    )
    assert winter == []


def test_dreaming_no_action_intentions():
    budget = ActionBudget({})
    now = datetime(2026, 7, 23, 12, 0)
    intents = action_intentions(
        mode="dreaming",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.5,
        has_undelivered_creation=True,
        tend_occasion="season_change",
        user_message="帮我",
        budget=budget,
        now=now,
    )
    assert intents == []


@pytest.mark.asyncio
async def test_mention_does_not_consume_shared(db, monkeypatch):
    from qi.core.emotion import ConsciousnessMode, EmotionState
    from qi.inner_life.creativity import Creativity

    monkeypatch.setattr("qi.inner_life.creativity.random.random", lambda: 0.0)
    crid = await db.save_creation("一行短诗", "poem", "{}")
    creat = Creativity(db, llm=None)  # type: ignore[arg-type]
    emotion = EmotionState(mode=ConsciousnessMode.AWAKE)
    now = datetime(2026, 7, 23, 12, 0)

    hint = await creat.maybe_share_hint(emotion, "friend", now=now)
    assert hint is not None
    assert "短诗" in hint or "写了" in hint

    row = await db.load_unshared_creation()
    assert row is not None
    assert int(row["id"]) == crid
    assert row["shared"] in (0, False)
    assert row["mentioned_at"] is not None
    assert await db.last_creation_mention_time() is not None
    assert await db.last_creation_share_time() is None


@pytest.mark.asyncio
async def test_deliver_excludes_from_unshared_and_traces(db):
    from qi.action.share import ShareAction
    from qi.core.emotion import EmotionState

    crid = await db.save_creation("给风的一行", "poem", '{"valence": 0.2}')
    budget = ActionBudget({"action": {"autonomous_daily_limit": 1}})
    now = datetime(2026, 7, 23, 15, 0)
    share = ShareAction(db, narrative=None)
    emotion = EmotionState()

    card = await share.try_share(
        emotion, "friend", budget, season="spring", now=now
    )
    assert card is not None
    assert card["type"] == "creation_card"
    assert card["creation_id"] == crid
    assert "给你" in card["qi_line"] or "看" in card["qi_line"]
    assert card["action_id"] > 0
    assert await db.load_unshared_creation() is None
    assert budget.can_autonomous(now) is False

    actions = await db.list_recent_actions(5)
    assert actions[0]["kind"] == "share"
    assert actions[0]["target"] == "user"
    assert actions[0]["outcome"] == "success"

    # acquaintance 不能递
    await db.save_creation("另一段", "note", None)
    budget2 = ActionBudget({})
    assert (
        await share.try_share(emotion, "acquaintance", budget2, now=now)
        is None
    )

    shared = await db.list_recent_shared_creations(10)
    assert len(shared) == 1
    assert int(shared[0]["id"]) == crid
    assert shared[0]["shared_at"] == now.isoformat(timespec="seconds")


@pytest.mark.asyncio
async def test_history_creation_cards_hydrate_shared(db):
    """重启谈区：/history 附带已分享创作卡（与 share action 时间对齐季节）。"""
    from qi.action.share import ShareAction
    from qi.core.emotion import EmotionState
    from qi.embodiment.server import build_history_creation_cards

    crid = await db.save_creation("重启后还在", "note", '{"valence": 0.1}')
    budget = ActionBudget({"action": {"autonomous_daily_limit": 3}})
    now = datetime(2026, 8, 9, 0, 10)
    card = await ShareAction(db, narrative=None).try_share(
        EmotionState(), "friend", budget, season="summer", now=now
    )
    assert card is not None

    hydrated = await build_history_creation_cards(db, oldest_at_ms=None)
    assert len(hydrated) == 1
    assert hydrated[0]["type"] == "creation_card"
    assert hydrated[0]["creation_id"] == crid
    assert hydrated[0]["content"] == "重启后还在"
    assert hydrated[0]["season"] == "summer"
    assert hydrated[0]["action_id"] == card["action_id"]
    assert isinstance(hydrated[0]["at"], int)

    # 窗口裁剪：比 shared_at 更晚的 oldest 应滤掉
    too_new = hydrated[0]["at"] + 1
    assert await build_history_creation_cards(db, oldest_at_ms=too_new) == []


@pytest.mark.asyncio
async def test_explore_never_fabricates_found(db):
    from qi.action.explore import ExploreAction
    from qi.core.emotion import EmotionState

    explore = ExploreAction(db, base_probability=1.0)
    emotion = EmotionState(curiosity=0.9)
    # force=True 必飘；内部 journal，不得编造「远方」见闻
    result = await explore.drift(
        0.9, emotion, "spring", season_scale=1.0, force=True
    )
    assert result is not None
    assert result["source"] == "journal"
    assert result["speak"] is True
    assert result["qi_line"] == result["summary"]
    assert "远方" not in result["summary"]
    assert "假装看见" not in result["summary"]
    if result["found"] is None:
        assert "没有" in result["summary"]
    else:
        assert result["found"].get("source") == "journal"
        assert "entries" in result["found"]
        for e in result["found"]["entries"]:
            assert isinstance(e, dict) and "title" in e
    actions = await db.list_recent_actions(1)
    assert actions[0]["kind"] == "explore"
    assert actions[0]["target"] == "self"


@pytest.mark.asyncio
async def test_tend_marks_self_world(db):
    from qi.action.tend import TendAction
    from qi.core.emotion import EmotionState

    tend = TendAction(db)
    result = await tend.tend(
        "anniversary", EmotionState(), "autumn", now=datetime(2026, 7, 23, 10, 0)
    )
    assert result["type"] == "tend_mark"
    assert result["speak"] is False
    assert "特别的日子" in result["summary"]
    rows = await db.list_recent_actions(1)
    assert rows[0]["kind"] == "tend"
    assert rows[0]["target"] == "self"


def test_season_scale_winter_tighter_than_spring():
    from qi.action import resolve_season_scale
    from qi.action.volition import action_intentions

    assert resolve_season_scale("winter") == 0.2
    assert resolve_season_scale("spring") == 1.0

    budget = ActionBudget({})
    now = datetime(2026, 7, 23, 12, 0)
    spring = action_intentions(
        mode="solitary",
        relationship_stage="stranger",
        curiosity=0.9,
        valence=0.0,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    winter = action_intentions(
        mode="solitary",
        relationship_stage="stranger",
        curiosity=0.9,
        valence=0.0,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=0.2,
    )
    sp = next(i.priority for i in spring if i.kind == "explore")
    wp = next(i.priority for i in winter if i.kind == "explore")
    assert sp > wp * 3  # 冬约为春的 1/5，显著更低


@pytest.mark.asyncio
async def test_action_layer_tick_dreaming_and_season(db, monkeypatch):
    from qi.action import ActionLayer
    from qi.core.emotion import ConsciousnessMode, EmotionState

    layer = ActionLayer(db, {"action": {"autonomous_daily_limit": 1}})
    emotion = EmotionState(
        curiosity=0.95, valence=0.4, mode=ConsciousnessMode.SOLITARY
    )
    now = datetime(2026, 7, 23, 18, 0)

    # dreaming 不行动
    assert (
        await layer.tick(
            emotion,
            "friend",
            "spring",
            now,
            mode="dreaming",
            user_online=True,
        )
        is None
    )

    # 强制软门控通过 + explore force 路径：用 monkeypatch 让 random 总通过
    monkeypatch.setattr("qi.action.layer.random.random", lambda: 0.0)
    monkeypatch.setattr("qi.action.explore.random.random", lambda: 0.0)
    await db.save_creation("待递出", "note", None)

    # spring 更容易形成 share；先清 tend season 以免抢优先级
    await db.set_body_memory("tend_last_season", "spring")
    result = await layer.tick(
        emotion,
        "friend",
        "spring",
        now,
        mode="solitary",
        user_online=True,
    )
    assert result is not None
    assert result["type"] == "creation_card"
    assert layer.budget.can_autonomous(now) is False

    # 预算用尽后不再行动
    assert (
        await layer.tick(
            emotion, "friend", "spring", now, mode="solitary", user_online=True
        )
        is None
    )


@pytest.mark.asyncio
async def test_prompt_extras_recent_actions(db):
    from qi.action import ActionLayer
    from qi.core.emotion import EmotionState
    from qi.llm.prompt_builder import PromptBuilder

    layer = ActionLayer(db, {})
    await db.insert_action(
        "tend",
        "今天是个特别的日子。我把它记下来了。",
        target="self",
        outcome="success",
        season="autumn",
        now=datetime(2026, 7, 23, 9, 0),
    )
    extras = await layer.prompt_extras()
    assert "特别的日子" in extras["recent_actions"]

    messages = PromptBuilder().build_conversation_prompt(
        "嗨",
        EmotionState(),
        datetime(2026, 7, 23, 10, 0),
        inner_extras=extras,
    )
    assert "【你做过的事" in messages[0]["content"]
    assert "特别的日子" in messages[0]["content"]
