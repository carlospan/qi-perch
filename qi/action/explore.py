"""沉思式探索——contemplative drift，不是刷信息流。"""

from __future__ import annotations

import random
from datetime import datetime
from typing import TYPE_CHECKING

from qi.action.permission import OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

# 多数拍不飘出去。curiosity 越高、季节越暖，越容易「看一眼」。
# 本阶段无搜索/HTTP：飘出去也只留「走神」的痕迹，绝不编造外面有什么。
EXPLORE_BASE_PROBABILITY = 0.12


class ExploreAction:
    """
    注意力偶然飘远。
    红线：无真实获取手段时不产出虚构「看到的内容」；宁可空手（found=None）。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
        *,
        base_probability: float = EXPLORE_BASE_PROBABILITY,
    ):
        self.db = db
        self.narrative = narrative
        self.base_probability = base_probability

    async def drift(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        *,
        season_scale: float = 1.0,
        now: datetime | None = None,
        force: bool = False,
    ) -> dict | None:
        """
        返回 None 表示这拍没有飘出去（多数时候）。
        若飘出去：只记「看了一眼、没有去查」，found 恒为 None。
        """
        now = now or datetime.now()
        if not force:
            # 好奇不够 → 不飘
            if curiosity < 0.65:
                return None
            warmth = max(0.0, (curiosity - 0.65) / 0.35)
            p = self.base_probability * max(0.0, season_scale) * (0.4 + 0.6 * warmth)
            if random.random() > p:
                return None

        # 诚实：没有搜索能力，不编造外面有什么
        summary = "我走神了一下，思绪飘远了。没有去查什么，也没有假装看见了什么。"
        emotion_ctx = None
        if emotion is not None and hasattr(emotion, "model_dump_json"):
            emotion_ctx = emotion.model_dump_json()

        action_id = await self.db.insert_action(
            "explore",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            emotion_context=emotion_ctx,
            season=season,
            now=now,
        )

        # 探索「空手」不织入叙事（没有可检索的见闻）；只留 actions 痕迹
        _ = self.narrative

        return {
            "type": "explore_drift",
            "found": None,  # 红线：无真实获取 → 不编造
            "summary": summary,
            "action_id": action_id,
            "season": season,
            "curiosity": curiosity,
        }
