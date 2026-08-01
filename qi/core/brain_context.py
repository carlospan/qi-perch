"""对话 prompt 上下文组装——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.brain_types import PromptContext
from qi.memory.facts import format_facts_for_prompt
from qi.relationship.culture import format_culture_for_prompt
from qi.relationship.scars import format_scars_for_prompt

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")


async def gather_prompt_context(
    brain: Brain,
    pending: str | None,
    now: datetime,
) -> PromptContext:
    recent: list[dict] = []
    memories: list[dict] = []
    extras: dict[str, str] = {}

    if brain.memory is not None:
        recent = brain.memory.working.get_context()
        if (
            pending
            and recent
            and recent[-1].get("role") == "user"
            and recent[-1].get("content") == pending
        ):
            recent = recent[:-1]
        query = pending or "此刻的心情"
        memories = await brain.memory.retrieve_for_prompt(query, top_k=3)
        try:
            facts = await brain.memory.active_facts()
            extras["user_facts"] = format_facts_for_prompt(
                facts, brain.relationship_stage
            )
        except Exception:
            logger.exception("组装用户事实 prompt 出错")
            extras["user_facts"] = "（你还不太了解他）"
        try:
            body_hint = await brain.memory.body_rhythm_hint(brain.relationship_stage)
            if body_hint:
                extras["body_hint"] = body_hint
        except Exception:
            logger.exception("组装身体节奏 hint 出错")
    elif brain._db is not None:
        recent = await brain._db.load_recent_messages(limit=20)
        if (
            pending
            and recent
            and recent[-1].get("role") == "user"
            and recent[-1].get("content") == pending
        ):
            recent = recent[:-1]

    if brain.inner_life is not None:
        try:
            life_extras = await brain.inner_life.prompt_extras(
                brain.emotion, brain.relationship_stage
            )
            extras.update(life_extras)
        except Exception:
            logger.exception("内在生命 prompt 组装出错")

    if brain.action is not None:
        try:
            extras.update(await brain.action.prompt_extras())
        except Exception:
            logger.exception("行动层 prompt 组装出错")

    if pending and brain.first_times is not None:
        hint = await brain.first_times.maybe_recall_hint(pending, now)
        if hint:
            extras["first_time_hint"] = hint

    if brain._drift_signals:
        extras["drift_hint"] = "；".join(brain._drift_signals)
        brain._drift_signals = []

    shared_culture = "（还没有只属于你们的默契）"
    relationship_hint = ""
    scar_hint = ""
    season_hint = ""
    if brain.relationship is not None:
        shared_culture = format_culture_for_prompt(
            brain.relationship.state.shared_culture
        )
        relationship_hint = brain.relationship.stage_prompt_hint()
        season_hint = brain.relationship.state.season
    if brain.scars is not None and brain._db is not None:
        scars = await brain._db.list_scars()
        scar_hint = format_scars_for_prompt(scars)

    return PromptContext(
        recent_messages=recent,
        retrieved_memories=memories,
        extras=extras,
        shared_culture=shared_culture,
        relationship_hint=relationship_hint,
        scar_hint=scar_hint,
        season_hint=season_hint,
    )
