"""内在生命协调器——一次心跳里偶尔发生的内心活动。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qi.inner_life.consciousness import ConsciousnessStream
from qi.inner_life.creativity import Creativity
from qi.inner_life.dream import DreamEngine
from qi.inner_life.self_model import SelfModel

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database


class InnerLife:
    """独处时的生活。不向外说，但会留下痕迹。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict):
        self.db = db
        self.config = config
        self.consciousness = ConsciousnessStream(db, llm, config)
        self.dreams = DreamEngine(db, llm, config)
        self.creativity = Creativity(db, llm, config)
        self.self_model = SelfModel(db, llm, config)
        self._prev_valence = 0.1
        self._prev_arousal = 0.4
        self._afterglow_done_for: int | None = None

    async def tick(
        self,
        emotion: EmotionState,
        last_interaction: datetime,
        now: datetime,
        relationship_stage: str = "stranger",
        after_first_time: bool = False,
    ) -> EmotionState:
        """
        内在生命一拍。可能改写情绪（梦的余韵），不向外说话。
        awake 时不做随机意识流/创作，只处理余韵与反思标记。
        """
        silence = now - last_interaction
        mode = emotion.mode.value

        # 梦境余韵：进入 awake 时应用一次
        if mode == "awake":
            dream = await self.db.load_latest_dream(min_retention=0.3)
            if dream and self._afterglow_done_for != dream["id"]:
                emotion = self.dreams.apply_afterglow(emotion, dream)
                self._afterglow_done_for = int(dream["id"])

        delta_v = emotion.valence - self._prev_valence
        self.self_model.note_emotion_surge(delta_v)

        # 第一次之后即使在对话中，也允许写一笔意识流；其余内在活动仍只在非 awake
        if mode != "awake" or after_first_time:
            await self.consciousness.maybe_generate(
                emotion,
                silence,
                after_first_time=after_first_time,
                prev_valence=self._prev_valence,
                prev_arousal=self._prev_arousal,
            )
        if mode != "awake":
            await self.consciousness.maybe_meta(emotion)
            await self.creativity.maybe_create(emotion, relationship_stage)
            await self.dreams.maybe_dream(emotion)

        self._prev_valence = emotion.valence
        self._prev_arousal = emotion.arousal
        return emotion

    async def prompt_extras(
        self,
        emotion: EmotionState,
        relationship_stage: str,
    ) -> dict[str, str]:
        """组装可注入对话 prompt 的内在生命片段。"""
        thoughts = await self.consciousness.recent_for_prompt()
        self_summary = await self.self_model.summary_for_prompt()
        dream_hint = await self.dreams.maybe_mention_hint(relationship_stage)
        creation_hint = await self.creativity.maybe_share_hint(
            emotion, relationship_stage
        )
        return {
            "recent_thoughts": thoughts,
            "self_narrative": self_summary,
            "dream_hint": dream_hint or "",
            "creation_hint": creation_hint or "",
        }
