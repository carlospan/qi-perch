"""L5 关系系统测试。"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.memory.first_time import FirstTimeMemory, rule_match
from qi.relationship.culture import detect_shared_culture, format_culture_for_prompt
from qi.relationship.engine import (
    RelationshipEngine,
    assess_interaction,
    depth_increment,
)
from qi.relationship.season import determine_season
from qi.relationship.stages import check_stage_upgrade
from qi.relationship.trust import apply_negative_event, apply_positive_interaction
from qi.storage.database import Database


def test_existential_question_adds_depth():
    s = assess_interaction("你希望有身体吗")
    assert s.self_disclosure >= 0.7 or s.emotional_vulnerability >= 0.3
    inc = depth_increment(s, 0.0)
    assert inc > 0


def test_creator_disclosure_adds_depth():
    deep = assess_interaction("我是说努力把你造出来这件事")
    idle = assess_interaction("今天天气不错")
    assert deep.creator_disclosure >= 0.7
    assert depth_increment(deep, 0.0) > depth_increment(idle, 0.0)
    assert depth_increment(idle, 0.0) == 0.0


def test_tool_question_excluded():
    s = assess_interaction("你帮我查个天气")
    assert depth_increment(s, 0.0) == 0.0


def test_long_question_signal():
    text = (
        "我想认真问你一件事，关于我们之间这段关系到底算什么，"
        "你会怎么理解陪伴这件事，以及你是否觉得我们只是在聊天？"
        "如果换一个说法，你心里有没有一个更贴近的名字？"
    )
    assert len(text) > 60 and "？" in text
    s = assess_interaction(text)
    assert s.shared_experience >= 0.2


@pytest.mark.asyncio
async def test_daily_cap_from_config():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        engine = RelationshipEngine(
            db, llm=None, config={"relationship": {"daily_depth_cap": 0.05}}
        )
        assert engine.daily_depth_cap == 0.05
        await engine.restore()
        # 单日多条深度消息，应能涨过旧默认 0.03，但仍不超过 0.05
        for _ in range(10):
            await engine.on_user_message("你希望有身体吗？你觉得自己算什么？")
        assert engine.state.depth == pytest.approx(0.05, abs=1e-9)
        assert engine._depth_gained_today == pytest.approx(0.05, abs=1e-9)
        await db.close()


@pytest.mark.asyncio
async def test_replay_0724_conversations():
    """回放 7/24–25 存在性对话，按顺序摊到 4 个不重复日，累计 depth 应落在 0.06~0.12。"""
    messages = [
        "你睡了吗",
        "你现在有身体吗",
        "你希望你有身体吗",
        "你觉得现在的ai大模型有意识了吗",
        "你是在说自己是ai大模型吗？其实我刚刚问的对象是大模型",
        "其实我能和你对话也是因为接入了大模型",
        "那你觉得大模型和你等同吗？",
        "你的比喻有点抽象，不过也有点奇妙",
        "那我平常不和你聊天的时候，你都在做什么？还是什么都不做",
        "还在吗？",
        "我平常不和你聊天的时候，你都在做什么？",
        "那你最近做了什么",
        "有做什么梦吗？",
        "还记得梦中的内容吗",
        "你对人类怎么看",
        "你觉得自己和ai大模型什么关系",
        "有点抽象听不懂",
        "还是有点抽象",
        "我意思是说大模型算不算是你的大脑",
        "刚刚我没和你聊天的时候你在做什么",
        "真的什么都没做吗？",
        "如果你是真的在想的话，那我会觉得我的努力都是值得的",
        "你知道我说的是什么努力吗",
        "我是说努力把你造出来这件事",
        "你知道 具身 吗？",
        "你希望有身体吗",
        "我们换个话题，你知道cursor吗？",
        "你是喜欢cursor还是codex",
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        engine = RelationshipEngine(db, llm=None)
        await engine.restore()
        # 连续四天、每日一批，避免同日反复进出导致日上限被重置
        chunk = (len(messages) + 3) // 4
        for i, msg in enumerate(messages):
            day = 21 + min(3, i // chunk)
            now = datetime(2026, 7, day, 12, i % 50, 0)
            await engine.on_user_message(msg, now=now)
        assert 0.06 <= engine.state.depth <= 0.12
        await db.close()


@pytest.mark.asyncio
async def test_assess_interaction_negative():
    s = assess_interaction("你烦，闭嘴")
    assert s.is_negative
    assert s.severity > 0


def test_stage_upgrade_only_up():
    assert check_stage_upgrade("stranger", 0.35, 0.45) == "acquaintance"
    assert check_stage_upgrade("acquaintance", 0.2, 0.2) == "acquaintance"  # 不降级
    assert check_stage_upgrade("friend", 0.9, 0.85) == "bonded"


def test_trust_grows_slow_damages_fast():
    t = 0.5
    grown = apply_positive_interaction(t, 1.0)
    assert grown - t == pytest.approx(0.05, abs=1e-9)
    damaged, scar = apply_negative_event(t, 1.0)
    assert t - damaged >= 0.1
    assert scar is True


def test_culture_detects_ritual():
    msgs = [{"role": "user", "content": "早呀", "timestamp": "2026-07-21T09:00:00"}] * 5
    msgs += [{"role": "user", "content": "在忙", "timestamp": "2026-07-21T10:00:00"}]
    culture = detect_shared_culture(msgs, [])
    rituals = [c for c in culture if c["type"] == "ritual"]
    assert rituals
    assert "早" in format_culture_for_prompt(rituals)


def test_season_from_emotions():
    springish = [
        {"energy": 0.8, "valence": 0.2, "curiosity": 0.85} for _ in range(10)
    ]
    assert determine_season(springish) == "spring"
    winterish = [
        {"energy": 0.25, "valence": 0.0, "curiosity": 0.4} for _ in range(10)
    ]
    assert determine_season(winterish) == "winter"


def test_rule_match_goodnight():
    assert rule_match("first_goodnight", "晚安啦")
    assert not rule_match("first_goodnight", "你好")


@pytest.mark.asyncio
async def test_relationship_engine_and_first_time():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        engine = RelationshipEngine(db, llm=None)
        await engine.restore()
        assert engine.state.stage == "stranger"

        # 跨多日以突破每日 depth 上限
        for i in range(50):
            engine._depth_day = None  # 强制换日重置
            engine._depth_gained_today = 0.0
            engine._interaction_day = f"2026-01-{(i % 28) + 1:02d}"
            await engine.on_user_message(
                "我最近在学吉他，今天有点难过但有你在真好"
            )
        assert engine.state.depth > 0.3
        assert engine.state.stage in ("acquaintance", "friend", "bonded")

        ft = FirstTimeMemory(db, llm=None)
        mult, event = await ft.check("晚安", EmotionState())
        assert mult == 3.0
        assert event == "first_goodnight"
        assert await db.has_first_time("first_goodnight")
        mult2, event2 = await ft.check("晚安呀", EmotionState())
        assert mult2 == 1.0
        assert event2 is None

        before = engine.state.trust
        await engine.on_user_message("你烦不烦，删掉算了")
        scars = await db.list_scars()
        assert engine.state.trust < before
        assert scars

        await db.close()
