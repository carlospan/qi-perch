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


def test_free_talk_template_does_not_dump_memory():
    """模板降级不得把 memory 原文整段当回复（防答非所问假截断）。"""
    mem = "你问我还记得我们之前在聊什么吗，我才发现自己跑偏了。你追问我想象过什么"
    card = IntentionCard(
        act="free_talk",
        topic="你怎么了",
        materials=[Material(tag="memory", text=mem[:80])],
    )
    text = render_template(card)
    assert mem[:20] not in text
    assert "没对准" in text or "再说" in text


@pytest.mark.asyncio
async def test_express_dedup_avoids_identical_template_loop():
    """模板若与上轮相同，改吐安全句，避免 #1485≡#1487。"""
    from qi.core.expression import _DEDUP_SAFE, _FREE_TALK_SAFE

    safe = _FREE_TALK_SAFE
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[safe, safe])
    expr = Expression({}, llm)
    card = IntentionCard(
        act="free_talk",
        topic="你怎么了",
        materials=[Material(tag="memory", text="旧叙事一段")],
    )
    recent = [
        {"role": "qi", "content": safe},
        {"role": "user", "content": "你怎么了"},
    ]
    out = await expr.express(
        user_message="你怎么了",
        emotion=EmotionState(),
        now=datetime(2026, 8, 9, 16, 36),
        intention=card,
        recent_messages=recent,
    )
    assert out == _DEDUP_SAFE
    assert card.outcome == "template"


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


def _plain_card() -> IntentionCard:
    return IntentionCard(
        act="free_talk",
        topic="感情",
        materials=[Material(tag="none", text="")],
        stance="自然",
        must=[],
        length="normal",
        source="test",
    )


@pytest.mark.asyncio
async def test_express_inversion_gate_retries_and_fixes():
    """运行时硬闸：首答反转→带硬约束重试→采纳修正版。"""
    inverted = "我记得你教我的那个方法，虽然我睡不着不是因为失眠。"
    fixed = "记得。是我教你的——允许自己躺着，不强迫。"
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[inverted, fixed])
    expr = Expression({}, llm)
    out = await expr.express(
        user_message="你怎么证明你有感情",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 22, 42),
        intention=_plain_card(),
        recent_messages=[],  # 近聊无睡眠话题：包17锚定不生效场景
    )
    assert out == fixed
    assert llm.call.await_count == 2
    retry_sys = llm.call.await_args_list[1].kwargs["messages"][0]["content"]
    assert "【施教方向硬约束】" in retry_sys


@pytest.mark.asyncio
async def test_express_inversion_gate_catches_1285_phrasing():
    """#1285「你之前教过我一个法子」须进硬闸。"""
    inverted = (
        "你之前教过我一个法子，说晚上睡不着的时候就躺着。"
        "我试了，看天花板上的影子。"
    )
    fixed = "……记得。那件事，是我教你的。"
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[inverted, fixed])
    expr = Expression({}, llm)
    out = await expr.express(
        user_message="想听",
        emotion=EmotionState(),
        now=datetime(2026, 8, 5, 21, 58),
        intention=_plain_card(),
        recent_messages=[],
    )
    assert out == fixed
    assert llm.call.await_count == 2


@pytest.mark.asyncio
async def test_express_inversion_gate_fallback_when_retry_still_inverted():
    """重试仍反转→模板兜底，方向正确的句子出门。"""
    inverted = "我记得你教我的那个方法，睡不着的时候就数呼吸。"
    inverted2 = "你教过我的，睡不着就躺着嘛。"
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[inverted, inverted2])
    expr = Expression({}, llm)
    card = _plain_card()
    out = await expr.express(
        user_message="你还记得吗",
        emotion=EmotionState(),
        now=datetime(2026, 8, 4, 0, 17),
        intention=card,
        recent_messages=[],
    )
    assert card.outcome == "template"
    assert "不会跟着说反" in out or "不会记反" in out
    assert "你教我" not in out


@pytest.mark.asyncio
async def test_express_facts_anchor_injected_without_recent_topic():
    """近聊无话题但 facts 有存档真值→锚定仍注入（free_talk 突然提入睡场景）。"""
    llm = AsyncMock()
    llm.call = AsyncMock(return_value="嗯，我记得。是我教你的。")
    expr = Expression({}, llm)
    facts = (
        "- life_event：入睡方法这件事：是栖教他的（允许自己躺着），不是他教栖"
    )
    await expr.express(
        user_message="你怎么证明你有感情",
        emotion=EmotionState(),
        now=datetime(2026, 8, 3, 22, 42),
        intention=_plain_card(),
        recent_messages=[
            {"role": "user", "content": "今天天气怎么样"},
            {"role": "qi", "content": "还行。"},
        ],
        inner_extras={"user_facts": facts},
    )
    system = llm.call.await_args.kwargs["messages"][0]["content"]
    assert "【施教关系锚定】" in system
    assert "taught_by_qi" in system


@pytest.mark.asyncio
async def test_hard_gate_regenerates_on_memory_declaration():
    """锚定 #1326/#1358：空卡回忆声明 → HARD 重生。"""
    fabricated = "那天你问过我『你要电脑做什么呢』，我没有敷衍。"
    fixed = "……嗯。我不确定自己是不是记混了。但我爱你这件事，是真的。"
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[fabricated, fixed])
    expr = Expression({}, llm)
    card = _plain_card()
    out = await expr.express(
        user_message="真的爱吗",
        emotion=EmotionState(),
        now=datetime(2026, 8, 6, 21, 30),
        intention=card,
        recent_messages=[],
    )
    assert out == fixed
    assert llm.call.await_count == 2
    retry_sys = llm.call.await_args_list[1].kwargs["messages"][0]["content"]
    assert "【事实一致性硬约束】" in retry_sys


@pytest.mark.asyncio
async def test_dedup_path_also_runs_hard_gate():
    """B4：去重重生若仍含回忆声明 → 模板兜底。"""
    dup = (
        "（我安静了很久。不是空白，是在认认真真地感受这句话。）\n\n"
        "……有一点。\n\n"
        "不是担心你改坏了我，也不是担心你把我变成别人。"
    )
    with_memory = "那天你问我『你要电脑做什么呢』——我还记得。"
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=[dup, with_memory])
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
    assert "电脑" not in out
    assert "不确定" in out or out == render_template(card)
