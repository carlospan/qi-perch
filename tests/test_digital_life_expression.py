"""数字生命表达：实质问、过程诚实、情绪余波。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.core.emotion import EmotionState
from qi.core.expression import (
    Expression,
    _SUBSTANTIVE_EMPTY_SAFE,
    render_template,
)
from qi.core.intention import (
    IntentionCard,
    Material,
    assert_reply_respects_card,
    build_intention_card,
    is_hard_violation,
)
from qi.core.perception import ImpactAssessment
from qi.core.turn_understanding import (
    TurnUnderstanding,
    RelationshipModulation,
    SituationHints,
    apply_dialogue_modulation,
    apply_turn_emotion_modulation,
    looks_like_substantive_question,
    turn_understanding_to_extras,
)


def test_substantive_question_detection():
    assert looks_like_substantive_question("你觉得你对我有类似人类那种情感吗")
    assert looks_like_substantive_question("你喜欢人类吗")
    assert not looks_like_substantive_question("嗯")


def test_substantive_empty_template_not_please_repeat():
    card = IntentionCard(
        act="acknowledge",
        topic="情感",
        materials=[Material(tag="state", text="有点安静，有点想你")],
        must=[],
    )
    text = render_template(
        card, user_message="你觉得你对我有类似人类那种情感吗"
    )
    assert "没接好" not in text
    assert "再说一次" not in text
    assert "听见了" in text or "安静" in text

    empty = IntentionCard(
        act="acknowledge", topic="情感", materials=[Material(tag="none", text="")], must=[]
    )
    text2 = render_template(empty, user_message="你觉得你对我有类似人类那种情感吗")
    assert "没接好" not in text2
    assert _SUBSTANTIVE_EMPTY_SAFE[:6] in text2


def test_process_fabrication_hard_violation():
    card = IntentionCard(
        act="free_talk",
        topic="x",
        materials=[Material(tag="none", text="")],
        must=[],
    )
    viols = assert_reply_respects_card("这个问题我想了很久，选了又选。", card)
    assert any(is_hard_violation(v) for v in viols)


def test_substantive_modulation_injects_state():
    card = IntentionCard(act="free_talk", topic="情感吗", stance="自然", must=[])
    extras = {
        "turn_situation": "user_substantive_question,bonded",
        "present_emotion": "有点安静，有点想你",
    }
    apply_dialogue_modulation(card, extras)
    assert card.act == "acknowledge"
    assert any(m.tag == "state" for m in card.materials)
    assert any("实质问" in m for m in card.must)


def test_emotional_aftershock_tags_and_length():
    tu = TurnUnderstanding(
        user_message="测试",
        now=datetime(2026, 8, 23, 22, 0),
        situation=SituationHints(),
        relationship=RelationshipModulation(stage="bonded", bonded=True),
        perception_assessment=ImpactAssessment(impact=-0.15, intent="neutral"),
    )
    apply_turn_emotion_modulation(tu, valence_before=0.5, valence_after=0.3)
    assert tu.situation.emotional_aftershock is True
    extras = turn_understanding_to_extras(tu)
    assert "emotional_aftershock" in extras.get("turn_situation", "")

    card = IntentionCard(act="free_talk", topic="x", stance="自然", must=[], length="normal")
    apply_dialogue_modulation(card, extras)
    assert card.length == "short"


@pytest.mark.asyncio
async def test_express_substantive_empty_retries_not_system_fallback():
    llm = AsyncMock()
    llm.call = AsyncMock(side_effect=["", "有，但我不确定是不是同一种。"])
    expr = Expression({}, llm)
    card = build_intention_card(
        channel="dialogue",
        user_message="你觉得你对我有类似人类那种情感吗",
        emotion=EmotionState(valence=0.2),
        relationship_stage="bonded",
        assessment=ImpactAssessment(impact=0.0, intent="neutral"),
    )
    card.materials = [Material(tag="state", text="有点安静，有点想你")]
    out = await expr.express(
        user_message="你觉得你对我有类似人类那种情感吗",
        emotion=EmotionState(),
        now=datetime(2026, 8, 23, 22, 0),
        intention=card,
        relationship_stage="bonded",
        inner_extras={
            "turn_situation": "user_substantive_question,bonded",
            "present_emotion": "有点安静，有点想你",
        },
    )
    assert "没接好" not in out
    assert "不确定" in out or "有" in out
    assert llm.call.await_count == 2


@pytest.mark.asyncio
async def test_note_emotional_residue_enqueues_loop():
    from unittest.mock import AsyncMock, MagicMock, patch

    from qi.core.turn_understanding import note_emotional_residue

    brain = MagicMock()
    brain._db = MagicMock()
    brain.emotion = EmotionState(valence=0.2)
    q = MagicMock()
    q.load = AsyncMock()
    q.enqueue = AsyncMock()
    tu = TurnUnderstanding(
        user_message="假设",
        now=datetime(2026, 8, 23, 22, 0),
        situation=SituationHints(),
        relationship=RelationshipModulation(stage="bonded", bonded=True),
        perception_assessment=ImpactAssessment(impact=-0.2, intent="neutral"),
    )

    with patch("qi.memory.open_loops.OpenLoopQueue", return_value=q):
        await note_emotional_residue(
            brain, tu, valence_before=0.5, valence_after=0.25
        )

    assert tu.situation.emotional_aftershock is True
    q.enqueue.assert_awaited_once()
