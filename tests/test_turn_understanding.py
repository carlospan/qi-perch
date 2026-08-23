"""回合理解 Phase 1 单测。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from qi.core.intention import IntentionCard
from qi.core.turn_understanding import (
    apply_dialogue_modulation,
    infer_relationship_modulation,
    infer_situation_hints,
    prepare_dialogue_turn,
    turn_situation_expression_hint,
    turn_understanding_to_extras,
)


def test_infer_situation_disclosure_late_night():
    now = datetime(2026, 8, 23, 4, 30)
    hints = infer_situation_hints("我还没睡", now, perception_intent="disclosure")
    assert hints.late_night is True
    assert hints.user_disclosure is True
    assert hints.user_request is False


def test_infer_relationship_bonded():
    rel = infer_relationship_modulation("bonded")
    assert rel.bonded is True
    assert rel.stage == "bonded"


def test_turn_understanding_to_extras_comma_separated():
    from qi.core.turn_understanding import RelationshipModulation, SituationHints, TurnUnderstanding

    tu = TurnUnderstanding(
        user_message="我还没睡",
        now=datetime(2026, 8, 23, 4, 0),
        situation=SituationHints(late_night=True, user_disclosure=True),
        relationship=RelationshipModulation(stage="bonded", bonded=True),
        perception_assessment=SimpleNamespace(intent="disclosure"),
    )
    extras = turn_understanding_to_extras(tu)
    assert extras["turn_situation"] == "late_night,user_disclosure,bonded"
    assert extras["perception_intent"] == "disclosure"


def test_apply_dialogue_modulation_bonded_late_disclosure():
    card = IntentionCard(act="acknowledge", topic="我还没睡", stance="自然", must=[])
    extras = {"turn_situation": "late_night,user_disclosure,bonded"}
    apply_dialogue_modulation(card, extras)
    assert card.stance == "亲近、关切"
    assert any("深夜" in m for m in card.must)


@pytest.mark.asyncio
async def test_prepare_dialogue_turn_reads_perception():
    brain = MagicMock()
    brain.relationship_stage = "bonded"
    brain.perception = SimpleNamespace(
        last_assessment=SimpleNamespace(intent="disclosure")
    )
    now = datetime(2026, 8, 23, 3, 0)
    tu = await prepare_dialogue_turn(brain, "我还没睡", now)
    assert tu.situation.user_disclosure is True
    assert tu.situation.late_night is True
    assert tu.relationship.bonded is True


def test_turn_situation_expression_hint():
    extras = {"turn_situation": "late_night,user_disclosure,bonded"}
    hint = turn_situation_expression_hint(extras)
    assert "深夜" in hint
    assert "恋人" in hint


def test_dialogue_router_fallthrough_sentinel():
    from qi.core.dialogue_router import FALLTHROUGH

    assert FALLTHROUGH is not None
