"""内在生命协调器——一次心跳里偶尔发生的内心活动。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qi.inner_life.consciousness import (
    ConsciousnessStream,
    emotion_residue_hint,
)
from qi.inner_life.creativity import Creativity
from qi.inner_life.dream import DreamEngine
from qi.inner_life.identity_snapshot import (
    SNAPSHOT_VALENCE_SURGE,
    ensure_identity_snapshot,
    mark_identity_snapshot_stale,
)
from qi.inner_life.self_model import SelfModel

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database


def _journal_entry(kind: str, text: str, now: datetime) -> dict:
    return {
        "kind": kind,
        "text": text.strip(),
        "at": int(now.timestamp() * 1000),
    }


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
        self._just_woke = False
        self.last_journal_entries: list[dict] = []

    def mark_waking(self) -> None:
        """重启后标记：下一次非 awake 心跳触发醒来回溯意识流。"""
        self._just_woke = True

    async def tick(
        self,
        emotion: EmotionState,
        last_interaction: datetime,
        now: datetime,
        relationship_stage: str = "stranger",
        after_first_time: bool = False,
        *,
        prefer_close_loop: bool = False,
    ) -> EmotionState:
        """
        内在生命一拍。可能改写情绪（梦的余韵），不向外说话。
        awake 时不做随机意识流/创作，只处理余韵与反思标记。
        prefer_close_loop：对话首轮 deliver 后优先闭合 open loop（不污染当轮）。
        """
        self.last_journal_entries = []
        silence = now - last_interaction
        mode = emotion.mode.value

        # 梦境余韵：进入 awake 时应用一次
        if mode == "awake":
            dream = await self.db.load_latest_dream(min_retention=0.3)
            if dream and self._afterglow_done_for != dream["id"]:
                emotion = self.dreams.apply_afterglow(emotion, dream)
                self._afterglow_done_for = int(dream["id"])

        delta_v = emotion.valence - self._prev_valence
        await self.self_model.note_emotion_surge(delta_v)
        if abs(delta_v) > SNAPSHOT_VALENCE_SURGE:
            await mark_identity_snapshot_stale(self.db)

        # 对话首轮闭 loop：允许在 awake（deliver 之后）写一笔，供下一轮
        if prefer_close_loop:
            thought = await self.consciousness.maybe_generate(
                emotion,
                silence,
                prefer_close=True,
                prev_valence=self._prev_valence,
                prev_arousal=self._prev_arousal,
            )
            if thought:
                self.last_journal_entries.append(
                    _journal_entry("独白", thought, now)
                )
        # 第一次之后即使在对话中，也允许写一笔意识流；其余内在活动仍只在非 awake
        # waking 旗标：仅在非 awake 尝试；成功生成后才清除，避免 awake 首拍白耗
        elif mode != "awake" or after_first_time:
            try_waking = bool(self._just_woke and mode != "awake")
            thought = await self.consciousness.maybe_generate(
                emotion,
                silence,
                after_first_time=after_first_time,
                just_woke=try_waking,
                prev_valence=self._prev_valence,
                prev_arousal=self._prev_arousal,
            )
            if thought:
                self.last_journal_entries.append(
                    _journal_entry("独白", thought, now)
                )
            if try_waking and thought is not None:
                self._just_woke = False
        if mode != "awake" and not prefer_close_loop:
            meta = await self.consciousness.maybe_meta(emotion)
            if meta:
                self.last_journal_entries.append(_journal_entry("独白", meta, now))
            await self.creativity.maybe_create(emotion, relationship_stage)
            dream_text = await self.dreams.maybe_dream(emotion)
            if dream_text:
                self.last_journal_entries.append(
                    _journal_entry("梦", dream_text, now)
                )

        self._prev_valence = emotion.valence
        self._prev_arousal = emotion.arousal
        return emotion

    async def prompt_extras(
        self,
        emotion: EmotionState,
        relationship_stage: str,
        *,
        trust: float = 0.0,
        season: str = "spring",
        shared_culture: str | list | None = None,
        traces: list | None = None,
    ) -> dict[str, str]:
        """组装可注入对话 prompt 的内在生命片段。"""
        thoughts = await self.consciousness.recent_for_prompt()
        self_summary = await self.self_model.summary_for_prompt()
        dream_hint = await self.dreams.maybe_mention_hint(relationship_stage)
        creation_hint = await self.creativity.maybe_share_hint(
            emotion, relationship_stage
        )
        snapshot = await ensure_identity_snapshot(
            self.db,
            stage=relationship_stage,
            trust=trust,
            season=season,
            shared_culture=shared_culture,
            traces=traces,
        )
        return {
            "recent_thoughts": thoughts,
            "self_narrative": self_summary,
            "identity_snapshot": snapshot,
            "dream_hint": dream_hint or "",
            "creation_hint": creation_hint or "",
            "emotion_residue": emotion_residue_hint(emotion),
        }
