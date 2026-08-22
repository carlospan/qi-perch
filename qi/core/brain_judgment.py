"""Brain 侧：响应式帮忙判断 + 委托队列履约。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.judgment import (
    OUTCOME_ACCEPT,
    OUTCOME_DECLINED,
    OUTCOME_DEFERRED,
    OUTCOME_RECAP,
    enqueue_delegate,
    judge_responsive_action,
    judgment_result_dict,
    load_delegate_queue,
    pop_delegate_queue,
    serialize_delegate_payload,
)

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain.judgment")


async def judgment_context(brain: Brain) -> dict[str, Any]:
    pressure_throttle = 0.0
    pr = getattr(brain, "last_pressure_response", None)
    if pr is not None:
        pressure_throttle = float(getattr(pr, "throttle", 0.0) or 0.0)
    q_len = 0
    if brain._db is not None:
        try:
            q_len = len(await load_delegate_queue(brain._db))
        except Exception:
            q_len = 0
    return {
        "relationship_stage": brain.relationship_stage,
        "scars": await brain._db.list_scars() if brain._db else None,
        "energy": float(getattr(brain.emotion, "energy", 0.5) or 0.5),
        "mode": brain.emotion.mode.value,
        "in_stasis": bool(brain.in_stasis),
        "pending_user_messages": len(brain._pending_queue),
        "delegate_queue_len": q_len,
        "pressure_throttle": pressure_throttle,
    }


async def judge_for_kind(brain: Brain, kind: str):
    ctx = await judgment_context(brain)
    trust = 0.5
    if brain.relationship is not None:
        trust = float(getattr(brain.relationship.state, "trust", 0.5) or 0.5)
    _ = trust
    return judge_responsive_action(
        kind,
        relationship_stage=ctx["relationship_stage"],
        scars=ctx["scars"],
        energy=ctx["energy"],
        mode=ctx["mode"],
        in_stasis=ctx["in_stasis"],
        pending_user_messages=ctx["pending_user_messages"],
        delegate_queue_len=ctx["delegate_queue_len"],
        pressure_throttle=ctx["pressure_throttle"],
    )


async def handle_decline_or_defer(
    brain: Brain,
    judgment,
    *,
    kind: str,
    user_text: str,
    payload: dict[str, Any],
    now: datetime,
) -> str | None:
    motive = judgment_result_dict(judgment)
    if judgment.decision == OUTCOME_DECLINED:
        if brain._db is not None:
            await brain._db.insert_action(
                kind,
                judgment.qi_line[:200],
                target="user",
                outcome=OUTCOME_DECLINED,
                season=brain._current_season(),
                now=now,
                detail_json=json.dumps({"motive": motive}, ensure_ascii=False),
            )
        await brain._deliver_qi_message(judgment.qi_line, now, proactive=False)
        return judgment.qi_line

    if judgment.decision == OUTCOME_DEFERRED and brain._db is not None:
        stored_payload = serialize_delegate_payload(payload)
        await enqueue_delegate(
            brain._db,
            kind=kind,
            summary=judgment.qi_line,
            payload=stored_payload,
            user_text=user_text,
            now=now,
        )
        await brain._db.insert_action(
            kind,
            f"deferred:{kind}",
            target="user",
            outcome=OUTCOME_DEFERRED,
            season=brain._current_season(),
            now=now,
            detail_json=json.dumps(
                {"motive": motive, "payload": stored_payload}, ensure_ascii=False
            ),
        )
        await brain._deliver_qi_message(judgment.qi_line, now, proactive=False)
        return judgment.qi_line
    return None


async def try_fulfill_delegate_queue(brain: Brain, now: datetime) -> None:
    """空闲拍：履约延后委托（无用户消息时）。"""
    if brain._db is None or brain.action is None:
        return
    if brain._pending_queue or brain.user_online is False:
        return
    if brain.emotion.mode.value == "dreaming" or brain.in_stasis:
        return
    item = await pop_delegate_queue(brain._db)
    if not item:
        return
    kind = str(item.get("kind") or "")
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    user_text = str(item.get("user_text") or "")
    try:
        if kind == "delegate_search":
            query = str(payload.get("query") or "")
            from qi.action.delegate_search import DelegateSearchAction

            ds = DelegateSearchAction(
                brain._db,
                web=brain.action._build_explore_web(),
                llm=brain.llm,
                narrative=brain.action.assist.narrative,
            )
            result = await ds.execute(
                query,
                season=brain._current_season(),
                now=now,
                user_text=user_text,
                motive=payload.get("motive"),
            )
            if result is not None:
                line = (
                    f"你刚才问的那个，我查过了。{result.get('qi_line') or ''}"
                ).strip()
                if line:
                    result = {**result, "qi_line": line, "speak": True}
                await brain._deliver_action_result(result, now)
        elif kind in ("open", "disk", "write", "together", "assist"):
            from qi.action.judgment import restore_delegate_request

            req_obj = restore_delegate_request(kind, payload)
            # 简化为重新走 execute_kind（confirmed=True）
            result = await brain.action.execute_kind(
                kind,
                brain.emotion,
                brain.relationship_stage,
                brain._current_season(),
                now,
                mode=brain.emotion.mode.value,
                user_online=brain.user_online,
                scars=await brain._db.list_scars(),
                trust=float(
                    getattr(brain.relationship.state, "trust", 0.5)
                    if brain.relationship
                    else 0.5
                ),
                op=payload.get("op"),
                target_path=payload.get("target_path"),
                confirmed=True,
                payload=req_obj,
            )
            if result is not None:
                prefix = "你刚才说的那件事，我做了。"
                ql = str(result.get("qi_line") or "").strip()
                if ql:
                    result = {**result, "qi_line": f"{prefix}{ql}", "speak": True}
                await brain._deliver_action_result(result, now)
    except Exception:
        logger.exception("delegate 履约失败 kind=%s", kind)


async def try_delegate_search_message(brain: Brain, text: str, now: datetime) -> str | None:
    from qi.action.delegate_search import (
        extract_search_query,
        looks_like_delegate_search,
    )

    if not looks_like_delegate_search(text):
        return None
    judgment = await judge_for_kind(brain, "delegate_search")
    if judgment.decision == OUTCOME_DECLINED:
        return await handle_decline_or_defer(
            brain,
            judgment,
            kind="delegate_search",
            user_text=text,
            payload={},
            now=now,
        )
    if judgment.decision == OUTCOME_DEFERRED:
        query = await extract_search_query(text, brain.llm)
        return await handle_decline_or_defer(
            brain,
            judgment,
            kind="delegate_search",
            user_text=text,
            payload={
                "query": query or text[:120],
                "motive": judgment_result_dict(judgment),
            },
            now=now,
        )
    query = await extract_search_query(text, brain.llm)
    if not query:
        await brain._deliver_qi_message(
            "你想让我查什么？", now, proactive=False
        )
        return "你想让我查什么？"
    from qi.action.delegate_search import DelegateSearchAction

    ds = DelegateSearchAction(
        brain._db,
        web=brain.action._build_explore_web() if brain.action else None,
        llm=brain.llm,
        narrative=brain.action.assist.narrative if brain.action else None,
    )
    motive = judgment_result_dict(judgment)
    result = await ds.execute(
        query,
        season=brain._current_season(),
        now=now,
        user_text=text,
        motive=motive.get("motive"),
    )
    if result is not None:
        ql = judgment.qi_line
        if result.get("qi_line"):
            result = {**result, "qi_line": f"{ql}{result['qi_line']}", "speak": True}
        await brain._deliver_action_result(result, now)
        return (result.get("qi_line") or "").strip() or None
    return None
