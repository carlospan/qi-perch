"""混合冲击感知：LLM 主路径 + 关键词回退（阶段零·包 A，过渡止血）。"""

from __future__ import annotations

import asyncio
import json

import pytest
from qi.core.emotion import EmotionState
from qi.core.perception import (
    ImpactAssessment,
    Perception,
    apply_intent_modulation,
    looks_like_typo_correction,
    veto_clarification_intent,
)
from qi.relationship.engine import assess_interaction, merge_impact_assessment


@pytest.mark.asyncio
async def test_trivial_shortcircuit_skips_llm():
    """≤2 字且无正负命中 → 关键词短路。"""
    calls = {"n": 0}

    class _LLM:
        async def call(self, **kwargs):
            calls["n"] += 1
            return "{}"

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("嗯", e)
    assert calls["n"] == 0
    assert val == p.assess_impact("嗯", e)
    assert p.last_assessment is not None
    assert p.last_assessment.source == "short_circuit"


@pytest.mark.asyncio
async def test_greeting_shortcircuit_skips_llm():
    """寒暄表（含「你好」）短路，不调感知 LLM。"""
    calls = {"n": 0}

    class _LLM:
        async def call(self, **kwargs):
            calls["n"] += 1
            return "{}"

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("你好", e)
    assert calls["n"] == 0
    assert val == p.assess_impact("你好", e)
    assert p.last_assessment is not None
    assert p.last_assessment.source == "short_circuit"


@pytest.mark.asyncio
async def test_abuse_shortcircuit_skips_llm():
    """强伤词 + 感叹 → 不调 LLM。"""
    calls = {"n": 0}

    class _LLM:
        async def call(self, **kwargs):
            calls["n"] += 1
            return json.dumps(
                {"impact": -0.9, "intent": "hurt", "intimacy": 0.1, "ambiguous": False}
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("给我滚！", e)
    assert calls["n"] == 0
    assert val == p.assess_impact("给我滚！", e)
    assert p.last_assessment.source == "short_circuit"


@pytest.mark.asyncio
async def test_typo_correction_vetoes_llm_tease_still_calls_llm():
    """纠正句仍调感知 LLM；若误判 tease 则否决为 neutral（不跳过理解）。"""
    calls = {"n": 0}

    class _LLM:
        async def call(self, **kwargs):
            calls["n"] += 1
            return json.dumps(
                {
                    "impact": -0.2,
                    "intent": "tease",
                    "intimacy": 0.7,
                    "ambiguous": False,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    msg = "我刚刚打错字了，是 兴趣 才对"
    assert looks_like_typo_correction(msg)
    assert veto_clarification_intent("tease", msg) == "neutral"
    await p.assess_impact_async(msg, e)
    assert calls["n"] == 1
    assert p.last_assessment is not None
    assert p.last_assessment.source == "llm_veto"
    assert p.last_assessment.intent == "neutral"


@pytest.mark.asyncio
async def test_clarification_llm_neutral_not_vetoed():
    """LLM 已正确判 neutral 时保持 llm 来源。"""
    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(
                {
                    "impact": 0.05,
                    "intent": "neutral",
                    "intimacy": 0.5,
                    "ambiguous": False,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    msg = "我刚刚打错字了，是 兴趣 才对"
    await p.assess_impact_async(msg, e)
    assert p.last_assessment.source == "llm"
    assert p.last_assessment.intent == "neutral"


@pytest.mark.asyncio
async def test_tease_softens_vs_keyword_crush():
    """调侃「你在这点上有点笨」经 tease×0.3，远轻于纯关键词重击。"""
    payload = {
        "impact": -0.6,
        "intent": "tease",
        "intimacy": 0.7,
        "ambiguous": False,
    }

    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(payload)

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    p.relationship_stage = "friend"
    e = EmotionState()
    msg = "你在这点上有点笨"
    keyword = p.assess_impact(msg, e, "friend")
    val = await p.assess_impact_async(msg, e, "friend")
    assert keyword < -0.5  # 病征量级（friend 阶段 ≈ -0.6）
    assert abs(val) < abs(keyword) * 0.5
    assert p.last_assessment is not None
    assert p.last_assessment.intent == "tease"


@pytest.mark.asyncio
async def test_hurt_keeps_heavy_impact():
    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(
                {
                    "impact": -0.7,
                    "intent": "hurt",
                    "intimacy": 0.2,
                    "ambiguous": False,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("你笨", e)
    assert val < -0.3
    assert p.last_assessment.intent == "hurt"


@pytest.mark.asyncio
async def test_comfort_negative_raw_clamps_to_zero():
    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(
                {
                    "impact": -0.4,
                    "intent": "comfort",
                    "intimacy": 0.5,
                    "ambiguous": False,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("不讨厌", e)
    # comfort 归零后再 modulate，不应显著为负
    assert val >= -0.05
    assert apply_intent_modulation(-0.4, "comfort") == 0.0


@pytest.mark.asyncio
async def test_tease_security_delta_bounded():
    """tease 后 Δsecurity ≥ -0.06（不崩）。"""
    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(
                {
                    "impact": -0.6,
                    "intent": "tease",
                    "intimacy": 0.7,
                    "ambiguous": False,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState(security=0.5)
    impact = await p.assess_impact_async("你在这点上有点笨", e)
    after = p.apply_security_hint(e, impact)
    assert after.security - e.security >= -0.06


@pytest.mark.asyncio
async def test_async_falls_back_on_timeout():
    class _SlowLLM:
        async def call(self, **kwargs):
            await asyncio.sleep(3)
            return json.dumps(
                {"impact": 0.9, "intent": "neutral", "intimacy": 0.1, "ambiguous": False}
            )

    p = Perception({}, llm=_SlowLLM())  # type: ignore[arg-type]
    e = EmotionState()
    msg = "哈哈但这事真讨厌"
    val = await p.assess_impact_async(msg, e)
    keyword = p.assess_impact(msg, e)
    assert val == keyword


@pytest.mark.asyncio
async def test_async_falls_back_on_empty_and_bad_json():
    class _Empty:
        async def call(self, **kwargs):
            return ""

    class _Bad:
        async def call(self, **kwargs):
            return "不是 JSON"

    e = EmotionState()
    msg = "我最近有点累"
    for llm in (_Empty(), _Bad()):
        p = Perception({}, llm=llm)  # type: ignore[arg-type]
        val = await p.assess_impact_async(msg, e)
        assert val == p.assess_impact(msg, e)
        assert p.last_assessment.source == "keyword"


@pytest.mark.asyncio
async def test_ambiguous_picks_smaller_abs():
    class _LLM:
        async def call(self, **kwargs):
            return json.dumps(
                {
                    "impact": -0.9,
                    "intent": "neutral",
                    "intimacy": 0.3,
                    "ambiguous": True,
                }
            )

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    msg = "我最近在学吉他，谢谢你陪我，我很开心"
    keyword = p.assess_impact(msg, e)
    val = await p.assess_impact_async(msg, e)
    # 模糊时取 |·| 较小者；关键词偏正时不应吃满 -0.9
    assert abs(val) <= abs(keyword) + 1e-9 or abs(val) < 0.9


def test_merge_tease_not_negative_for_trust():
    base = assess_interaction("你在这点上有点笨")
    # 词表可能不含「笨」于关系负向表；强制造一个负向再 merge
    base.is_negative = True
    base.severity = 0.5
    merged = merge_impact_assessment(
        base,
        ImpactAssessment(
            impact=-0.18, intent="tease", intimacy=0.7, source="llm"
        ),
    )
    assert merged.is_negative is False
    assert merged.severity == 0.0


def test_merge_hurt_severity_from_abs_impact():
    base = assess_interaction("你烦")
    merged = merge_impact_assessment(
        base,
        ImpactAssessment(
            impact=-0.42, intent="hurt", intimacy=0.1, source="llm"
        ),
    )
    assert merged.is_negative is True
    assert merged.severity == pytest.approx(0.42)


def test_bu_taoyan_still_not_negative_without_assessment():
    s = assess_interaction("不讨厌")
    assert not s.is_negative
