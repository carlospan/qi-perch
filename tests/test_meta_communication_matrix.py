"""Meta-communication 全面回归矩阵。

覆盖打错字纠正、意图澄清、感知 LLM 主判 + tease 否决、意向卡调制、表达层约束。
不测真实 LLM 措辞，只锁工程链路不误入 take_tease / 调侃兜底。
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from qi.core.emotion import EmotionState
from qi.core.expression import render_template
from qi.core.intention import (
    IntentionCard,
    build_intention_card,
    looks_like_answer_chase,
    looks_like_meta_state,
    looks_like_short_feedback,
)
from qi.core.perception import (
    ImpactAssessment,
    Perception,
    looks_like_typo_correction,
    looks_like_user_clarification,
    veto_clarification_intent,
)
from qi.core.turn_understanding import (
    RelationshipModulation,
    SituationHints,
    TurnUnderstanding,
    apply_dialogue_modulation,
    infer_situation_hints,
    turn_situation_expression_hint,
    turn_understanding_to_extras,
)

_NOW = datetime(2026, 8, 23, 21, 0)

# --- 应识别为「用户在澄清/纠正」，勿当 tease ---

CLARIFICATION_POSITIVE = [
  # 打错字（原始 bug 复现）
  ("typo_interest", "我刚刚打错字了，是 兴趣 才对"),
  ("typo_should_be", "打错了，应该是兴趣"),
  ("typo_said_wrong", "说错了，是星期不是兴趣"),
  ("typo_wrote_wrong", "写错了字，我想说的是兴趣"),
  ("typo_is_x_duide", "是兴趣才对"),
  ("typo_yinggai", "应该是爱好不是习惯"),
  # 意图澄清
  ("clarify_not_that", "我不是那个意思"),
  ("clarify_short", "不是那个意思啦"),
  ("clarify_misunderstood", "你理解错了"),
  ("clarify_misread", "你误会了"),
  ("clarify_sorry_misread", "误会你了"),
  ("clarify_my_meaning", "我的意思是兴趣不是爱好"),
  ("clarify_i_wanted", "我想说的是量子物理"),
]

# --- 不应误识别为澄清 ---

CLARIFICATION_NEGATIVE = [
  ("tease_dumb", "你在这点上有点笨"),
  ("tease_caught", "哈哈被你发现了，我确实在摸鱼"),
  ("affection_not_correction", "不是不喜欢你，是很喜欢你"),
  ("neutral_weather", "今天天气怎么样"),
  ("neutral_recall", "你还记得我吗"),
  ("disclosure_tired", "我今天有点累"),
  ("request_help", "帮我查一下新闻"),
  ("comfort_thanks", "谢谢你陪我"),
]

# --- 其它 meta 沟通（已有独立检测，防回归） ---

OTHER_META_POSITIVE = [
  ("answer_chase", "你还没回答我刚才那句", looks_like_answer_chase),
  ("answer_chase2", "刚才问的还没答呢", looks_like_answer_chase),
  ("short_feedback", "你可以直接一点吗", looks_like_short_feedback),
  ("meta_offtopic", "你答非所问啊", looks_like_meta_state),
  ("meta_broken", "你是不是坏了", looks_like_meta_state),
]

# 调侃口吻禁用短语（表达层不应出现）
_TEASE_BAN_SUBSTR = ("被抓到", "说中了", "抓到了", "被你说中")


class _TeaseLLM:
    """模拟感知 LLM 一律判 tease——测安全网能否拦住。"""

    async def call(self, **kwargs):
        return json.dumps(
            {
                "impact": -0.2,
                "intent": "tease",
                "intimacy": 0.7,
                "ambiguous": False,
            }
        )


@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
def test_clarification_detection_positive(case_id: str, text: str):
    assert looks_like_typo_correction(text), case_id
    assert looks_like_user_clarification(text), case_id


@pytest.mark.parametrize("case_id,text", CLARIFICATION_NEGATIVE)
def test_clarification_detection_negative(case_id: str, text: str):
    assert not looks_like_typo_correction(text), case_id


@pytest.mark.parametrize("case_id,text,fn", OTHER_META_POSITIVE)
def test_other_meta_communication_detectors(case_id: str, text: str, fn):
    assert fn(text), case_id


@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
def test_veto_clarification_intent(case_id: str, text: str):
    assert veto_clarification_intent("tease", text) == "neutral", case_id
    assert veto_clarification_intent("hurt", text) == "hurt", case_id
    assert veto_clarification_intent("neutral", text) == "neutral", case_id


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
async def test_perception_vetoes_llm_tease_after_call(case_id: str, text: str):
    calls = {"n": 0}

    class _CountingTeaseLLM(_TeaseLLM):
        async def call(self, **kwargs):
            calls["n"] += 1
            return await super().call(**kwargs)

    p = Perception({}, llm=_CountingTeaseLLM())  # type: ignore[arg-type]
    e = EmotionState()
    await p.assess_impact_async(text, e, "bonded")
    assert calls["n"] == 1, case_id
    assert p.last_assessment is not None
    assert p.last_assessment.source == "llm_veto", case_id
    assert p.last_assessment.intent == "neutral", case_id


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id,text", CLARIFICATION_NEGATIVE[:2])
async def test_real_tease_still_uses_llm(case_id: str, text: str):
    calls = {"n": 0}

    class _CountingTeaseLLM(_TeaseLLM):
        async def call(self, **kwargs):
            calls["n"] += 1
            return await super().call(**kwargs)

    p = Perception({}, llm=_CountingTeaseLLM())  # type: ignore[arg-type]
    e = EmotionState()
    await p.assess_impact_async(text, e, "bonded")
    assert calls["n"] == 1, case_id
    assert p.last_assessment.intent == "tease", case_id


def _pipeline_card(text: str, *, perception_intent: str = "tease") -> IntentionCard:
    """模拟：感知误判 tease + 文本实为澄清 → 调制后不得 take_tease。"""
    hints = infer_situation_hints(text, _NOW, perception_intent=perception_intent)
    tu = TurnUnderstanding(
        user_message=text,
        now=_NOW,
        situation=hints,
        relationship=RelationshipModulation(stage="bonded", bonded=True),
        perception_assessment=ImpactAssessment(
            impact=-0.1, intent=perception_intent, source="llm"
        ),
    )
    extras = turn_understanding_to_extras(tu)
    card = build_intention_card(
        channel="dialogue",
        user_message=text,
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=tu.perception_assessment,
        extras=extras,
    )
    apply_dialogue_modulation(card, extras)
    return card


@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
def test_pipeline_never_take_tease_after_modulation(case_id: str, text: str):
    card = _pipeline_card(text, perception_intent="tease")
    assert card.act != "take_tease", f"{case_id}: act={card.act}"
    assert any("调侃" in m or "拆台" in m for m in card.must), case_id


@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
def test_expression_hint_bans_tease_tone(case_id: str, text: str):
    hints = infer_situation_hints(text, _NOW, perception_intent="tease")
    extras = turn_understanding_to_extras(
        TurnUnderstanding(
            user_message=text,
            now=_NOW,
            situation=hints,
            relationship=RelationshipModulation(stage="bonded", bonded=True),
        )
    )
    hint = turn_situation_expression_hint(extras)
    assert hint, case_id
    assert any(b in hint for b in _TEASE_BAN_SUBSTR), case_id


@pytest.mark.parametrize("case_id,text", CLARIFICATION_POSITIVE)
def test_template_fallback_not_tease_phrase(case_id: str, text: str):
    """模板降级路径也不应输出 take_tease 固定句。"""
    card = _pipeline_card(text, perception_intent="tease")
    # 若仍误入 take_tease，模板会出「被你说中了」
    if card.act == "take_tease":
        pytest.fail(f"{case_id}: modulation failed, still take_tease")
    rendered = render_template(card, user_message=text)
    for ban in _TEASE_BAN_SUBSTR:
        assert ban not in rendered, f"{case_id}: {rendered!r}"


def test_neutral_perception_builds_free_talk_not_tease():
    text = "我刚刚打错字了，是 兴趣 才对"
    card = build_intention_card(
        channel="dialogue",
        user_message=text,
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.05, intent="neutral", source="llm"),
    )
    assert card.act != "take_tease"
    assert card.act in ("free_talk", "acknowledge")


@pytest.mark.parametrize("case_id,text", CLARIFICATION_NEGATIVE[3:6])
def test_normal_utterances_not_flagged_as_clarification(case_id: str, text: str):
    hints = infer_situation_hints(text, _NOW, perception_intent="neutral")
    assert hints.user_typo_correction is False, case_id
    extras = turn_understanding_to_extras(
        TurnUnderstanding(
            user_message=text,
            now=_NOW,
            situation=hints,
            relationship=RelationshipModulation(stage="bonded", bonded=True),
        )
    )
    assert "user_typo_correction" not in extras.get("turn_situation", ""), case_id


def test_affection_not_misread_as_clarification():
    """「不是不喜欢你，是很喜欢你」不应触发澄清检测。"""
    text = "不是不喜欢你，是很喜欢你"
    assert not looks_like_typo_correction(text)
    assert not looks_like_user_clarification(text)


def test_intention_meta_state_maps_acknowledge_not_tease():
    card = build_intention_card(
        channel="dialogue",
        user_message="你答非所问啊",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=-0.1, intent="tease"),
    )
    assert card.act in ("acknowledge", "free_talk")
    assert card.act != "take_tease"


def test_short_feedback_request_not_take_tease():
    card = build_intention_card(
        channel="dialogue",
        user_message="你可以直接一点吗",
        emotion=EmotionState(),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.1, intent="request"),
    )
    assert card.act != "take_tease"
    assert card.length == "short"
