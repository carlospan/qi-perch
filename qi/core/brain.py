"""Brain Loop——栖的心脏。"""

from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from qi.action import ActionLayer
from qi.core import brain_background as _brain_background
from qi.core import brain_context as _brain_context
from qi.core import brain_delivery as _brain_delivery
from qi.core import brain_persist as _brain_persist
from qi.core import brain_trace as _brain_trace
from qi.core.brain_background import BackgroundTasks
from qi.core.brain_types import (
    EMOTION_SAVE_MIN_INTERVAL as EMOTION_SAVE_MIN_INTERVAL,
)
from qi.core.brain_types import (
    PENDING_QUEUE_MAX,
    PromptContext,
    _PendingSpeech,
)
from qi.core.brain_types import (
    SEASON_EMOTION_HOURS as SEASON_EMOTION_HOURS,
)
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
from qi.embodiment.voice.tts import create_tts
from qi.inner_life import InnerLife
from qi.memory.first_time import FirstTimeMemory
from qi.memory.manager import MemoryManager
from qi.relationship import RelationshipEngine
from qi.relationship.scars import ScarManager
from qi.relationship.season import apply_season_effect

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
        self.perception = Perception(config, llm=llm)
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
        # 本进程会话内是否已有过真实交谈——冷启动后的第一句话不构成「共同沉默」
        self._interacted_this_session = False
        self.heartbeat_count = 0
        self._pending_queue: deque[str] = deque(maxlen=PENDING_QUEUE_MAX)
        self._pending_speech: _PendingSpeech | None = None
        self._last_emotion_saved_at: datetime | None = None
        self._heartbeat_lock = asyncio.Lock()
        self._db: Database | None = None
        self._last_response: str | None = None
        self._background = BackgroundTasks(self)
        self._prev_valence = self.emotion.valence
        self._accumulated_suppressed = 0.0
        self.proactive = ProactiveGate(config)
        self.proactive_queue: asyncio.Queue[str] = asyncio.Queue()
        self.action: ActionLayer | None = None
        self._drift_signals: list[str] = []
        self._last_avatar_payload: dict | None = None
        self._traces: deque[dict] = deque(maxlen=20)
        self._trace_day: str | None = None

    def attach_embodiment(self, server: EmbodimentServer) -> None:
        """接上身体——之后说话会推到前端。"""
        self.embodiment = server

    def _current_season(self) -> str:
        if self.relationship is not None:
            return self.relationship.state.season
        return "spring"

    async def _sync_avatar(self, now: datetime | None = None, force: bool = False) -> None:
        await _brain_delivery.sync_avatar(self, now, force)

    async def _emit_speech(self, text: str) -> None:
        await _brain_delivery.emit_speech(self, text)

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
        await _brain_delivery.push_proactive_text(self, text)

    async def start(self) -> None:
        self._background.start()
        try:
            while self.alive:
                async with self._heartbeat_lock:
                    await self._heartbeat()
                    speech = self._take_pending_speech()
                if speech is not None:
                    # 主动开口：出锁后推送，不再人工停顿（用户回复才「想了想」）
                    await self._deliver_qi_message(
                        speech.text, speech.now, proactive=speech.proactive
                    )
                if not self.alive:
                    break
                interval = next_interval(self.emotion, self.config)
                await asyncio.sleep(interval)
        finally:
            await self._background.stop()

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
    ) -> PromptContext:
        return await _brain_context.gather_prompt_context(self, pending, now)

    async def _deliver_qi_message(
        self,
        response: str,
        now: datetime,
        *,
        proactive: bool = False,
    ) -> None:
        await _brain_delivery.deliver_qi_message(
            self, response, now, proactive=proactive
        )

    async def _heartbeat(self) -> str | None:
        self.heartbeat_count += 1
        now = datetime.now()
        self.proactive.reset_day(now)
        response: str | None = None
        pending = self._pending_queue.popleft() if self._pending_queue else None
        impact_mult = 1.0
        triggered_first: str | None = None
        impact: float | None = None
        kind: str | None = None
        action_type: str | None = None
        silence_before = self.perception.detect_silence(self.last_interaction, now)

        self.emotion.mode = determine_mode(
            self.last_interaction,
            self.user_online,
            now,
            interacting=pending is not None,
        )

        if pending is not None:
            # 感知先于关系：同一拍 intent 供 trust/伤疤复用（阶段零·包 A）
            recent_for_impact: list[dict] = []
            if self.memory is not None:
                recent_for_impact = self.memory.working.get_context()
            elif self._db is not None:
                recent_for_impact = await self._db.load_recent_messages(limit=5)

            impact = await self.perception.assess_impact_async(
                pending,
                self.emotion,
                self.relationship_stage,
                recent_messages=recent_for_impact,
            )

            if self.relationship is not None:
                rel = await self.relationship.on_user_message(
                    pending,
                    now,
                    assessment=self.perception.last_assessment,
                )
                if rel.get("stage_changed") and self.inner_life is not None:
                    self.inner_life.self_model.mark_major_event()

            if self.first_times is not None:
                impact_mult, triggered_first = await self.first_times.check(
                    pending,
                    self.emotion,
                    silence_before=silence_before
                    if self._interacted_this_session
                    else None,
                )

            if self.memory is not None:
                await self.memory.notice_facts(
                    pending,
                    self.emotion,
                    self.relationship_stage,
                    now,
                )

            impact = impact * impact_mult
            self.emotion = apply_event_impact(self.emotion, impact)
            self.emotion = self.perception.apply_security_hint(self.emotion, impact)
            self.last_interaction = now
            self._interacted_this_session = True

            if self._db is not None:
                await self._db.save_message("user", pending)

            if self.memory is not None:
                anomalies = await self.memory.on_user_message(pending, self.emotion, now)
                self._apply_anomaly_nudge(anomalies)

        decay_mult = float(self.config.get("emotion", {}).get("decay_multiplier", 1.0))
        self.emotion = step_emotion(
            self.emotion,
            now,
            decay_multiplier=decay_mult,
            relationship_stage=self.relationship_stage,
        )
        if self.relationship is not None:
            self.emotion = apply_season_effect(
                self.emotion, self.relationship.state.season
            )
        self.emotion = clamp_emotion(self.emotion)

        want_express = self._track_expression_threshold()

        # 无用户句时照常跑内在生命；有 first_time 时把意识流放到回复之后，
        # 避免同拍独白经 recent_thoughts 启动效应，把意象投射成「对方说的」。
        if self.inner_life is not None and pending is None:
            try:
                self.emotion = await self.inner_life.tick(
                    self.emotion,
                    self.last_interaction,
                    now,
                    self.relationship_stage,
                    after_first_time=False,
                )
                self.emotion = clamp_emotion(self.emotion)
                await self._broadcast_journal_entries()
            except Exception:
                logger.exception("内在生命 tick 出错")

        if pending is not None:
            ctx = await self._gather_prompt_context(pending, now)

            self.avatar.set_thinking(True)
            await self._sync_avatar(now, force=True)
            try:
                response = await self.expression.express(
                    user_message=pending,
                    emotion=self.emotion,
                    now=now,
                    recent_messages=ctx.recent_messages,
                    memories=ctx.retrieved_memories,
                    inner_extras=ctx.extras,
                    relationship_stage=self.relationship_stage,
                    shared_culture=ctx.shared_culture,
                    relationship_hint=ctx.relationship_hint,
                    scar_hint=ctx.scar_hint,
                    season=ctx.season_hint,
                )
            finally:
                self.avatar.set_thinking(False)

            if response:
                self._pending_speech = _PendingSpeech(
                    text=response, now=now, proactive=False
                )
            else:
                # 对话路径保持静默（任务包 C：只做主动开口兜底）
                failure = getattr(
                    getattr(self.llm, "last_outcome", None), "failure", None
                )
                logger.warning(
                    "对话表达返回空串 failure=%s，本轮不说话"
                    "（检查 API 密钥/网络/provider）",
                    failure,
                )

            # 第一次之后再想一次：在开口之后写意识流，供「忆」与下一轮，不污染本轮回复
            if self.inner_life is not None and triggered_first:
                try:
                    self.emotion = await self.inner_life.tick(
                        self.emotion,
                        self.last_interaction,
                        now,
                        self.relationship_stage,
                        after_first_time=True,
                    )
                    self.emotion = clamp_emotion(self.emotion)
                    await self._broadcast_journal_entries()
                except Exception:
                    logger.exception("第一次后意识流 tick 出错")

        elif pending is None:
            silence_seconds = self.perception.detect_silence(self.last_interaction, now)
            # 行动与主动言语同拍不叠加：先评估自主行动（更稀有）；
            # 动了手则不再 pick_proactive_kind；没动手再 fall through 到主动言语。
            acted = False
            if self.action is not None:
                try:
                    scars = (
                        await self._db.list_scars()
                        if self._db is not None
                        else None
                    )
                    action_result = await self.action.tick(
                        self.emotion,
                        self.relationship_stage,
                        self._current_season(),
                        now,
                        mode=self.emotion.mode.value,
                        user_online=self.user_online,
                        scars=scars,
                    )
                    if action_result is not None:
                        acted = True
                        action_type = (
                            str(action_result.get("type") or action_result.get("kind") or "")
                            or None
                        )
                        await self._persist_action_budget()
                        await self._deliver_action_result(action_result, now)
                except Exception:
                    logger.exception("行动层 tick 出错")

            if not acted:
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
                ctx = await self._gather_prompt_context(None, now)
                cue = self.proactive.cue_for(kind)
                self.avatar.set_thinking(True)
                await self._sync_avatar(now, force=True)
                try:
                    response = await self.expression.express(
                        user_message=cue,
                        emotion=self.emotion,
                        now=now,
                        recent_messages=ctx.recent_messages,
                        memories=ctx.retrieved_memories,
                        inner_extras=ctx.extras,
                        relationship_stage=self.relationship_stage,
                        shared_culture=ctx.shared_culture,
                        relationship_hint=ctx.relationship_hint,
                        scar_hint=ctx.scar_hint,
                        season=ctx.season_hint,
                        proactive_kind=kind,
                    )
                finally:
                    self.avatar.set_thinking(False)

                failure = getattr(
                    getattr(self.llm, "last_outcome", None), "failure", None
                )
                if response:
                    self.proactive.record(kind, now)
                    if kind == "express_feeling":
                        self._consume_expression_want()
                    self._pending_speech = _PendingSpeech(
                        text=response, now=now, proactive=True
                    )
                    await self._persist_proactive_gate()
                elif failure == "unreachable":
                    # 拔管：本地短句兜底，仍计入主动日限——它还在，只是嘴暂时笨了
                    text = self.proactive.fallback_line(kind)
                    self.proactive.record(kind, now)
                    if kind == "express_feeling":
                        self._consume_expression_want()
                    self._pending_speech = _PendingSpeech(
                        text=text, now=now, proactive=True
                    )
                    await self._persist_proactive_gate()
                    logger.warning(
                        "主动表达 LLM 不可达，改用本地兜底 kind=%s", kind
                    )
                else:
                    # empty 或其他：静默，不 record（不占日限）
                    logger.warning(
                        "主动表达返回空串 kind=%s failure=%s"
                        "（检查 API 密钥/网络/provider）",
                        kind,
                        failure,
                    )
            elif want_express:
                # 想开口但被门控拦住——把冲动留下来，下一拍还能想起来
                self._accumulated_suppressed = max(self._accumulated_suppressed, 1.01)

        await self._sync_avatar(now)

        if triggered_first:
            await self._notify_first_time()

        await self._record_trace(
            pending=pending,
            want_express=want_express,
            kind=kind,
            action_type=action_type,
            impact=impact,
            now=now,
        )

        if self._db is not None:
            await self._maybe_save_emotion(now, force=pending is not None)

        self._last_response = response
        return response

    async def _record_trace(
        self,
        *,
        pending: str | None,
        want_express: bool,
        kind: str | None,
        action_type: str | None,
        impact: float | None,
        now: datetime,
    ) -> None:
        """心跳决策痕迹——给人排障，不进 prompt。"""
        await _brain_trace.record_trace(
            self,
            pending=pending,
            want_express=want_express,
            kind=kind,
            action_type=action_type,
            impact=impact,
            now=now,
        )

    async def format_why(self, limit: int = 8) -> str:
        """格式化最近心跳痕迹，供 CLI /why。"""
        return await _brain_trace.format_why(self, limit=limit)

    async def _broadcast_journal_entries(self) -> None:
        await _brain_delivery.broadcast_journal_entries(self)

    async def _notify_first_time(self) -> None:
        await _brain_delivery.notify_first_time(self)

    def _take_pending_speech(self) -> _PendingSpeech | None:
        speech = self._pending_speech
        self._pending_speech = None
        return speech

    async def _maybe_save_emotion(self, now: datetime, *, force: bool = False) -> None:
        """空心跳节流落盘；有用户消息或强制时立即写。"""
        await _brain_persist.maybe_save_emotion(self, now, force=force)

    async def receive_user_message(self, message: str) -> str | None:
        text = (message or "").strip()
        if not text:
            return None
        async with self._heartbeat_lock:
            if len(self._pending_queue) >= PENDING_QUEUE_MAX:
                dropped = self._pending_queue.popleft()
                logger.warning(
                    "待处理消息队列已满，丢弃最早一条: %s",
                    dropped[:40],
                )
            self._pending_queue.append(text)
            await self._heartbeat()
            speech = self._take_pending_speech()
        if speech is None:
            return None
        # 生成已在锁内完成；出锁后再「想了想」，再推送——不堵心跳
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self._deliver_qi_message(
            speech.text, speech.now, proactive=speech.proactive
        )
        return speech.text

    async def _background_narrative_weaving(self) -> None:
        await _brain_background.narrative_weaving(self)

    async def _pending_event_count(self) -> int:
        return await _brain_background.pending_event_count(self)

    async def _background_memory_decay(self) -> None:
        await _brain_background.memory_decay(self)

    async def _background_self_reflection(self) -> None:
        """
        定期询问是否该反思。门控在 should_reflect（周间隔 / 重大事件标志），
        这里用短轮询，避免 mark_major_event 后要等将近一周才轮到。
        """
        await _brain_background.self_reflection(self)

    async def _background_dream_decay(self) -> None:
        await _brain_background.dream_decay(self)

    async def _resume_interval_wait(
        self, key: str, interval: float, default_first: float
    ) -> float:
        """检测类后台任务的首次等待：距上次检测不足周期则补足。

        重启不重置检测节奏——频繁重启时短首跑延迟会把「每天/每三天一轮」
        变成「每次重启一轮」，小样本误报被反复制造（实证：漂移/文化误报）。
        与 proactive gate、depth 日帽同构，落 body_memory。
        """
        return await _brain_background.resume_interval_wait(
            self, key, interval, default_first
        )

    async def _mark_interval_done(self, key: str) -> None:
        await _brain_background.mark_interval_done(self, key)

    async def _background_culture_detection(self) -> None:
        await _brain_background.culture_detection(self)

    async def _background_season_detection(self) -> None:
        await _brain_background.season_detection(self)

    async def _background_scar_healing(self) -> None:
        await _brain_background.scar_healing(self)

    async def _background_user_drift(self) -> None:
        await _brain_background.user_drift(self)

    async def _persist_proactive_gate(self) -> None:
        await _brain_persist.persist_proactive_gate(self)

    async def _persist_action_budget(self) -> None:
        await _brain_persist.persist_action_budget(self)

    async def _deliver_action_result(
        self, result: dict, now: datetime
    ) -> None:
        """行动结果：卡片推前端；share 的 qi_line 作为这一拍的开口（非主动言语通道）。"""
        await _brain_delivery.deliver_action_result(self, result, now)

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
        # L7：叙事注入 ShareAction；预算从 body_memory 恢复
        self.action = ActionLayer(
            db, self.config, narrative=self.memory.narrative
        )
        await self.action.restore_budget()
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
        # 醒来回溯：如果上次对话有实质内容，标记重启后第一拍触发意识流
        await self._maybe_mark_waking(db)

    async def _maybe_mark_waking(self, db: Database) -> None:
        """重启后检测上次对话是否有深度，有则标记 waking 意识流。"""
        if self.inner_life is None:
            return
        from qi.inner_life.consciousness import is_trivial_utterance

        recent = await db.load_recent_messages(limit=6)
        if not recent:
            return
        last_user = next(
            (m for m in reversed(recent) if m.get("role") == "user"), None
        )
        if last_user is None:
            return
        text = (last_user.get("content") or "").strip()
        # 纯寒暄不触发；有实质内容才「醒来后想一想」（停机期间并未在想）
        if is_trivial_utterance(text):
            return
        self.inner_life.mark_waking()
        logger.info("标记醒来回溯：上次对话有实质内容")

    async def save_state(self, db: Database) -> None:
        await db.save_emotion(self.emotion)
        self._last_emotion_saved_at = datetime.now()
        await self._persist_proactive_gate()
        await self._persist_action_budget()
        if self.relationship is not None:
            await self.relationship.persist()
