"""Brain Loop——栖的心脏。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.emotion import (
    EmotionState,
    apply_event_impact,
    clamp_emotion,
    should_express,
    step_emotion,
)
from qi.core.expression import Expression
from qi.core.perception import Perception
from qi.core.proactive import ProactiveGate, pick_proactive_kind
from qi.core.rhythm import determine_mode, next_interval
from qi.embodiment.avatar.controller import AvatarController
from qi.embodiment.voice.tts import create_tts, emotion_to_voice_params
from qi.inner_life import InnerLife
from qi.memory.first_time import FirstTimeMemory
from qi.memory.manager import MemoryManager
from qi.relationship import RelationshipEngine
from qi.relationship.culture import detect_shared_culture, format_culture_for_prompt
from qi.relationship.drift import build_updated_user_model, detect_user_drift
from qi.relationship.scars import ScarManager, format_scars_for_prompt
from qi.relationship.season import apply_season_effect, determine_season

if TYPE_CHECKING:
    from qi.embodiment.server import EmbodimentServer
    from qi.embodiment.voice.tts import TTSProvider
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.brain")


class Brain:
    """栖的意识核心。心跳 + 记忆 + 情绪 + 内在生命 + 关系。"""

    def __init__(self, config: dict, llm: LLMGateway):
        self.config = config
        self.llm = llm
        self.emotion = EmotionState()
        self.perception = Perception(config)
        self.expression = Expression(config, llm)
        self.memory: MemoryManager | None = None
        self.inner_life: InnerLife | None = None
        self.relationship: RelationshipEngine | None = None
        self.first_times: FirstTimeMemory | None = None
        self.scars: ScarManager | None = None
        self.avatar = AvatarController()
        self.embodiment: EmbodimentServer | None = None
        self.tts: TTSProvider | None = create_tts(config)
        self.alive = True
        self.user_online = True
        self.last_interaction = datetime.now()
        self.heartbeat_count = 0
        self._pending_message: str | None = None
        self._heartbeat_lock = asyncio.Lock()
        self._db: Database | None = None
        self._last_response: str | None = None
        self._bg_tasks: list[asyncio.Task] = []
        self._prev_valence = self.emotion.valence
        self._accumulated_suppressed = 0.0
        self.proactive = ProactiveGate(config)
        self.proactive_queue: asyncio.Queue[str] = asyncio.Queue()
        self._drift_signals: list[str] = []
        self._last_avatar_payload: dict | None = None

    def attach_embodiment(self, server: EmbodimentServer) -> None:
        """接上身体——之后说话会推到前端。"""
        self.embodiment = server

    def _current_season(self) -> str:
        if self.relationship is not None:
            return self.relationship.state.season
        return "spring"

    async def _sync_avatar(self, now: datetime | None = None, force: bool = False) -> None:
        now = now or datetime.now()
        state = self.avatar.map_state(
            self.emotion,
            self.emotion.mode.value,
            season=self._current_season(),
            now=now,
        )
        payload = state.to_dict()
        if not force and payload == self._last_avatar_payload:
            return
        self._last_avatar_payload = payload
        if self.embodiment is not None:
            await self.embodiment.broadcast(
                {
                    "type": "state",
                    "payload": {
                        "avatar_state": payload,
                        "season": self._current_season(),
                        "mode": self.emotion.mode.value,
                    },
                }
            )

    async def _emit_speech(self, text: str) -> None:
        if self.embodiment is None:
            return
        await self.embodiment.send_speech(
            text,
            self.emotion.description(),
            tone=self.emotion.mode.value,
        )
        if self.tts is None:
            return
        try:
            import base64

            speed, pitch = emotion_to_voice_params(self.emotion)
            audio = await self.tts.speak(text, speed=speed, pitch=pitch)
            if audio:
                await self.embodiment.send_audio(base64.b64encode(audio).decode("ascii"))
        except Exception:
            logger.exception("TTS 合成失败")

    @property
    def relationship_stage(self) -> str:
        if self.relationship is not None:
            return self.relationship.state.stage
        return "stranger"

    def attach_db(self, db: Database) -> None:
        self._db = db

    def _consume_expression_want(self) -> None:
        self._accumulated_suppressed = 0.0

    async def _push_proactive_text(self, text: str) -> None:
        await self.proactive_queue.put(text)
        await self._emit_speech(text)

    async def start(self) -> None:
        self._bg_tasks = [
            asyncio.create_task(self._background_narrative_weaving()),
            asyncio.create_task(self._background_memory_decay()),
            asyncio.create_task(self._background_self_reflection()),
            asyncio.create_task(self._background_dream_decay()),
            asyncio.create_task(self._background_culture_detection()),
            asyncio.create_task(self._background_season_detection()),
            asyncio.create_task(self._background_scar_healing()),
            asyncio.create_task(self._background_user_drift()),
        ]
        try:
            while self.alive:
                async with self._heartbeat_lock:
                    await self._heartbeat()
                if not self.alive:
                    break
                interval = next_interval(self.emotion, self.config)
                await asyncio.sleep(interval)
        finally:
            for task in self._bg_tasks:
                task.cancel()
            for task in self._bg_tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _apply_anomaly_nudge(self, anomalies: list[str]) -> None:
        if not anomalies:
            return
        self.emotion.curiosity = min(1.0, self.emotion.curiosity + 0.05 * len(anomalies))
        self.emotion.security = max(0.0, self.emotion.security - 0.02 * len(anomalies))

    def _track_expression_threshold(self) -> bool:
        """想主动开口吗？被门控挡住时保留积累，真正开口后再清空。"""
        delta = self.emotion.valence - self._prev_valence
        threshold = float(
            self.config.get("emotion", {}).get("expression_threshold", 0.3)
        )
        want = should_express(
            delta,
            self.relationship_stage,
            self._accumulated_suppressed,
            expression_threshold=threshold,
        )
        if not want:
            self._accumulated_suppressed += abs(delta)
        self._prev_valence = self.emotion.valence
        return want

    async def _gather_prompt_context(
        self,
        pending: str | None,
        now: datetime,
    ) -> tuple[list[dict], list[dict], dict[str, str], str, str, str, str]:
        recent: list[dict] = []
        memories: list[dict] = []
        extras: dict[str, str] = {}

        if self.memory is not None:
            recent = self.memory.working.get_context()
            if (
                pending
                and recent
                and recent[-1].get("role") == "user"
                and recent[-1].get("content") == pending
            ):
                recent = recent[:-1]
            query = pending or "此刻的心情"
            memories = await self.memory.retrieve(query, top_k=3)
        elif self._db is not None:
            recent = await self._db.load_recent_messages(limit=20)
            if (
                pending
                and recent
                and recent[-1].get("role") == "user"
                and recent[-1].get("content") == pending
            ):
                recent = recent[:-1]

        if self.inner_life is not None:
            try:
                extras = await self.inner_life.prompt_extras(
                    self.emotion, self.relationship_stage
                )
            except Exception:
                logger.exception("内在生命 prompt 组装出错")
                extras = {}

        if pending and self.first_times is not None:
            hint = await self.first_times.maybe_recall_hint(pending, now)
            if hint:
                extras["first_time_hint"] = hint

        if self._drift_signals:
            extras["drift_hint"] = "；".join(self._drift_signals)
            self._drift_signals = []

        shared_culture = "（还没有只属于你们的默契）"
        relationship_hint = ""
        scar_hint = ""
        season_hint = ""
        if self.relationship is not None:
            shared_culture = format_culture_for_prompt(
                self.relationship.state.shared_culture
            )
            relationship_hint = self.relationship.stage_prompt_hint()
            season_hint = self.relationship.state.season
        if self.scars is not None and self._db is not None:
            scars = await self._db.list_scars()
            scar_hint = format_scars_for_prompt(scars)

        return (
            recent,
            memories,
            extras,
            shared_culture,
            relationship_hint,
            scar_hint,
            season_hint,
        )

    async def _deliver_qi_message(
        self,
        response: str,
        now: datetime,
        *,
        proactive: bool = False,
    ) -> None:
        self.avatar.set_talking(True)
        await self._sync_avatar(now, force=True)
        if proactive:
            await self._push_proactive_text(response)
        else:
            await self._emit_speech(response)
        self.avatar.set_talking(False)
        await self._sync_avatar(now, force=True)

        if self.memory is not None:
            self.memory.on_qi_message(response)
        if self._db is not None:
            await self._db.save_message(
                "qi",
                response,
                emotion_context=self.emotion.model_dump_json(),
            )

    async def _heartbeat(self) -> str | None:
        self.heartbeat_count += 1
        now = datetime.now()
        self.proactive.reset_day(now)
        response: str | None = None
        pending = self._pending_message
        impact_mult = 1.0
        triggered_first: str | None = None
        silence_before = self.perception.detect_silence(self.last_interaction, now)

        self.emotion.mode = determine_mode(
            self.last_interaction,
            self.user_online,
            now,
            interacting=pending is not None,
        )

        if pending is not None:
            if self.relationship is not None:
                rel = await self.relationship.on_user_message(pending, now)
                if rel.get("stage_changed") and self.inner_life is not None:
                    self.inner_life.self_model.mark_major_event()

            if self.first_times is not None:
                impact_mult, triggered_first = await self.first_times.check(
                    pending,
                    self.emotion,
                    silence_before=silence_before,
                )

            impact = self.perception.assess_impact(
                pending, self.emotion, self.relationship_stage
            )
            impact *= impact_mult
            self.emotion = apply_event_impact(self.emotion, impact)
            self.emotion = self.perception.apply_security_hint(self.emotion, impact)
            self.last_interaction = now

            if self._db is not None:
                await self._db.save_message("user", pending)

            if self.memory is not None:
                anomalies = await self.memory.on_user_message(pending, self.emotion, now)
                self._apply_anomaly_nudge(anomalies)

        decay_mult = float(self.config.get("emotion", {}).get("decay_multiplier", 1.0))
        self.emotion = step_emotion(self.emotion, now, decay_multiplier=decay_mult)
        if self.relationship is not None:
            self.emotion = apply_season_effect(
                self.emotion, self.relationship.state.season
            )
        self.emotion = clamp_emotion(self.emotion)

        want_express = self._track_expression_threshold()

        if self.inner_life is not None and (pending is None or triggered_first):
            try:
                self.emotion = await self.inner_life.tick(
                    self.emotion,
                    self.last_interaction,
                    now,
                    self.relationship_stage,
                    after_first_time=bool(triggered_first),
                )
                self.emotion = clamp_emotion(self.emotion)
            except Exception:
                logger.exception("内在生命 tick 出错")

        if pending is not None:
            (
                recent,
                memories,
                extras,
                shared_culture,
                relationship_hint,
                scar_hint,
                season_hint,
            ) = await self._gather_prompt_context(pending, now)

            self.avatar.set_thinking(True)
            await self._sync_avatar(now, force=True)
            try:
                response = await self.expression.express(
                    user_message=pending,
                    emotion=self.emotion,
                    now=now,
                    recent_messages=recent,
                    memories=memories,
                    inner_extras=extras,
                    relationship_stage=self.relationship_stage,
                    shared_culture=shared_culture,
                    relationship_hint=relationship_hint,
                    scar_hint=scar_hint,
                    season=season_hint,
                )
            finally:
                self.avatar.set_thinking(False)

            self._pending_message = None

            if response:
                await self._deliver_qi_message(response, now, proactive=False)

        elif pending is None:
            silence_seconds = self.perception.detect_silence(self.last_interaction, now)
            kind = pick_proactive_kind(
                want_express=want_express,
                relationship_stage=self.relationship_stage,
                emotion_security=self.emotion.security,
                emotion_attachment=self.emotion.attachment,
                silence_seconds=silence_seconds,
                mode=self.emotion.mode.value,
                user_online=self.user_online,
                gate=self.proactive,
                now=now,
            )
            if kind is not None:
                (
                    recent,
                    memories,
                    extras,
                    shared_culture,
                    relationship_hint,
                    scar_hint,
                    season_hint,
                ) = await self._gather_prompt_context(None, now)
                cue = self.proactive.cue_for(kind)
                self.avatar.set_thinking(True)
                await self._sync_avatar(now, force=True)
                try:
                    response = await self.expression.express(
                        user_message=cue,
                        emotion=self.emotion,
                        now=now,
                        recent_messages=recent,
                        memories=memories,
                        inner_extras=extras,
                        relationship_stage=self.relationship_stage,
                        shared_culture=shared_culture,
                        relationship_hint=relationship_hint,
                        scar_hint=scar_hint,
                        season=season_hint,
                        proactive_kind=kind,
                    )
                finally:
                    self.avatar.set_thinking(False)

                if response:
                    self.proactive.record(kind, now)
                    if kind == "express_feeling":
                        self._consume_expression_want()
                    await self._deliver_qi_message(response, now, proactive=True)
                    await self._persist_proactive_gate()
            elif want_express:
                # 想开口但被门控拦住——把冲动留下来，下一拍还能想起来
                self._accumulated_suppressed = max(self._accumulated_suppressed, 1.01)

        await self._sync_avatar(now)

        if self._db is not None:
            await self._db.save_emotion(self.emotion)

        self._last_response = response
        return response

    async def receive_user_message(self, message: str) -> str | None:
        self._pending_message = message
        async with self._heartbeat_lock:
            return await self._heartbeat()

    async def _background_narrative_weaving(self) -> None:
        interval = float(
            self.config.get("memory", {}).get("narrative_weave_interval", 21600)
        )
        while self.alive:
            await asyncio.sleep(interval)
            if not self.alive or self.memory is None:
                continue
            try:
                if await self.memory.has_unprocessed_events():
                    await self.memory.weave_narrative(
                        self.emotion, self.relationship_stage
                    )
            except Exception:
                logger.exception("叙事编织后台出错")

    async def _background_memory_decay(self) -> None:
        interval = float(self.config.get("memory", {}).get("decay_interval", 86400))
        while self.alive:
            await asyncio.sleep(interval)
            if not self.alive or self.memory is None:
                continue
            try:
                await self.memory.narrative.decay()
            except Exception:
                logger.exception("记忆褪色后台出错")

    async def _background_self_reflection(self) -> None:
        interval = float(
            self.config.get("inner_life", {}).get("self_reflection_interval", 604800)
        )
        await asyncio.sleep(min(60.0, interval))
        while self.alive:
            if self.inner_life is not None:
                try:
                    await self.inner_life.self_model.maybe_reflect(
                        self.emotion, self.relationship_stage
                    )
                except Exception:
                    logger.exception("自我反思后台出错")
            await asyncio.sleep(interval)

    async def _background_dream_decay(self) -> None:
        while self.alive:
            await asyncio.sleep(3600)
            if not self.alive or self.inner_life is None:
                continue
            try:
                await self.inner_life.dreams.decay_all()
            except Exception:
                logger.exception("梦境衰减后台出错")

    async def _background_culture_detection(self) -> None:
        interval = float(
            self.config.get("relationship", {}).get("culture_detection_interval", 86400)
        )
        await asyncio.sleep(min(120.0, interval))
        while self.alive:
            if self.relationship is not None and self._db is not None:
                try:
                    msgs = await self._db.load_recent_messages(limit=200)
                    culture = detect_shared_culture(
                        msgs, self.relationship.state.shared_culture
                    )
                    self.relationship.state.shared_culture = culture
                    await self.relationship.persist()
                except Exception:
                    logger.exception("共同文化检测出错")
            await asyncio.sleep(interval)

    async def _background_season_detection(self) -> None:
        interval = float(
            self.config.get("relationship", {}).get("season_detection_interval", 86400)
        )
        await asyncio.sleep(min(180.0, interval))
        while self.alive:
            if self.relationship is not None and self._db is not None:
                try:
                    history = await self._db.load_recent_emotions(limit=30)
                    old = self.relationship.state.season
                    new = determine_season(history)
                    if new != old:
                        self.relationship.state.season = new
                        await self.relationship.persist()
                        if self.inner_life is not None:
                            await self._db.save_consciousness(
                                content=f"季节变了。从{old}到了{new}。",
                                stream_type="stream",
                                trigger="season_change",
                            )
                except Exception:
                    logger.exception("季节判定出错")
            await asyncio.sleep(interval)

    async def _background_scar_healing(self) -> None:
        interval = float(
            self.config.get("relationship", {}).get("scar_healing_interval", 86400)
        )
        await asyncio.sleep(min(240.0, interval))
        while self.alive:
            if self.scars is not None and self.relationship is not None:
                try:
                    healed = await self.scars.check_healing(self.relationship.state.trust)
                    if healed:
                        await self.relationship.on_scar_healed()
                except Exception:
                    logger.exception("伤疤愈合检查出错")
            await asyncio.sleep(interval)

    async def _background_user_drift(self) -> None:
        interval = float(
            self.config.get("relationship", {}).get("drift_detection_interval", 259200)
        )
        await asyncio.sleep(min(300.0, interval))
        while self.alive:
            if self._db is not None:
                try:
                    model = await self._db.load_user_model() or {}
                    msgs = await self._db.load_recent_messages(limit=100)
                    signals = detect_user_drift(model, msgs)
                    updated = build_updated_user_model(msgs, signals)
                    await self._db.save_user_model(**updated)
                    if signals:
                        self._drift_signals = signals
                        await self._db.save_consciousness(
                            content=f"我注意到他最近变了：{'；'.join(signals)}。不是不好。是……不一样了。",
                            stream_type="stream",
                            trigger="user_drift",
                        )
                except Exception:
                    logger.exception("用户漂移检测出错")
            await asyncio.sleep(interval)

    async def _persist_proactive_gate(self) -> None:
        if self._db is None:
            return
        try:
            await self._db.set_body_memory("proactive_gate", self.proactive.snapshot())
        except Exception:
            logger.exception("主动门控持久化失败")

    async def restore_state(self, db: Database) -> None:
        self._db = db
        self.memory = MemoryManager(db, self.config, llm=self.llm)
        self.inner_life = InnerLife(db, self.llm, self.config)
        self.relationship = RelationshipEngine(db, self.llm, self.config)
        self.first_times = FirstTimeMemory(db, self.llm)
        self.scars = ScarManager(db, self.llm)
        await self.memory.restore()
        await self.relationship.restore()
        self.perception.relationship_stage = self.relationship.state.stage
        saved_gate = await db.get_body_memory("proactive_gate")
        if isinstance(saved_gate, dict):
            self.proactive.restore(saved_gate)
        saved = await db.load_emotion()
        if saved is not None:
            self.emotion = saved
            self._prev_valence = saved.valence
            if self.inner_life:
                self.inner_life._prev_valence = saved.valence
                self.inner_life._prev_arousal = saved.arousal
            logger.info("恢复情绪：%s", self.emotion.description())

    async def save_state(self, db: Database) -> None:
        await db.save_emotion(self.emotion)
        await self._persist_proactive_gate()
        if self.relationship is not None:
            await self.relationship.persist()
