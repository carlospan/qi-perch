"""表达层——把内在状态变成一句话。"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import TYPE_CHECKING

from qi.llm.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway


class Expression:
    """栖开口的地方。想了想，再说话。"""

    def __init__(self, config: dict, llm: LLMGateway):
        self.config = config
        self.llm = llm
        self.prompt_builder = PromptBuilder()

    async def express(
        self,
        user_message: str,
        emotion: EmotionState,
        now: datetime,
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
        await asyncio.sleep(random.uniform(0.5, 1.5))

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
        )
        return await self.llm.call(purpose="conversation", messages=messages)
