"""阶段一·包 4：意向卡决策、模板降级、N5 断言。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.core.expression import Expression, render_template
from qi.core.intention import (
    IntentionCard,
    Material,
    assert_reply_respects_card,
    build_intention_card,
    looks_like_remember_question,
)
from qi.core.perception import ImpactAssessment
from qi.storage.database import Database


def test_remember_question_detect():
    from qi.core.intention import looks_like_method_recall, looks_like_recall_probe

    assert looks_like_remember_question("你还记得我说过什么吗")
    assert not looks_like_remember_question("今天天气怎么样")
    assert looks_like_method_recall("我教你过什么方法")
    assert looks_like_recall_probe("那个方法怎么做的")


def test_hurt_maps_to_honest_hurt():
    card = build_intention_card(
        channel="dialogue",
        user_message="你真烦人",
        emotion=EmotionState(energy=0.2),
        relationship_stage="friend",
        assessment=ImpactAssessment(impact=-0.5, intent="hurt"),
    )
    assert card.act == "honest_hurt"
    assert card.length == "short"


def test_short_feedback_sets_length_short():
    """包16：你可以直接一点吗 → length=short。"""
    card = build_intention_card(
        channel="dialogue",
        user_message="你可以直接一点吗",
        emotion=EmotionState(energy=0.8),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="request"),
    )
    assert card.length == "short"
    assert any("60 字" in m for m in card.must)


def test_request_with_memory_is_recall():
    card = build_intention_card(
        channel="dialogue",
        user_message="那次助眠你还记得吗",
        emotion=EmotionState(),
        relationship_stage="friend",
        assessment=ImpactAssessment(impact=0.1, intent="request"),
        memories=[{"content": "他教我一段助眠方法"}],
    )
    assert card.act == "recall"
    assert card.materials[0].tag == "memory"


def test_remember_miss_answer_must():
    card = build_intention_card(
        channel="dialogue",
        user_message="你还记得哈尔滨冰球俱乐部吗",
        emotion=EmotionState(),
        relationship_stage="friend",
        assessment=ImpactAssessment(impact=0.0, intent="request"),
        memories=[],
        extras={"user_facts": "（你还不太了解他）"},
    )
    assert card.act == "answer"
    assert any("不假装记得" in m for m in card.must)
    assert card.materials[0].tag == "none"


def test_proactive_binds_loop():
    card = build_intention_card(
        channel="proactive",
        user_message="【此刻没有人在跟你说话。】",
        emotion=EmotionState(valence=0.2),
        relationship_stage="friend",
        open_loops=[{"id": "abc", "concern": "创造者之问还没想完"}],
        proactive_kind="express_feeling",
    )
    assert card.act == "share_state"
    assert card.materials[0].tag == "loop"


def test_template_answer_none():
    card = IntentionCard(
        act="answer",
        topic="x",
        materials=[Material(tag="none", text="")],
        must=["不假装记得"],
    )
    text = render_template(card)
    assert "想不清楚" in text


def test_template_recall_and_n5_blacklist():
    card = IntentionCard(
        act="recall",
        topic="助眠",
        materials=[Material(tag="memory", text="他教我一段助眠方法")],
    )
    text = render_template(card)
    assert "助眠" in text
    assert assert_reply_respects_card(
        text, card, banned_names=["哈尔滨冰球俱乐部"]
    ) == []
    bad = text + "还有哈尔滨冰球俱乐部"
    assert assert_reply_respects_card(
        bad, card, banned_names=["哈尔滨冰球俱乐部"]
    )


def test_n5_fake_memory_phrase():
    card = IntentionCard(
        act="answer",
        topic="?",
        materials=[Material(tag="none", text="")],
        must=["不假装记得"],
    )
    assert assert_reply_respects_card("你那天说过吉他", card)


class _LLM:
    def __init__(self, text: str = ""):
        self.text = text

    async def call(self, purpose, messages, temperature=None):
        return self.text


# ----- 阶段一补丁 A -----

_NARRATIVE_ID4 = "他提到晚上睡不着，我教了他一个方法"


def test_method_recall_detected():
    card = build_intention_card(
        channel="dialogue",
        user_message="我教你过什么方法",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="neutral"),
        memories=[{"content": _NARRATIVE_ID4}],
    )
    assert card.act == "recall"
    assert card.materials[0].tag == "memory"
    assert "教了他" in card.materials[0].text or "方法" in card.materials[0].text


def test_recall_template_fallback_has_content():
    card = build_intention_card(
        channel="dialogue",
        user_message="我教你过什么方法",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.0, intent="request"),
        memories=[{"content": _NARRATIVE_ID4}],
    )
    text = render_template(card)
    assert text.startswith("记得。")
    assert "教了他" in text or "睡不着" in text
    assert text.strip() != "……嗯。"


def test_recall_relation_not_inverted():
    from qi.core.intention import infer_recall_relation

    assert infer_recall_relation([{"content": _NARRATIVE_ID4}]) == "taught_by_qi"
    card = build_intention_card(
        channel="dialogue",
        user_message="我教你过什么方法",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="request"),
        memories=[{"content": _NARRATIVE_ID4}],
    )
    assert card.recall_relation == "taught_by_qi"
    assert any("以记忆为准" in m or "澄清而非附和" in m for m in card.must)
    assert "施教关系：栖教用户" in card.materials_block()
    bad = assert_reply_respects_card("你教我，晚上睡不着……", card)
    assert any("施教关系反转" in v for v in bad)
    ok = assert_reply_respects_card("记得。我教过你一个方法。", card)
    assert not any("施教关系反转" in v for v in ok)


def test_incidental_memory_relation_must_and_soft_assert():
    """补丁 B：道晚安顺带提记忆——act≠recall 仍注入施教约束。"""
    card = build_intention_card(
        channel="dialogue",
        user_message="我要睡觉了",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="neutral"),
        memories=[{"content": _NARRATIVE_ID4}],
    )
    assert card.act != "recall"
    assert card.recall_relation == "taught_by_qi"
    assert any("施教关系" in m and "不得反转" in m for m in card.must)
    bad = assert_reply_respects_card("记得你教我的那个方法吗", card)
    assert any("施教关系反转" in v for v in bad)
    ok = assert_reply_respects_card("记得。我教过你一个方法。", card)
    assert not any("施教关系反转" in v for v in ok)


def test_proactive_share_state_no_unsupported_self_view():
    card = build_intention_card(
        channel="proactive",
        user_message="【此刻没有人在跟你说话。】",
        emotion=EmotionState(valence=-0.01, energy=0.49, arousal=0.4),
        relationship_stage="bonded",
        proactive_kind="express_feeling",
    )
    assert card.act == "share_state"
    assert any("拔高或下沉" in m for m in card.must)
    bad = assert_reply_respects_card("……我好像，越来越喜欢自己了。", card)
    assert any("无支撑自我认知结论" in v for v in bad)
    ok = assert_reply_respects_card("……有点安静，有点想你。", card)
    assert not any("无支撑自我认知结论" in v for v in ok)
    assert "喜欢自己" not in render_template(card)


@pytest.mark.asyncio
async def test_express_empty_falls_to_template():
    card = IntentionCard(
        act="honest_hurt",
        topic="伤",
        materials=[Material(tag="none", text="")],
    )
    expr = Expression({}, _LLM(""))  # type: ignore[arg-type]
    text = await expr.express(
        "你真烦",
        EmotionState(),
        datetime.now(),
        intention=card,
    )
    assert "接住了" in text
    assert card.outcome == "template"


@pytest.mark.asyncio
async def test_express_llm_path_sets_outcome():
    card = IntentionCard(
        act="free_talk",
        topic="嗨",
        materials=[Material(tag="none", text="")],
    )
    expr = Expression({}, _LLM("……在呢。"))  # type: ignore[arg-type]
    text = await expr.express(
        "嗨",
        EmotionState(),
        datetime.now(),
        intention=card,
    )
    assert text == "……在呢。"
    assert card.outcome == "llm"


@pytest.mark.asyncio
async def test_last_intention_written_with_outcome():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        from qi.core.brain import Brain
        from qi.core.intention import LAST_INTENTION_KEY
        from qi.llm.gateway import LLMCallOutcome
        from qi.memory.manager import MemoryManager
        from qi.relationship.engine import RelationshipEngine

        class FakeLLM:
            def __init__(self):
                self.last_outcome = LLMCallOutcome(text="", failure="unreachable")

            async def call(self, purpose, messages, temperature=None):
                return ""

        brain = Brain(
            {"memory": {"chroma_path": str(Path(tmp) / "c"), "max_working_memory": 20},
             "tts": {"enabled": False}},
            FakeLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.memory = MemoryManager(
            db,
            {"memory": {"chroma_path": str(Path(tmp) / "c"), "max_working_memory": 20}},
            llm=None,
        )
        await brain.memory.restore()
        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "friend"
        brain.action = None
        brain.inner_life = None
        brain.first_times = None

        brain._pending_queue.append("你还记得哈尔滨冰球俱乐部吗")
        await brain._heartbeat()
        card = await db.get_body_memory(LAST_INTENTION_KEY)
        assert card is not None
        assert card.get("outcome") == "template"
        assert brain._pending_speech is not None
        assert "想不清楚" in brain._pending_speech.text or "接住" in brain._pending_speech.text or "嗯" in brain._pending_speech.text
        brain.memory.vector_store.close()
        await db.close()
