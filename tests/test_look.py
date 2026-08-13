"""L7 look：瞥视解析、门控与 glance。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.budget import ActionBudget
from qi.action.layer import ActionLayer
from qi.action.look import (
    FALLBACK_QI_LINE,
    FIRST_NOTICE_LINE,
    LookAction,
    looks_like_look_invite,
    looks_like_look_pause,
    looks_like_look_resume,
)
from qi.action.permission import can_look
from qi.action.volition import action_intentions
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database


def test_look_invite_positive_negative():
    # 强启发式：含昨夜漏检句式
    assert looks_like_look_invite("你能看到我现在在做什么吗？")
    assert looks_like_look_invite("你能看到我在做什么吗？")
    assert looks_like_look_invite("现在呢？你能看到我在做什么吗？")
    assert looks_like_look_invite("限制呢？你能看到我在做什么吗？")
    assert looks_like_look_invite("看看我屏幕")
    assert looks_like_look_invite("猜猜我在干什么")
    assert looks_like_look_invite("你看得见这边吗")
    assert looks_like_look_invite("我屏幕上是什么")
    # 反例
    assert not looks_like_look_invite("你在干嘛")
    assert not looks_like_look_invite("在吗")
    assert not looks_like_look_invite("帮我看看这个文件 note.txt")
    assert not looks_like_look_invite("你觉得我该做什么")
    assert not looks_like_look_invite("你还记得我上次在做什么吗")


@pytest.mark.asyncio
async def test_detect_look_invite_llm_weak_candidate():
    from qi.action.look import detect_look_invite

    class _Yes:
        async def call(self, purpose, messages, temperature=None):
            assert purpose == "fact"
            return "yes"

    class _No:
        async def call(self, purpose, messages, temperature=None):
            return "no"

    # 弱表述：强规则可能不中，靠 LLM
    weak = "你那边能瞄到我这边的画面吗"
    assert not looks_like_look_invite(weak)
    assert await detect_look_invite(weak, llm=_Yes())
    assert not await detect_look_invite(weak, llm=_No())
    # 无 LLM 时弱候选不放行
    assert not await detect_look_invite(weak, llm=None)
    # 强规则仍短路，不调 LLM
    assert await detect_look_invite("看看我屏幕", llm=_No())


def test_look_pause_resume_cues():
    assert looks_like_look_pause("别看")
    assert looks_like_look_pause("不要看屏")
    assert looks_like_look_resume("可以看了")
    assert not looks_like_look_resume("看看我屏幕")


def test_can_look_stages():
    assert not can_look("stranger")
    assert can_look("acquaintance")
    assert can_look("friend")


@pytest.mark.asyncio
async def test_glance_success_has_qi_line(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            assert purpose == "look"
            content = messages[1]["content"]
            assert isinstance(content, list)
            assert content[1]["type"] == "image_url"
            return "好像在看一份文档……"

    look = LookAction(
        db,
        config={"action": {"look": {"min_interval_minutes": 15}}},
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "Code", False),
    )
    now = datetime.now()
    result = await look.glance(
        relationship_stage="friend",
        season="spring",
        now=now,
        reactive=True,
        user_question="你能看到我现在在做什么吗？",
        mode="awake",
    )
    assert result is not None
    assert result["outcome"] == "success"
    assert result["qi_line"]
    assert result.get("speak") is True
    rows = await db.list_recent_actions(limit=1)
    assert rows and rows[0]["kind"] == "look"


@pytest.mark.asyncio
async def test_glance_llm_empty_uses_fallback(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            return ""

    look = LookAction(
        db,
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "x", False),
    )
    result = await look.glance(
        relationship_stage="acquaintance",
        season="spring",
        now=datetime.now(),
        reactive=True,
        mode="awake",
    )
    assert result is not None
    assert result["qi_line"].endswith(FALLBACK_QI_LINE) or result[
        "qi_line"
    ] == FALLBACK_QI_LINE
    assert result.get("speak") is True
    assert FIRST_NOTICE_LINE in result["qi_line"] or result[
        "qi_line"
    ] == FALLBACK_QI_LINE


@pytest.mark.asyncio
async def test_first_notice_prefixed_not_from_llm(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()
    seen_system = []

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            seen_system.append(messages[0]["content"])
            return "好像在写字。"

    look = LookAction(
        db,
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "x", False),
    )
    r1 = await look.glance(
        relationship_stage="friend",
        season="spring",
        now=datetime.now(),
        reactive=True,
        mode="awake",
    )
    assert r1 is not None
    assert r1["qi_line"].startswith(FIRST_NOTICE_LINE)
    assert "可自然提一句" not in seen_system[0]
    assert "只当现场" not in seen_system[0]
    r2 = await look.glance(
        relationship_stage="friend",
        season="spring",
        now=datetime.now(),
        reactive=True,
        mode="awake",
    )
    assert r2 is not None
    assert not r2["qi_line"].startswith(FIRST_NOTICE_LINE)


@pytest.mark.asyncio
async def test_autonomous_no_double_success_under_lock(tmp_path):
    """并发自主 glance 不得连成两次成功。"""
    import asyncio

    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            await asyncio.sleep(0.05)
            return "瞥见了。"

    look = LookAction(
        db,
        config={"action": {"look": {"min_interval_minutes": 15}}},
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "Editor", False),
    )
    now = datetime.now()
    results = await asyncio.gather(
        look.try_autonomous(
            relationship_stage="friend", season="spring", now=now, mode="solitary"
        ),
        look.try_autonomous(
            relationship_stage="friend", season="spring", now=now, mode="solitary"
        ),
    )
    ok = [r for r in results if r is not None and r.get("outcome") == "success"]
    assert len(ok) == 1


@pytest.mark.asyncio
async def test_autonomous_interval_and_san_bu_guo_san(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            return "瞥见一点光。"

    look = LookAction(
        db,
        config={"action": {"look": {"min_interval_minutes": 15}}},
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "Editor", False),
    )
    now = datetime.now()
    r1 = await look.try_autonomous(
        relationship_stage="friend", season="spring", now=now, mode="solitary"
    )
    assert r1 is not None
    # 紧接着应被防连瞥挡住（软门）
    r2 = await look.try_autonomous(
        relationship_stage="friend", season="spring", now=now, mode="solitary"
    )
    assert r2 is None
    r3 = await look.try_autonomous(
        relationship_stage="friend", season="spring", now=now, mode="solitary"
    )
    assert r3 is None
    # 第 3 次冲动：soft_count>=2 → 软门放行
    r4 = await look.try_autonomous(
        relationship_stage="friend",
        season="spring",
        now=now,
        mode="solitary",
    )
    assert r4 is not None


@pytest.mark.asyncio
async def test_pause_blocks_autonomous_invite_clears(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            return "看到了。"

    look = LookAction(
        db,
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "x", False),
    )
    now = datetime.now()
    await look.set_pause(now)
    assert await look.is_paused(now + timedelta(minutes=10))
    assert (
        await look.try_autonomous(
            relationship_stage="friend",
            season="spring",
            now=now,
            mode="solitary",
        )
        is None
    )
    r = await look.glance(
        relationship_stage="friend",
        season="spring",
        now=now,
        reactive=True,
        user_question="看看我屏幕",
        mode="awake",
    )
    assert r is not None
    assert not await look.is_paused(now)


def test_look_intention_silence_boost():
    budget = ActionBudget({"action": {"autonomous_daily_limit": 20}})
    now = datetime.now()
    base = dict(
        mode="solitary",
        relationship_stage="acquaintance",
        curiosity=0.7,
        valence=0.1,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
    )
    short = action_intentions(**base, silence_seconds=60)
    long = action_intentions(**base, silence_seconds=25 * 60)
    look_s = next(i for i in short if i.kind == "look")
    look_l = next(i for i in long if i.kind == "look")
    assert look_l.priority > look_s.priority


class _FakeLLM:
    def __init__(self, text: str = "嗯。") -> None:
        self.text = text

    async def call(self, purpose, messages, temperature=None):
        return self.text


@pytest.mark.asyncio
async def test_brain_look_invite_dialog(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _FakeLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        layer = ActionLayer(db, {}, llm=_FakeLLM("你好像在写东西。"))
        layer.look._capture_fn = lambda: (b"\xff\xd8\xff", "Doc", False)
        brain.action = layer
        brain.inner_life = None
        brain.first_times = None
        brain.memory = None
        brain.user_online = True
        brain.emotion = EmotionState(
            mode=ConsciousnessMode.AWAKE, curiosity=0.5, energy=0.7, valence=0.2
        )
        rel = MagicMock()
        rel.state.stage = "friend"
        rel.state.trust = 0.7
        rel.state.season = "spring"
        brain.relationship = rel

        with (
            patch.object(
                brain, "_deliver_action_result", new_callable=AsyncMock
            ) as deliver,
            patch.object(brain, "_heartbeat", new_callable=AsyncMock),
        ):
            line = await brain.receive_user_message(
                "你能看到我现在在做什么吗？"
            )
        assert line
        deliver.assert_awaited()
        payload = deliver.await_args.args[0]
        assert payload.get("speak") is True
        assert payload.get("type") == "look_glance"
