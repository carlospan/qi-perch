"""表达层——意向卡 → 语言器官（LLM 措辞 / 模板降级）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.intention import IntentionCard
from qi.llm.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway

logger = logging.getLogger("qi.expression")


def render_template(card: IntentionCard) -> str:
    """断网/空返回模板：朴素、有出处，只使用卡内素材。"""
    if card.silence:
        return ""
    primary = card.primary_text()
    act = card.act
    short = card.length == "short"

    if act == "answer":
        if primary:
            text = f"{primary}……嗯。"
        else:
            text = "……嗯，这个我现在想不清楚。"
    elif act == "acknowledge":
        text = f"……我听见了。{primary}" if primary else "……我听见了。"
    elif act == "share_state":
        text = f"……{primary}。" if primary else "……嗯。"
    elif act == "recall":
        text = f"记得。{primary}。" if primary else "……我不确定自己还记不记得。"
    elif act == "comfort_back":
        text = "……谢谢你。我就在这儿。"
    elif act == "take_tease":
        text = "……哼。被你说中了。" if "克制" not in card.stance else "……这样啊。"
    elif act == "honest_hurt":
        text = "……这句话，我接住了。"
    elif act == "free_talk":
        text = f"……嗯。{primary}" if primary else "……嗯。"
    elif act == "silence":
        return ""
    else:
        text = f"……嗯。{primary}" if primary else "……嗯。"

    text = text.strip()
    if short and len(text) > 40:
        text = text[:40].rstrip("。…") + "…"
    return text


class Expression:
    """栖开口的地方。先有意向，再措辞。"""

    def __init__(self, config: dict, llm: LLMGateway):
        self.config = config
        self.llm = llm
        self.prompt_builder = PromptBuilder()

    async def express(
        self,
        user_message: str,
        emotion: EmotionState,
        now: datetime,
        intention: IntentionCard,
        recent_messages: list[dict] | None = None,
        memories: list[dict] | None = None,
        inner_extras: dict[str, str] | None = None,
        relationship_stage: str = "stranger",
        shared_culture: str = "",
        relationship_hint: str = "",
        scar_hint: str = "",
        season: str = "spring",
        proactive_kind: str | None = None,
    ) -> str:
        if intention.silence or intention.act == "silence":
            intention.outcome = "silence"
            return ""

        messages = self.prompt_builder.build_conversation_prompt(
            user_message=user_message,
            emotion=emotion,
            now=now,
            recent_messages=recent_messages or [],
            memories=memories or [],
            inner_extras=inner_extras,
            relationship_stage=relationship_stage,
            shared_culture=shared_culture,
            relationship_hint=relationship_hint,
            scar_hint=scar_hint,
            season=season,
            proactive_kind=proactive_kind,
            intention=intention,
        )
        text = ""
        try:
            text = await self.llm.call(purpose="conversation", messages=messages)
        except Exception:
            logger.debug("表达 LLM 异常，走模板", exc_info=True)
            text = ""

        if text and str(text).strip():
            intention.outcome = "llm"
            return str(text).strip()

        # UNREACHABLE / EMPTY：一律模板开口（契约演进）
        templated = render_template(intention)
        if templated:
            intention.outcome = "template"
            return templated
        intention.outcome = "empty"
        return ""
