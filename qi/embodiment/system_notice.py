"""具身系统态提示——失败可见，不进栖的 speech。"""

from __future__ import annotations

from typing import Literal

SystemNoticeKind = Literal["missing_key", "unreachable", "empty", "timeout", "turn_busy"]

_MESSAGES: dict[SystemNoticeKind, str] = {
    "missing_key": "还没有可用的模型钥匙。请检查 API 密钥配置。",
    "unreachable": "这会儿连不上模型。可以再试一次，或检查网络与配置。",
    "empty": "这轮没接好。你可以再发一句。",
    "timeout": "等太久了，先解开输入。若稍后她仍回了，气泡仍会显示。",
    "turn_busy": "我还在想上一句。想改口可以直接说，或点「我想重说」。",
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
