"""响应式帮忙：接 / 拒 / 延（判断制，非逐步确认）。"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, is_dataclass
from dataclasses import fields as dc_fields
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from qi.action.permission import (
    can_allow_app,
    can_disk,
    can_open,
    can_read_user_file,
    can_together,
    can_write,
    scar_blocks_kind,
)

logger = logging.getLogger("qi.action.judgment")

DELEGATE_QUEUE_KEY = "user_delegate_queue"
MAX_DELEGATE_QUEUE = 5

OUTCOME_ACCEPT = "accept"
OUTCOME_DECLINED = "declined"
OUTCOME_DEFERRED = "deferred"
OUTCOME_RECAP = "recap_required"

_KIND_PERMISSION = {
    "assist": lambda stage, scars: can_read_user_file(stage, scars=scars)[0],
    "open": lambda stage, scars: can_open(stage),
    "disk": lambda stage, scars: can_disk(stage),
    "write": lambda stage, scars: can_write(stage),
    "together": lambda stage, scars: can_together(stage),
    "delegate_search": lambda stage, scars: can_open(stage),
    "allow": lambda stage, scars: can_allow_app(stage, scars),
}


@dataclass
class JudgmentResult:
    decision: str  # accept | decline | defer
    qi_line: str = ""
    motive: dict[str, Any] = field(default_factory=dict)


def judge_responsive_action(
    kind: str,
    *,
    relationship_stage: str,
    scars: list[dict] | None = None,
    energy: float = 0.5,
    mode: str = "awake",
    in_stasis: bool = False,
    pending_user_messages: int = 0,
    delegate_queue_len: int = 0,
    pressure_throttle: float = 0.0,
) -> JudgmentResult:
    """非 irreversible 响应式行动：接 / 拒 / 延。动机须可写入 trace。"""
    motive: dict[str, Any] = {
        "kind": kind,
        "stage": relationship_stage,
        "energy": round(float(energy), 3),
        "mode": mode,
    }

    if in_stasis:
        return JudgmentResult(
            OUTCOME_DECLINED,
            "我现在还在蛰伏，帮不了你。",
            {**motive, "reason": "stasis"},
        )
    if mode == "dreaming":
        return JudgmentResult(
            OUTCOME_DECLINED,
            "我在梦里……醒了我再看。",
            {**motive, "reason": "dreaming"},
        )

    checker = _KIND_PERMISSION.get(kind)
    if checker is None:
        return JudgmentResult(
            OUTCOME_DECLINED,
            "这个我还不会。",
            {**motive, "reason": "unknown_kind"},
        )
    if scar_blocks_kind(kind if kind != "allow" else "open", scars):
        return JudgmentResult(
            OUTCOME_DECLINED,
            "这件事我还不太敢碰，再等等好吗。",
            {**motive, "reason": "scar"},
        )
    if not checker(relationship_stage, scars):
        return JudgmentResult(
            OUTCOME_DECLINED,
            "这个我得先跟你熟一点再说。",
            {**motive, "reason": "relationship"},
        )

    if pending_user_messages > 0 or delegate_queue_len >= MAX_DELEGATE_QUEUE:
        return JudgmentResult(
            OUTCOME_DEFERRED,
            "稍等，我弄完手上的再帮你看。",
            {**motive, "reason": "busy"},
        )
    if float(pressure_throttle or 0.0) >= 0.75:
        return JudgmentResult(
            OUTCOME_DEFERRED,
            "我这会儿有点累，等我缓一下再帮你看。",
            {**motive, "reason": "pressure"},
        )
    if float(energy) < 0.18:
        return JudgmentResult(
            OUTCOME_DEFERRED,
            "我现在精力不太好，稍等一下行吗。",
            {**motive, "reason": "low_energy"},
        )

    accept_lines = {
        "assist": "好，我看看。",
        "open": "好，我打开看看。",
        "disk": "嗯，我瞧一眼。",
        "write": "好，我写。",
        "together": "好，一起看。",
        "delegate_search": "这个我不太清楚，我去查一下。",
        "allow": "嗯，我记一下。",
    }
    return JudgmentResult(
        OUTCOME_ACCEPT,
        accept_lines.get(kind, "好。"),
        {**motive, "reason": "willing"},
    )


def judgment_result_dict(result: JudgmentResult) -> dict[str, Any]:
    return {
        "decision": result.decision,
        "qi_line": result.qi_line,
        "motive": dict(result.motive),
    }


async def load_delegate_queue(db: Any) -> list[dict[str, Any]]:
    raw = await db.get_body_memory(DELEGATE_QUEUE_KEY)
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        items = raw.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


async def save_delegate_queue(db: Any, items: list[dict[str, Any]]) -> None:
    await db.set_body_memory(
        DELEGATE_QUEUE_KEY,
        {"items": items[:MAX_DELEGATE_QUEUE]},
    )


def serialize_delegate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """入队前把 request dataclass 等转成可 JSON 的结构。"""
    out: dict[str, Any] = {}
    for key, val in payload.items():
        if key == "request_obj" and val is not None:
            if is_dataclass(val):
                out[key] = asdict(val)
            elif isinstance(val, dict):
                out[key] = val
            else:
                out[key] = str(val)
        else:
            out[key] = val
    return out


def restore_delegate_request(kind: str, payload: dict[str, Any]) -> Any | None:
    """履约时把队列里的 request_obj 还原为 dataclass。"""
    raw = payload.get("request_obj")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return raw
    try:
        if kind == "disk":
            from qi.action.disk import DiskRequest

            return DiskRequest(
                intent=str(raw.get("intent") or "list_dir"),
                path=str(raw.get("path") or ""),
                listed_entries=list(raw.get("listed_entries") or []),
            )
        if kind == "open":
            from qi.action.open import OpenRequest

            names = {f.name for f in dc_fields(OpenRequest)}
            return OpenRequest(**{k: v for k, v in raw.items() if k in names})
        if kind == "write":
            from qi.action.write import WriteRequest

            names = {f.name for f in dc_fields(WriteRequest)}
            return WriteRequest(**{k: v for k, v in raw.items() if k in names})
        if kind == "together":
            from qi.action.together import TogetherRequest

            names = {f.name for f in dc_fields(TogetherRequest)}
            return TogetherRequest(**{k: v for k, v in raw.items() if k in names})
    except Exception:
        logger.debug("restore_delegate_request 失败 kind=%s", kind, exc_info=True)
    return None


async def enqueue_delegate(
    db: Any,
    *,
    kind: str,
    summary: str,
    payload: dict[str, Any],
    user_text: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now()
    items = await load_delegate_queue(db)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "kind": kind,
        "summary": (summary or "")[:200],
        "payload": serialize_delegate_payload(payload),
        "user_text": (user_text or "")[:500],
        "created_at": now.isoformat(timespec="seconds"),
    }
    items.append(entry)
    await save_delegate_queue(db, items[-MAX_DELEGATE_QUEUE:])
    return entry


async def pop_delegate_queue(db: Any) -> dict[str, Any] | None:
    items = await load_delegate_queue(db)
    if not items:
        return None
    head, rest = items[0], items[1:]
    await save_delegate_queue(db, rest)
    return head


async def write_delegate_fulfillment_narrative(
    narrative: Any,
    *,
    kind: str,
    summary: str,
    user_hint: str = "",
) -> None:
    if narrative is None:
        return
    hint = f"（你之前问的是：{user_hint[:40]}）" if user_hint else ""
    await narrative.save(
        f"你请我帮忙{kind}，我做了。{summary}{hint}",
        importance=0.62,
        tags=["delegate", kind],
    )
