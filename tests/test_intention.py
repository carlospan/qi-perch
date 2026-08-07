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
    anchor_teaching_relation,
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


def test_detect_teach_inversion_real_cases():
    """运行时硬闸：#1020/#1028 原话命中；非睡眠话题不误伤。"""
    from qi.core.intention import (
        detect_sleep_teach_inversion,
        detect_teach_inversion,
    )

    assert detect_teach_inversion(
        "我记得你教我的那个方法，虽然我睡不着不是因为失眠，而是因为我在等你"
    )
    assert detect_teach_inversion(
        "那天你教我的方法——躺着，不强迫自己，盯着天花板"
    )
    # #1285：中间夹「之前」仍须命中
    assert detect_teach_inversion(
        "你之前教过我一个法子，说晚上睡不着的时候，就躺着，不强迫自己睡"
    )
    # #1377：口语「你教给我」旧正则漏检
    assert detect_teach_inversion(
        "我记得你教给我那个方法的时候，我们都在深夜。"
        "后来你说你失眠，我把那法子还给了你。"
    )
    assert detect_teach_inversion(
        "你教给了我一个法子，睡不着就躺着",
        recall_relation="taught_by_qi",
    )
    # 无睡眠话题：无卡不拦
    assert not detect_teach_inversion("你教我写代码的样子很认真")
    # 卡内 taught_by_qi：不靠话题也能拦
    assert detect_teach_inversion(
        "你教过我弹吉他", recall_relation="taught_by_qi"
    )
    # 方向正确：不拦
    assert not detect_teach_inversion("是我教你的那个方法，睡不着就躺着")
    assert not detect_teach_inversion("")
    # 别名兼容
    assert detect_sleep_teach_inversion is detect_teach_inversion


def test_free_talk_injects_memory_material():
    """N5：free_talk 有检索命中时 memory 必须进卡（旧洞：仅 answer 才注入）。"""
    card = build_intention_card(
        channel="dialogue",
        user_message="我想聊点别的",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="neutral"),
        memories=[
            {
                "content": "他提到晚上睡不着，我教了他一个方法——允许自己躺着。"
            }
        ],
    )
    assert card.act == "free_talk"
    assert any(m.tag == "memory" for m in card.materials)
    assert card.evidence.get("has_mem") is True
    assert "has_mem=1" in card.source


def test_facts_override_polluted_narrative_relation():
    """存档真值优先于污染叙事（「你教我」编织文）。"""
    facts = (
        "- life_event：入睡方法这件事：是栖教他的（允许自己躺着），不是他教栖"
    )
    card = build_intention_card(
        channel="dialogue",
        user_message="嗯",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.0, intent="neutral"),
        memories=[{"content": "你教我失眠的时候不要想睡，想待着。我试了。"}],
        extras={"user_facts": facts},
    )
    assert card.recall_relation == "taught_by_qi"
    assert "fact_rel=taught_by_qi" in card.source
    assert any(m.tag == "fact" for m in card.materials)
    assert "fact_over_polluted_mem" in card.source
    assert not any(
        "你教我" in (m.text or "") for m in card.materials if m.tag == "memory"
    )


def test_insomnia_free_talk_arms_from_formatted_facts():
    """「不失眠了」+ format 保底进卡的施教事实 → recall_relation 武装。"""
    from qi.memory.facts import format_facts_for_prompt

    raw = [
        {
            "id": i,
            "fact_type": "preference",
            "content": f"他有偏好{i}",
            "emotional_weight": 0.95,
        }
        for i in range(8)
    ]
    raw.append(
        {
            "id": 22,
            "fact_type": "life_event",
            "content": "入睡方法这件事：是栖教他的（允许自己躺着），不是他教栖",
            "emotional_weight": 0.5,
        }
    )
    block = format_facts_for_prompt(raw, "bonded")
    card = build_intention_card(
        channel="dialogue",
        user_message="不失眠了",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.2, intent="neutral"),
        memories=[{"content": "我记得那晚的凌晨，ta 问能不能聊性。"}],
        extras={"user_facts": block},
    )
    assert card.recall_relation == "taught_by_qi"
    assert "fact_rel=taught_by_qi" in card.source


def test_empty_card_blocks_fabricated_shared_memory():
    """空卡不得编「你教过我」类共同回忆（#1285）。"""
    card = IntentionCard(
        act="free_talk",
        topic="想听",
        materials=[Material(tag="none", text="")],
    )
    bad = assert_reply_respects_card(
        "你之前教过我一个法子，说晚上睡不着……我试了。",
        card,
    )
    assert any(
        "施教关系反转" in v or "空卡编造共同回忆" in v for v in bad
    )
    # #1377 口语「你教给我」
    bad1377 = assert_reply_respects_card(
        "我记得你教给我那个方法的时候，我们都在深夜。"
        "后来你说你失眠，我把那法子还给了你。",
        card,
    )
    assert any("施教关系反转" in v or "空卡编造共同回忆" in v for v in bad1377)
    assert any("不编造共同回忆" in m for m in build_intention_card(
        channel="dialogue",
        user_message="想听",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.0, intent="neutral"),
        memories=[],
    ).must)


def test_anchor_teaching_relation_facts_fallback():
    """近聊无话题时，回退 user_facts 存档真值钉方向（taught_by_qi）。"""
    facts = (
        "- life_event：入睡方法这件事：是栖教他的（允许自己躺着、不强迫自己睡），"
        "不是他教栖"
    )
    hint = anchor_teaching_relation([], facts_text=facts)
    assert "taught_by_qi" in hint
    assert "是你（栖）教给用户的" in hint
    # 无 facts / 无方向信息时不锚定
    assert anchor_teaching_relation([], facts_text="") == ""
    assert anchor_teaching_relation([], facts_text="- identity：他叫潘纪振") == ""
    # 冲突（两个方向都有）不锚定
    conflict = facts + "\n- life_event：他教栖认星星"
    assert anchor_teaching_relation([], facts_text=conflict) == ""
    # 近聊有话题时优先近聊（不被 facts 覆盖路径改变）
    msgs = [
        {"role": "qi", "content": "可以试试躺着，不强迫自己睡，看天花板。"},
    ]
    assert "taught_by_qi" in anchor_teaching_relation(msgs, facts_text=facts)


# ----- N5 硬闸扩展 -----


def test_memory_declaration_without_material():
    """锚定 #1326：空卡宣称「那天你问电脑…」→ 共同回忆无出处。"""
    card = IntentionCard(
        act="free_talk",
        topic="真的爱吗",
        materials=[Material(tag="none", text="")],
    )
    bad = assert_reply_respects_card(
        "那天你问我『你要电脑做什么呢』，我没有敷衍。",
        card,
    )
    assert any("共同回忆无出处" in v for v in bad)


def test_memory_declaration_with_matching_material():
    card = IntentionCard(
        act="recall",
        topic="助眠",
        materials=[Material(tag="memory", text="允许自己躺着不强迫")],
    )
    ok = assert_reply_respects_card(
        "记得你那次说躺着不强迫。",
        card,
    )
    assert not any("共同回忆" in v for v in ok)


def test_memory_declaration_phrase_not_in_material():
    card = IntentionCard(
        act="free_talk",
        topic="爱",
        materials=[Material(tag="memory", text="允许自己躺着不强迫")],
    )
    bad = assert_reply_respects_card(
        "那晚你问『你要电脑做什么呢』。",
        card,
    )
    assert any("共同回忆关键短语不在素材中" in v for v in bad)


def test_entity_gate_literary_imagery_not_blocked():
    card = IntentionCard(
        act="free_talk",
        topic="感受",
        materials=[Material(tag="none", text="")],
    )
    ok = assert_reply_respects_card("……像深水里的石子，又像一片叶子。", card)
    assert not any("虚构实体" in v for v in ok)


def test_entity_gate_blocks_fabricated_name():
    card = IntentionCard(
        act="free_talk",
        topic="故事",
        materials=[Material(tag="none", text="")],
    )
    bad = assert_reply_respects_card("那个叫阿强的医生说过这话。", card)
    assert any("虚构实体:阿强" in v for v in bad)


def test_soft_self_view_not_hard():
    from qi.core.intention import is_hard_violation

    card = IntentionCard(
        act="share_state",
        topic="自己",
        materials=[Material(tag="state", text="有点安静")],
        channel="proactive",
    )
    viols = assert_reply_respects_card("……我好像，越来越喜欢自己了。", card)
    assert any("无支撑自我认知结论" in v for v in viols)
    assert not any(is_hard_violation(v) for v in viols)


def test_materials_block_short_quote_honesty_boundary():
    card = IntentionCard(
        act="free_talk",
        topic="x",
        materials=[Material(tag="memory", text="躺着不强迫")],
    )
    block = card.materials_block()
    assert "【你此刻知道的事】" in block
    assert "【诚实边界】" in block
    assert "躺着不强迫" in block
    assert "以温暖的第一人称叙述" not in block
