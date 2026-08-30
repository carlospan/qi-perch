"""设置页试连通：结果文案（不进 speech / 谈区）。"""

from __future__ import annotations

from typing import Literal

ProbeKind = Literal["ok", "missing_key", "unreachable", "empty", "timeout"]

PROBE_TIMEOUT_S = 20.0

_MESSAGES: dict[ProbeKind, str] = {
    "ok": "通了，可以回去找她说了。",
    "missing_key": "还没有可用的模型钥匙。先保存 API 密钥再试。",
    "unreachable": "连不上模型。检查网络、接口地址，或钥匙是否有效。",
    "empty": "这轮没接好。可再试一次。",
    "timeout": "等太久了，先当没通。可再试一次。",
}


def probe_result_payload(*, kind: ProbeKind) -> dict:
    """WS `settings_llm_probe` 的 payload。"""
    return {
        "ok": kind == "ok",
        "kind": kind,
        "message": _MESSAGES[kind],
    }


def kind_from_probe_outcome(failure: str | None, *, timed_out: bool = False) -> ProbeKind:
    if timed_out:
        return "timeout"
    if failure is None:
        return "ok"
    if failure == "missing_key":
        return "missing_key"
    if failure == "unreachable":
        return "unreachable"
    if failure == "empty":
        return "empty"
    return "unreachable"


async def run_settings_llm_probe(llm, *, timeout_s: float = PROBE_TIMEOUT_S) -> dict:
    """对 gateway 跑一记探测；调用方不得写入对话历史。"""
    if llm is None or not hasattr(llm, "probe"):
        return probe_result_payload(kind="unreachable")
    try:
        outcome, timed_out = await llm.probe(timeout_s=timeout_s)
    except Exception:
        return probe_result_payload(kind="unreachable")
    if timed_out:
        return probe_result_payload(kind="timeout")
    if outcome.ok:
        return probe_result_payload(kind="ok")
    return probe_result_payload(
        kind=kind_from_probe_outcome(outcome.failure, timed_out=False)
    )
