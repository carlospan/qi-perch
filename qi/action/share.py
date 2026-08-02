"""分享创造——把独处时写下的东西真正递到你面前。"""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_SUCCESS,
    can_share,
)

if TYPE_CHECKING:
    from qi.action.budget import ActionBudget
    from qi.core.emotion import EmotionState
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

# 递出时栖附上的话——脆弱、不好意思，不是「系统生成内容如下」
_QI_LINES = (
    "我今天写了个东西……给你。",
    "写了一点。有点不好意思，但想让你看。",
    "我写了个东西。很短。给你。",
    "有一段话一直放在心里……想给你看。",
)


def _emotion_json(emotion: EmotionState | None) -> str | None:
    if emotion is None:
        return None
    if hasattr(emotion, "model_dump_json"):
        return emotion.model_dump_json()
    return None


def _parse_emotion_context(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return raw


class ShareAction:
    """
    L7 起手式：纯内部，不引入工具调度。
    L4 maybe_share_hint = 提起；本类 deliver = 递出。
    deliver 只占 ActionBudget，不占 ProactiveGate。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
    ):
        self.db = db
        self.narrative = narrative

    async def deliver(
        self,
        creation: dict,
        emotion: EmotionState | None,
        relationship_stage: str,
        *,
        season: str | None = None,
        now: datetime | None = None,
        qi_line: str | None = None,
    ) -> dict:
        """
        把一条未递出创作标为 shared，写入 actions，显著者织入 narrative。
        返回卡片 dict（L6 渲染接口；本层只定结构）。
        调用方须已通过 can_share + budget；本方法不再二次占预算。
        """
        _ = relationship_stage  # 门控在 try_share；此处保留签名与设计稿一致
        now = now or datetime.now()
        creation_id = int(creation["id"])
        content = str(creation.get("content") or "")
        creation_type = str(creation.get("type") or "note")
        # C4 表达层：话术选型，不是动机来源
        line = qi_line or random.choice(_QI_LINES)

        await self.db.mark_creation_shared(creation_id)

        summary = f"我把一段创作递给他了。{line}"
        action_id = await self.db.insert_action(
            "share",
            summary,
            target="user",
            outcome=OUTCOME_SUCCESS,
            emotion_context=_emotion_json(emotion),
            season=season,
            now=now,
        )

        if self.narrative is not None:
            snippet = content[:80].replace("\n", " ")
            await self.narrative.save(
                f"我把写给自己的一段话递给他看了。大概是：{snippet}",
                importance=0.78,
                emotional_intensity=0.65,
                tags=["action", "share", "creation"],
            )

        return {
            "type": "creation_card",
            "creation_id": creation_id,
            "creation_type": creation_type,
            "content": content,
            "emotion_context": _parse_emotion_context(
                creation.get("emotion_context")
            ),
            "qi_line": line,
            "action_id": action_id,
            "season": season,
        }

    async def try_share(
        self,
        emotion: EmotionState,
        relationship_stage: str,
        budget: ActionBudget,
        *,
        season: str = "spring",
        now: datetime | None = None,
    ) -> dict | None:
        """
        门控 + 取未递出创作 + deliver + budget.record。
        供阶段三 ActionLayer 调用；LLM 不直接调本方法。
        """
        now = now or datetime.now()
        if not can_share(relationship_stage):
            return None
        if not budget.can_autonomous(now):
            return None
        creation = await self.db.load_unshared_creation()
        if not creation:
            return None
        card = await self.deliver(
            creation,
            emotion,
            relationship_stage,
            season=season,
            now=now,
        )
        budget.record("share", now)
        return card
