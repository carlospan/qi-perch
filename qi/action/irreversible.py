"""不可逆对外动作（发微信、转账等）——诚实说明尚未实现，不叠确认门。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.permission import OUTCOME_FAILED_CAPABILITY, can_irreversible

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.action.irreversible")

_IRREVERSIBLE_CUES = re.compile(
    r"(帮.{0,16})?(发|发送).{0,20}(微信|短信|邮件|微博|消息给)|"
    r"(给|向).{0,12}(发|发送).{0,12}(微信|短信|邮件)|"
    r"(转账|付款|发红包|代付)",
    re.I,
)


def looks_like_irreversible_request(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 240:
        return False
    return bool(_IRREVERSIBLE_CUES.search(t))


def irreversible_qi_line(*, allowed: bool) -> str:
    if not allowed:
        return "这类对外发消息、转账的事，我们再熟一点我再碰。"
    return (
        "帮你发微信、发短信这类事我还做不到——"
        "不能替你对外发消息或付款；我能帮的是你看文件、开链接、写你授权的笔记。"
    )


async def try_irreversible_message(
    brain: Brain, text: str, now: datetime
) -> str | None:
    """识别不可逆意图并诚实回应；返回 qi_line 或 None（非此类请求）。"""
    if not looks_like_irreversible_request(text):
        return None
    scars = None
    if brain._db is not None:
        try:
            scars = await brain._db.list_scars()
        except Exception:
            scars = None
    trust = 0.5
    if brain.relationship is not None:
        trust = float(getattr(brain.relationship.state, "trust", 0.5) or 0.5)
    allowed, _confirm = can_irreversible(
        brain.relationship_stage, trust=trust, scars=scars
    )
    line = irreversible_qi_line(allowed=allowed)
    outcome = OUTCOME_FAILED_CAPABILITY
    if brain._db is not None:
        detail: dict[str, Any] = {
            "reason": "not_implemented",
            "allowed": allowed,
            "user_text": text[:200],
        }
        await brain._db.insert_action(
            "irreversible",
            text[:120],
            target="user",
            outcome=outcome,
            season=brain._current_season(),
            now=now,
            detail_json=json.dumps(detail, ensure_ascii=False),
        )
    await brain._deliver_qi_message(line, now, proactive=False)
    return line
