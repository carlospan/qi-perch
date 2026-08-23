"""对话 prompt 上下文组装——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.brain_types import PromptContext
from qi.memory.facts import format_facts_for_prompt
from qi.relationship.culture import format_culture_for_prompt
from qi.relationship.scars import format_scars_for_prompt

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")

# 高频虚词双字；挡假重叠（如「不要」），不挡话题词（如「助眠」「烤鸭」）
_STOP_WORDS = frozenset(
    {
        "知道",
        "可以",
        "不要",
        "没有",
        "什么",
        "这个",
        "那个",
        "自己",
        "不是",
        "已经",
        "怎么",
        "因为",
        "如果",
        "所以",
        "然后",
        "就是",
        "觉得",
        "应该",
        "真的",
        "还是",
        "但是",
        "不过",
        "可能",
        "其实",
        "有点",
        "一下",
        "一次",
        "一直",
        "一定",
        "一样",
        "只是",
        "不会",
        "一个",
        "今天",
        "现在",
        "刚才",
        "上次",
        "为什么",
        "放在",
        "心上",
    }
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _cjk_bigrams(text: str) -> set[str]:
    """汉字双字滑动窗口（无分词依赖）。"""
    chars = _CJK_RE.findall(text or "")
    if len(chars) < 2:
        return set()
    return {"".join(chars[i : i + 2]) for i in range(len(chars) - 1)}


def _filter_by_topic_relevance(
    memories: list[dict],
    query: str,
    recent_messages: list[dict],
    *,
    min_overlap: int = 1,
) -> list[dict]:
    """过滤话题无关记忆。话题双字与记忆双字至少重叠 min_overlap 才保留。

    全部不重叠时返回空列表（B1：不塞回错记忆）。
    """
    if not memories:
        return []

    topic_text = query or ""
    for m in recent_messages[-2:]:
        topic_text += " " + (m.get("content") or "")
    topic_words = {w for w in _cjk_bigrams(topic_text) if w not in _STOP_WORDS}

    kept: list[dict] = []
    for mem in memories:
        content = str(mem.get("content") or "")
        mem_words = _cjk_bigrams(content)
        overlap = topic_words & mem_words
        if len(overlap) >= min_overlap:
            kept.append(mem)
        else:
            logger.debug(
                "检索相关门过滤: query_keys=%s mem_keys=%s",
                sorted(topic_words)[:10],
                sorted(mem_words)[:10],
            )
    return kept


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
        memories = _filter_by_topic_relevance(memories, query, recent)
        try:
            facts = await brain.memory.active_facts()
            extras["user_facts"] = format_facts_for_prompt(facts, brain.relationship_stage)
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

    shared_culture = "（还没有只属于你们的默契）"
    relationship_hint = ""
    scar_hint = ""
    season_hint = ""
    trust = 0.0
    culture_raw: list | str | None = None
    if brain.relationship is not None:
        shared_culture = format_culture_for_prompt(brain.relationship.state.shared_culture)
        relationship_hint = brain.relationship.stage_prompt_hint()
        season_hint = brain.relationship.state.season
        trust = float(brain.relationship.state.trust or 0)
        culture_raw = brain.relationship.state.shared_culture
    if brain.scars is not None and brain._db is not None:
        scars = await brain._db.list_scars()
        scar_hint = format_scars_for_prompt(scars)

    if brain.inner_life is not None:
        try:
            traces = list(brain._traces) if getattr(brain, "_traces", None) else None
            life_extras = await brain.inner_life.prompt_extras(
                brain.emotion,
                brain.relationship_stage,
                trust=trust,
                season=season_hint or "spring",
                shared_culture=culture_raw if culture_raw is not None else shared_culture,
                traces=traces,
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

    if pending:
        from qi.core.intention import short_emotion_label
        from qi.core.turn_understanding import (
            apply_turn_emotion_modulation,
            prepare_dialogue_turn,
            turn_understanding_to_extras,
        )

        tu = getattr(brain, "_current_turn", None)
        if tu is None or tu.user_message != pending:
            tu = await prepare_dialogue_turn(brain, pending, now)
        vb = getattr(brain, "_turn_valence_before", None)
        if vb is not None:
            apply_turn_emotion_modulation(
                tu,
                valence_before=float(vb),
                valence_after=float(brain.emotion.valence),
            )
        extras["present_emotion"] = short_emotion_label(brain.emotion)
        extras.update(turn_understanding_to_extras(tu))

    return PromptContext(
        recent_messages=recent,
        retrieved_memories=memories,
        extras=extras,
        shared_culture=shared_culture,
        relationship_hint=relationship_hint,
        scar_hint=scar_hint,
        season_hint=season_hint,
    )
