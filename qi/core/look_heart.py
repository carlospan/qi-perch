"""Look 所见走心：冲击入情 + 当场主观短说（非表演堆词）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.action.look import FIRST_NOTICE_LINE
from qi.core.emotion import apply_event_impact
from qi.core.intention import IntentionCard, Material

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.core.look_heart")

# 自主瞥冲击缩尺，护「安静不打扰」；邀瞥全量
_AUTONOMOUS_IMPACT_SCALE = 0.4
_REACTIVE_IMPACT_SCALE = 1.0

_LOOK_MUST = [
    "只依据【材料】里的所见开口，不编造画面外细节、标题或进程名",
    "一两句短说：有依据的主观（犹豫、好奇、不适、想问一句皆可），不是画面清单或窗口说明书",
    "不要堆情绪词或客服腔，不要解释看屏规则",
]


def _impression_text(result: dict) -> str:
    found = result.get("found")
    if isinstance(found, dict):
        raw = str(found.get("impression") or "").strip()
        if raw:
            return raw
    return str(result.get("summary") or result.get("qi_line") or "").strip()


async def enrich_look_glance(brain: Brain, result: dict, now: datetime) -> None:
    """
    成功 look_glance：所见 → 情绪冲击，再薄表达成主观短说。
    就地改 result['qi_line']；幂等（_look_heart_done）。
    """
    if result.get("_look_heart_done"):
        return
    if result.get("type") != "look_glance":
        return
    if result.get("outcome") != "success":
        return

    impression = _impression_text(result)
    if not impression:
        result["_look_heart_done"] = True
        return

    await _apply_look_impact(brain, result, impression, now)
    await _rewrite_look_qi_line(brain, result, impression, now)
    if result.get("reactive"):
        await _enqueue_look_loop(brain, impression)
        await _notice_look_facts(brain, impression, now)
    result["_look_heart_done"] = True


async def _load_look_loops(brain: Brain) -> list[dict]:
    try:
        if hasattr(brain, "_load_open_loops"):
            loops = await brain._load_open_loops()
            return list(loops) if loops else []
    except Exception:
        logger.debug("look 读 open_loops 失败", exc_info=True)
    return []


async def _enqueue_look_loop(brain: Brain, impression: str) -> None:
    db = getattr(brain, "_db", None)
    if db is None:
        return
    try:
        from qi.memory.open_loops import OpenLoopQueue

        q = OpenLoopQueue(db)
        await q.load()
        seed = (impression or "").strip()[:40]
        await q.enqueue("look_glance", seed=seed)
    except Exception:
        logger.debug("look 写 open_loops 失败", exc_info=True)


async def _notice_look_facts(
    brain: Brain, impression: str, now: datetime
) -> None:
    memory = getattr(brain, "memory", None)
    if memory is None or not hasattr(memory, "notice_facts"):
        return
    try:
        await memory.notice_facts(
            impression,
            brain.emotion,
            brain.relationship_stage,
            now,
        )
    except Exception:
        logger.debug("look notice_facts 失败", exc_info=True)


async def _apply_look_impact(
    brain: Brain, result: dict, impression: str, now: datetime
) -> None:
    if brain.perception is None:
        return
    try:
        stage = brain.relationship_stage
        impact = await brain.perception.assess_impact_async(
            impression,
            brain.emotion,
            relationship_stage=stage,
        )
        scale = (
            _REACTIVE_IMPACT_SCALE
            if result.get("reactive")
            else _AUTONOMOUS_IMPACT_SCALE
        )
        impact = float(impact) * scale
        brain.emotion = apply_event_impact(brain.emotion, impact)
        brain.emotion = brain.perception.apply_security_hint(brain.emotion, impact)
        result["_look_impact"] = impact
        try:
            await brain._maybe_save_emotion(now, force=True)
        except Exception:
            logger.debug("look 冲击后落盘情绪失败", exc_info=True)
    except Exception:
        logger.debug("look 所见冲击失败", exc_info=True)


async def _rewrite_look_qi_line(
    brain: Brain, result: dict, impression: str, now: datetime
) -> None:
    if brain.expression is None or brain.llm is None:
        return

    from qi.core.brain_context import retrieve_filtered_memories

    first_notice = bool(result.get("first_notice"))
    reactive = bool(result.get("reactive"))
    user_q = str(result.get("user_question") or "").strip()
    if reactive and user_q:
        user_message = f"对方问：「{user_q}」\n你刚瞥了一眼屏幕；结合所见短答。"
        query = f"{user_q} {impression}".strip()
    else:
        user_message = "（你刚瞥了一眼对方的屏幕）"
        query = impression

    memories = await retrieve_filtered_memories(
        brain, query, recent_messages=[], top_k=3
    )

    materials = [Material(tag="cue", text=impression)]
    loops = await _load_look_loops(brain)
    if loops:
        concern = str(loops[0].get("concern") or "").strip()
        if concern:
            materials.append(Material(tag="loop", text=concern[:80]))

    card = IntentionCard(
        act="acknowledge",
        topic="瞥见屏幕",
        materials=materials,
        stance="诚实的主观：有依据的印象或联想可以，虚构事实不行",
        must=list(_LOOK_MUST),
        length="short",
        channel="proactive",
        source="look_glance",
    )

    try:
        line = (
            await brain.expression.express(
                user_message=user_message,
                emotion=brain.emotion,
                now=now,
                intention=card,
                recent_messages=[],
                memories=memories,
                relationship_stage=brain.relationship_stage,
                season=str(result.get("season") or "spring"),
                proactive_kind=None,
            )
            or ""
        ).strip()
    except Exception:
        logger.debug("look 主观短说失败", exc_info=True)
        line = ""

    if not line:
        return

    if first_notice and not line.startswith(FIRST_NOTICE_LINE):
        line = f"{FIRST_NOTICE_LINE}{line}"
    result["qi_line"] = line
    result["summary"] = (line[:80] if line else result.get("summary") or "").strip()
