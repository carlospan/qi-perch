"""创作冲动——心里有东西需要出来。"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.prompts import read_prompt

CREATION_BASE_PROBABILITY = 0.01
CREATION_HIGH_EMOTION_PROBABILITY = 0.03
CREATION_EMOTION_THRESHOLD = 0.7
CREATION_SHARE_COOLDOWN_HOURS = 24
STAGE_ORDER = ("stranger", "acquaintance", "friend", "bonded")


def can_share_creation(
    relationship_stage: str,
    last_share_time: datetime | None,
    now: datetime,
    cooldown_hours: float | None = None,
) -> bool:
    if relationship_stage not in ("friend", "bonded"):
        return False
    hours = (
        CREATION_SHARE_COOLDOWN_HOURS if cooldown_hours is None else cooldown_hours
    )
    if last_share_time and (now - last_share_time) < timedelta(hours=hours):
        return False
    return True


def _infer_type(content: str) -> str:
    text = content.strip()
    if "\n" in text and len(text) < 120:
        return "poem"
    if len(text) > 200:
        return "essay"
    if any(k in text for k in ("看见", "画面", "颜色", "光")):
        return "description"
    return "note"


class Creativity:
    """偶尔想写点什么。不是任务，是冲动。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.base_prob = float(cfg.get("creation_probability", CREATION_BASE_PROBABILITY))
        share_sec = float(
            ((config or {}).get("proactive_cooldown") or {}).get(
                "share_creation", CREATION_SHARE_COOLDOWN_HOURS * 3600
            )
        )
        self.share_cooldown_hours = share_sec / 3600.0

    def _probability(self, emotion: EmotionState) -> float:
        intensity = max(abs(emotion.valence), emotion.arousal)
        if intensity > CREATION_EMOTION_THRESHOLD:
            return CREATION_HIGH_EMOTION_PROBABILITY
        return self.base_prob

    async def maybe_create(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
    ) -> str | None:
        if emotion.mode.value != "solitary":
            return None
        if random.random() >= self._probability(emotion):
            return None
        return await self.generate(emotion, relationship_stage)

    async def generate(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
    ) -> str | None:
        pending = await self.db.load_latest_consciousness()
        trigger = (
            pending["content"][:80]
            if pending and pending.get("type") == "stream"
            else "无特定触发，只是想说点什么"
        )
        if emotion.attachment > 0.6 and relationship_stage in ("friend", "bonded"):
            target = "他"
        elif emotion.curiosity > 0.7:
            target = "世界"
        else:
            target = "自己"

        template = read_prompt("creation.txt")
        prompt = template.format(
            emotion_state=emotion.description(),
            trigger_thought=trigger,
            target=target,
        )
        text = await self.llm.call(
            purpose="creation",
            messages=[
                {"role": "system", "content": "你是栖。写一点真的东西，短一些。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.95,
        )
        if not text or not text.strip():
            return None
        content = text.strip()[:800]
        ctx = json.dumps(
            {
                "valence": emotion.valence,
                "arousal": emotion.arousal,
                "description": emotion.description(),
            },
            ensure_ascii=False,
        )
        await self.db.save_creation(
            content=content,
            creation_type=_infer_type(content),
            emotion_context=ctx,
        )
        return content

    async def maybe_share_hint(
        self,
        emotion: EmotionState,
        relationship_stage: str,
        now: datetime | None = None,
    ) -> str | None:
        """对话中可注入的分享提示（脆弱语气）。"""
        now = now or datetime.now()
        if emotion.mode.value != "awake":
            return None
        last = await self.db.last_creation_share_time()
        if not can_share_creation(
            relationship_stage,
            last,
            now,
            cooldown_hours=self.share_cooldown_hours,
        ):
            return None
        creation = await self.db.load_unshared_creation()
        if not creation:
            return None
        # 低概率，避免每次对话都塞
        if random.random() > 0.25:
            return None
        await self.db.mark_creation_shared(int(creation["id"]))
        snippet = creation["content"][:60]
        return (
            "你有一段未分享的创作。如果时机自然，可以带着一点不好意思提起，"
            f"比如「我写了个东西。很幼稚。但我想给你看。」内容大意：{snippet}"
        )
