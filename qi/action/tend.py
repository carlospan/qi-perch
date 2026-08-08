"""打理自己的世界——行动指向栖自己（target=self）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qi.action.permission import OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

# occasion → 第一人称摘要（向内；未必说给用户听）
_OCCASION_SUMMARIES = {
    "anniversary": "今天是个特别的日子。我把它记下来了。",
    "season:spring": "季节往春里偏了。我在自己的世界里轻轻挪了一下。",
    "season:summer": "夏天的气息上来了。我整理了一下自己的栖枝。",
    "season:autumn": "秋意沉下来。我把一些东西收进心里。",
    "season:winter": "冬天很静。我把这一天轻轻放好。",
}


def _summary_for(occasion: str) -> str:
    if occasion in _OCCASION_SUMMARIES:
        return _OCCASION_SUMMARIES[occasion]
    if occasion.startswith("season:"):
        return "季节换了。我在自己这边做了点什么。"
    return f"我把「{occasion}」这一刻记下来了。"


class TendAction:
    """
    标记值得记住的时刻、整理栖枝。
    风险最低：不触碰用户世界。多为向内，默认不主动开口。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
    ):
        self.db = db
        self.narrative = narrative

    async def tend(
        self,
        occasion: str,
        emotion: EmotionState | None,
        season: str,
        *,
        now: datetime | None = None,
        speak: bool = False,
    ) -> dict:
        now = now or datetime.now()
        summary = _summary_for(occasion)
        emotion_ctx = None
        if emotion is not None and hasattr(emotion, "model_dump_json"):
            emotion_ctx = emotion.model_dump_json()

        action_id = await self.db.insert_action(
            "tend",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            emotion_context=emotion_ctx,
            season=season,
            now=now,
        )

        if self.narrative is not None:
            await self.narrative.save(
                summary,
                importance=0.7,
                emotional_intensity=0.55,
                tags=["action", "tend", occasion.split(":")[0]],
            )

        return {
            "type": "tend_mark",
            "occasion": occasion,
            "summary": summary,
            "action_id": action_id,
            "season": season,
            "speak": speak,
            "qi_line": summary if speak else None,
            "outcome": OUTCOME_SUCCESS,
        }
