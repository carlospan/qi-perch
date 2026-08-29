"""进行中轮次：打断 / 重说意图（懂意思，不靠口令）。"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Literal

from qi.core.perception import looks_like_typo_correction

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway

logger = logging.getLogger("qi.core.turn_interrupt")

InterruptKind = Literal["rephrase", "stop", "none"]

# 仅作「要不要问模型」的弱门控，不是唯一入口
_INTERRUPT_GATE_RE = re.compile(
    r"重说|改口|说错|打错|等下|等一下|先别|停一下|停下|打断|"
    r"不算|收回|我重来|重新说|不是这个意思|我想说的是|我是想说",
    re.I,
)

_CLASSIFY_PROMPT = """\
用户在你正在回复（或正在想）时又说了一句。判断他想干什么。
只输出一行 JSON，不要其它文字：
{"kind":"rephrase"|"stop"|"none"}

- rephrase：想改口 / 重说刚才那句 / 叫你先别按旧句答（含「我说错了」「我想重说」等，不限原话）
- stop：只想让你先停下、先别说了，未必立刻重说
- none：新话题或普通接话，不是叫你停/改口

用户句：
"""


def maybe_interrupt_gate(text: str) -> bool:
    """弱门控：像打断/改口时值得问模型；不是判定本身。"""
    t = (text or "").strip()
    if not t:
        return False
    if looks_like_typo_correction(t):
        return True
    if _INTERRUPT_GATE_RE.search(t):
        return True
    # 极短句在忙碌时也问一声（「等下」「停」等口令外说法）
    if len(t) <= 12:
        return True
    return False


def _parse_kind(raw: str) -> InterruptKind:
    text = (raw or "").strip()
    if not text:
        return "none"
    try:
        # 允许模型包 markdown
        if "{" in text:
            text = text[text.index("{") : text.rindex("}") + 1]
        data = json.loads(text)
        kind = str(data.get("kind") or "").strip().lower()
        if kind in ("rephrase", "stop", "none"):
            return kind  # type: ignore[return-value]
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.debug("打断意图 JSON 解析失败: %s", raw[:80])
    low = text.lower()
    if "rephrase" in low:
        return "rephrase"
    if "stop" in low:
        return "stop"
    return "none"


async def classify_turn_interrupt(
    llm: LLMGateway | None,
    text: str,
    *,
    force: bool = False,
) -> InterruptKind:
    """
    判别忙碌中用户句是否打断/重说。
    force=True：跳过门控（例如按钮已明示，不应走此函数）。
    """
    t = (text or "").strip()
    if not t:
        return "none"
    if not force and not maybe_interrupt_gate(t):
        return "none"
    if llm is None:
        return "none"
    try:
        raw = await llm.call(
            purpose="fact",
            messages=[
                {"role": "system", "content": "你只输出 JSON，判断用户是否要打断或重说。"},
                {"role": "user", "content": _CLASSIFY_PROMPT + t},
            ],
            temperature=0.0,
        )
    except Exception:
        logger.debug("打断意图 LLM 失败", exc_info=True)
        return "none"
    return _parse_kind(raw)


REPHRASE_ACK = "好，你重说。"
STOP_ACK = "嗯。"
