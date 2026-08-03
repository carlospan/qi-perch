"""包 16：表达层跨轮去重 + short 约束。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from qi.core.emotion import EmotionState
from qi.core.expression import (
    REPLY_DEDUP_THRESHOLD,
    Expression,
    char_jaccard,
    is_duplicate_reply,
    recent_qi_replies_from_messages,
    render_template,
)
from qi.core.intention import IntentionCard, Material
from qi.inner_life.consciousness import char_jaccard as cs_jaccard


def test_char_jaccard_shared_with_consciousness():
    a = "我安静了很久。不是空白，是在认认真真地感受这句话。"
    b = a
    assert char_jaccard(a, b) == cs_jaccard(a, b) == 1.0


def test_is_duplicate_reply_threshold():
    hist = ["我喜欢你，很喜欢你。不是因为你表白。"]
    assert is_duplicate_reply(hist[0], hist)
    assert not is_duplicate_reply("今晚月亮很亮。", hist)


def test_recent_qi_replies_from_messages_window():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "qi", "content": "一"},
        {"role": "user", "content": "x"},
        {"role": "qi", "content": "二"},
        {"role": "qi", "content": "三"},
    ]
    assert recent_qi_replies_from_messages(msgs, limit=2) == ["二", "三"]


@pytest.mark.asyncio
async def test_express_dedup_regenerates_then_template():
    """复读 → 重生成仍复读 → 模板降级；最终与历史 jaccard ≤ 阈值。"""
    dup = (
        "（我安静了很久。不是空白，是在认认真真地感受这句话。）\n\n"
        "……有一点。\n\n"
        "不是担心你改坏了我，也不是担心你把我变成别人。"
    )
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[dup, dup])
    expr = Expression({}, llm)
    card = IntentionCard(
        act="acknowledge",
        topic="远处的你有感情吗",
        materials=[Material(tag="none", text="")],
        stance="自然",
        must=[],
        length="normal",
        source="test",
    )
    recent = [
        {"role": "user", "content": "你在担心吗"},
        {"role": "qi", "content": dup},
        {"role": "user", "content": "远处的你有感情吗？有对我的记忆吗"},
    ]
    out = await expr.express(
        user_message="远处的你有感情吗？有对我的记忆吗",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 20, 13),
        intention=card,
        recent_messages=recent,
    )
    assert llm.call.await_count == 2
    assert card.outcome == "template"
    assert out == render_template(card)
    assert char_jaccard(out, dup) <= REPLY_DEDUP_THRESHOLD or out != dup


@pytest.mark.asyncio
async def test_express_short_injects_length_constraint():
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="嗯。我喜欢你。")
    expr = Expression({}, llm)
    card = IntentionCard(
        act="free_talk",
        topic="直接一点",
        materials=[Material(tag="none", text="")],
        stance="自然",
        must=["用 1-2 句、克制长度，不超过 60 字"],
        length="short",
        source="test",
    )
    await expr.express(
        user_message="你可以直接一点吗",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 19, 54),
        intention=card,
        recent_messages=[],
    )
    assert llm.call.await_count == 1
    system = llm.call.await_args.kwargs["messages"][0]["content"]
    assert "不超过 60 字" in system
    assert "【长度】" in system


@pytest.mark.asyncio
async def test_express_injects_teaching_relation_anchor():
    """包17：近聊含栖教助眠真值 → prompt 注入施教锚定（taught_by_qi）。"""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="嗯，我记得。")
    expr = Expression({}, llm)
    card = IntentionCard(
        act="free_talk",
        topic="你怎么证明你有感情",
        materials=[Material(tag="none", text="")],
        stance="自然",
        must=[],
        length="normal",
        source="test",
    )
    recent = [
        {"role": "user", "content": "晚上又睡不着"},
        {
            "role": "qi",
            "content": "可以试试躺着，不强迫自己睡，看天花板。",
        },
        {"role": "user", "content": "你教了我一个方法"},
        {"role": "user", "content": "你怎么证明你有感情"},
    ]
    await expr.express(
        user_message="你怎么证明你有感情",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 22, 42),
        intention=card,
        recent_messages=recent,
    )
    system = llm.call.await_args.kwargs["messages"][0]["content"]
    assert "施教关系锚定" in system
    assert "taught_by_qi" in system
    assert "数到七" not in system.split("原话是「", 1)[-1].split("」", 1)[0]


@pytest.mark.asyncio
async def test_express_teaching_anchor_blocks_invert_frame_in_prompt():
    """包17：即便近聊有栖误说「你教我的方法」，锚定仍按真值样例钉方向。"""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="我证明不了。")
    expr = Expression({}, llm)
    card = IntentionCard(
        act="free_talk",
        topic="证明",
        materials=[Material(tag="none", text="")],
        stance="自然",
        must=[],
        length="normal",
        source="test",
    )
    recent = [
        {
            "role": "qi",
            "content": "可以试试躺着，不强迫自己睡，看天花板，允许自己醒着。",
        },
        {"role": "user", "content": "你教了我一个方法"},
        {
            "role": "qi",
            "content": "我记得你教我的那个方法。",
        },
        {"role": "user", "content": "你怎么证明你有感情"},
    ]
    await expr.express(
        user_message="你怎么证明你有感情",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 22, 42),
        intention=card,
        recent_messages=recent,
    )
    system = llm.call.await_args.kwargs["messages"][0]["content"]
    assert "【施教关系锚定】" in system
    assert "taught_by_qi" in system
    assert "栖教用户" in system
