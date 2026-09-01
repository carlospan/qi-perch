"""look 所见走心：冲击 + 主观短说。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from qi.action.look import FIRST_NOTICE_LINE, LookAction, min_interval_minutes
from qi.core.emotion import EmotionState
from qi.core.look_heart import enrich_look_glance
from qi.storage.database import Database


def test_min_interval_default_is_30():
    assert min_interval_minutes({}) == 30.0
    assert min_interval_minutes({"action": {"look": {}}}) == 30.0
    assert min_interval_minutes({"action": {"look": {"min_interval_minutes": 15}}}) == 15.0


@pytest.mark.asyncio
async def test_enrich_look_applies_impact_and_rewrites_line():
    brain = MagicMock()
    brain.relationship_stage = "friend"
    brain.emotion = EmotionState()
    valence_before = float(brain.emotion.valence)
    brain.perception = MagicMock()
    brain.perception.assess_impact_async = AsyncMock(return_value=0.5)
    brain.perception.apply_security_hint = MagicMock(
        side_effect=lambda e, _i: e
    )
    brain._maybe_save_emotion = AsyncMock()
    brain.expression = MagicMock()
    brain.expression.express = AsyncMock(return_value="好像有点晃……你在看文档？")
    brain.llm = MagicMock()
    brain.memory = None

    result = {
        "type": "look_glance",
        "outcome": "success",
        "reactive": True,
        "user_question": "你能看到我现在在做什么吗？",
        "season": "spring",
        "first_notice": False,
        "qi_line": "屏幕上是一块白底文档。",
        "summary": "屏幕上是一块白底文档。",
        "found": {"impression": "屏幕上是一块白底文档。"},
        "speak": True,
    }
    now = datetime.now()
    await enrich_look_glance(brain, result, now)

    assert result.get("_look_heart_done") is True
    assert result.get("_look_impact") == pytest.approx(0.5)
    assert float(brain.emotion.valence) != valence_before or float(
        brain.emotion.arousal
    ) > 0
    assert result["qi_line"] == "好像有点晃……你在看文档？"
    brain.expression.express.assert_awaited()
    # 幂等
    await enrich_look_glance(brain, result, now)
    assert brain.expression.express.await_count == 1


@pytest.mark.asyncio
async def test_enrich_look_autonomous_scales_impact():
    brain = MagicMock()
    brain.relationship_stage = "friend"
    brain.emotion = EmotionState()
    brain.perception = MagicMock()
    brain.perception.assess_impact_async = AsyncMock(return_value=1.0)
    brain.perception.apply_security_hint = MagicMock(
        side_effect=lambda e, _i: e
    )
    brain._maybe_save_emotion = AsyncMock()
    brain.expression = MagicMock()
    brain.expression.express = AsyncMock(return_value="嗯……亮了一下。")
    brain.llm = MagicMock()
    brain.memory = None

    result = {
        "type": "look_glance",
        "outcome": "success",
        "reactive": False,
        "season": "spring",
        "first_notice": False,
        "qi_line": "一片亮。",
        "summary": "一片亮。",
        "found": {"impression": "一片亮。"},
        "speak": True,
    }
    await enrich_look_glance(brain, result, datetime.now())
    assert result.get("_look_impact") == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_enrich_preserves_first_notice_prefix():
    brain = MagicMock()
    brain.relationship_stage = "friend"
    brain.emotion = EmotionState()
    brain.perception = MagicMock()
    brain.perception.assess_impact_async = AsyncMock(return_value=0.1)
    brain.perception.apply_security_hint = MagicMock(
        side_effect=lambda e, _i: e
    )
    brain._maybe_save_emotion = AsyncMock()
    brain.expression = MagicMock()
    brain.expression.express = AsyncMock(return_value="有点安静的编辑器。")
    brain.llm = MagicMock()
    brain.memory = None

    result = {
        "type": "look_glance",
        "outcome": "success",
        "reactive": True,
        "season": "spring",
        "first_notice": True,
        "qi_line": FIRST_NOTICE_LINE + "代码窗口。",
        "summary": "代码窗口。",
        "found": {"impression": "代码窗口。"},
        "speak": True,
    }
    await enrich_look_glance(brain, result, datetime.now())
    assert result["qi_line"].startswith(FIRST_NOTICE_LINE)


@pytest.mark.asyncio
async def test_glance_stores_impression_as_material(tmp_path):
    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()

    class _LLM:
        async def call(self, purpose, messages, temperature=None):
            assert purpose == "look"
            return "白底上密密的字。"

    look = LookAction(
        db,
        config={"action": {"look": {"min_interval_minutes": 30}}},
        llm=_LLM(),  # type: ignore[arg-type]
        capture_fn=lambda: (b"\xff\xd8\xff", "Code", False),
    )
    result = await look.glance(
        relationship_stage="friend",
        season="spring",
        now=datetime.now(),
        reactive=True,
        user_question="看看我屏幕",
        mode="awake",
    )
    assert result is not None
    assert result["found"]["impression"] == "白底上密密的字。"
    assert result.get("speak") is True


@pytest.mark.asyncio
async def test_enrich_look_passes_filtered_memories():
    brain = MagicMock()
    brain.relationship_stage = "friend"
    brain.emotion = EmotionState()
    brain.perception = MagicMock()
    brain.perception.assess_impact_async = AsyncMock(return_value=0.2)
    brain.perception.apply_security_hint = MagicMock(side_effect=lambda e, _i: e)
    brain._maybe_save_emotion = AsyncMock()
    brain.expression = MagicMock()
    brain.expression.express = AsyncMock(return_value="白底文档……上次也这样。")
    brain.llm = MagicMock()
    brain.memory = MagicMock()
    brain.memory.retrieve_for_prompt = AsyncMock(
        return_value=[{"content": "上次也在看白底文档"}]
    )

    result = {
        "type": "look_glance",
        "outcome": "success",
        "reactive": True,
        "user_question": "你能看到屏幕吗",
        "season": "spring",
        "first_notice": False,
        "qi_line": "白底文档。",
        "summary": "白底文档。",
        "found": {"impression": "白底文档。"},
        "speak": True,
    }
    await enrich_look_glance(brain, result, datetime.now())

    kwargs = brain.expression.express.await_args.kwargs
    assert kwargs["memories"] == [{"content": "上次也在看白底文档"}]
    brain.memory.retrieve_for_prompt.assert_awaited_once()
    call_query = brain.memory.retrieve_for_prompt.await_args.args[0]
    assert "白底文档" in call_query
    assert "屏幕" in call_query


@pytest.mark.asyncio
async def test_enrich_look_memory_retrieval_failure_uses_empty():
    brain = MagicMock()
    brain.relationship_stage = "friend"
    brain.emotion = EmotionState()
    brain.perception = MagicMock()
    brain.perception.assess_impact_async = AsyncMock(return_value=0.1)
    brain.perception.apply_security_hint = MagicMock(side_effect=lambda e, _i: e)
    brain._maybe_save_emotion = AsyncMock()
    brain.expression = MagicMock()
    brain.expression.express = AsyncMock(return_value="嗯。")
    brain.llm = MagicMock()
    brain.memory = MagicMock()
    brain.memory.retrieve_for_prompt = AsyncMock(side_effect=RuntimeError("chroma down"))

    result = {
        "type": "look_glance",
        "outcome": "success",
        "reactive": False,
        "season": "spring",
        "first_notice": False,
        "qi_line": "一片亮。",
        "summary": "一片亮。",
        "found": {"impression": "一片亮。"},
        "speak": True,
    }
    await enrich_look_glance(brain, result, datetime.now())
    kwargs = brain.expression.express.await_args.kwargs
    assert kwargs["memories"] == []
