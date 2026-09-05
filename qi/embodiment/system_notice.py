"""具身系统态提示——失败可见，不进栖的 speech。"""

from __future__ import annotations

from typing import Literal

SystemNoticeKind = Literal[
    "missing_key",
    "unreachable",
    "empty",
    "timeout",
    "turn_busy",
    "queue_full",
    "delivery_timeout",
]

_MESSAGES: dict[SystemNoticeKind, str] = {
    "missing_key": "还没有可用的模型钥匙。点左下角齿轮打开设置，粘贴 API 密钥。",
    "unreachable": "这会儿连不上模型。可以再试一次，或检查网络与配置。",
    "empty": "这轮没接好。你可以再发一句。",
    "timeout": "等太久了，先解开输入。她可能还在想；若稍后仍回了，气泡会显示。",
    "turn_busy": "我还在想上一句。想改口可以直接说，或点「我想重说」。",
    "queue_full": "话说得有点密，这一句我还接不住。稍等我说完再发，或先「我想重说」。",
    "delivery_timeout": "这句可能没送到。气泡还在，你可以再发一次。",
}


def notice_payload(kind: SystemNoticeKind) -> dict:
    """WS `system_notice` 的 payload。"""
    return {
        "kind": kind,
        "message": _MESSAGES[kind],
        "action": "open_settings" if kind == "missing_key" else None,
    }


def kind_from_llm_failure(failure: str | None) -> SystemNoticeKind | None:
    if failure == "missing_key":
        return "missing_key"
    if failure == "unreachable":
        return "unreachable"
    if failure == "empty":
        return "empty"
    return None


def fallback_notice_for_silent_turn(brain) -> dict:
    """轮次无 speech、无挂起 notice 时的兜底系统态。

    有 last_outcome.failure → 对应 kind；否则 empty。
    """
    fail = None
    llm = getattr(brain, "llm", None)
    last = getattr(llm, "last_outcome", None) if llm is not None else None
    if last is not None:
        fail = getattr(last, "failure", None)
    kind = kind_from_llm_failure(fail) or "empty"
    return notice_payload(kind)
