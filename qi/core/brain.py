"""Brain Loop——栖的心脏。"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
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
    MAJOR_COMMITMENT_DAILY_CAP,
    MAJOR_COMMITMENT_GATE_KEY,
    EmotionState,
    apply_event_impact,
    apply_relationship_emotion_nudge,
    clamp_emotion,
    is_major_commitment_signal,
    should_express,
    step_emotion,
)
from qi.core.expression import Expression
from qi.core.intention import LAST_INTENTION_KEY, build_intention_card
from qi.core.perception import Perception
from qi.core.proactive import ProactiveGate, pick_proactive_kind
from qi.core.rhythm import determine_mode, next_interval
from qi.embodiment.avatar.controller import AvatarController
from qi.embodiment.voice.tts import create_tts
from qi.inner_life import InnerLife
from qi.memory.first_time import FirstTimeMemory
from qi.memory.manager import MemoryManager
from qi.memory.open_loops import OpenLoopQueue
from qi.relationship import RelationshipEngine
from qi.relationship.scars import ScarManager
from qi.relationship.season import apply_season_effect
from qi.stasis.ledger import (
    ATTEMPT_TOKEN_COST,
    EFFECTIVE_INTERACTION_AMOUNT,
    MEM_RETRIEVAL_TOKEN_COST,
    ONLINE_PRESENCE_AMOUNT,
    ONLINE_PRESENCE_MIN_INTERVAL_SEC,
    STORAGE_ESTIMATE_EVERY_N_BEATS,
    ResourceLedger,
)
from qi.stasis.ledger import (
    BODY_MEMORY_KEY as LEDGER_BODY_KEY,
)
from qi.stasis.pressure import STARVE_BEATS as DEFAULT_STARVE_BEATS
from qi.world import WorldModel

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
        self._gws_broadcast_hint: dict | None = None
        self._prev_valence = self.emotion.valence
        self._accumulated_suppressed = 0.0
        self.proactive = ProactiveGate(config)
        self.proactive_queue: asyncio.Queue[str] = asyncio.Queue()
        # ActionBudget 日限 = 安全阀，不计入 C2 账本余额；两者并存，职责分离
        self.action: ActionLayer | None = None
        self.ledger = ResourceLedger()  # N0 资源账本（包 12）；压力动力学归包 13
        self.last_pressure_response = None  # PressureResponse | None（N3：供 explore 软调制）
        self.last_sensing = None  # SensingSnapshot | None（包 8）
        self.last_user_message: str | None = None  # assist-2：供 trace / 感知
        self.last_assist_request = None  # AssistRequest | None（assist-2）
        # assist-3 / open：跨轮确认（仅内存；AssistRequest | OpenRequest）
        self.pending_assist_confirmation = None  # AssistRequest | OpenRequest | None
        self.pending_assist_confirmation_at: datetime | None = None
        self.pending_assist_heartbeats: int = 0
        # assist-5：粘性目标（确认成功后保留，供口头补执行）
        self.last_assist_target: str | None = None
        self.last_assist_target_at: datetime | None = None
        self.world = WorldModel()
        self.last_world = None  # dict | None（包 9：世界模型旁路快照）
        # 包 14：优雅停钩子（库内不 sys.exit；CLI 可注入）
        self.on_halt: Callable[[], None] | None = None
        from qi.stasis.checkpoint import default_checkpoint_dir

        self.checkpoint_dir: Path = default_checkpoint_dir()
        # 蛰伏（STASIS）：断粮后停主心跳；通道可留，但拒绝业务对话（第 1 批）
        self.in_stasis: bool = False
        self._stasis_checkpoint_written: bool = False
        self._stasis_wake: asyncio.Event | None = None
        self._drift_signals: list[str] = []
        self._last_avatar_payload: dict | None = None
        self._last_state_packet: dict | None = None
        self._traces: deque[dict] = deque(maxlen=20)
        self._trace_day: str | None = None
        # 本会话首条用户消息：deliver 之后 prefer_close open loop（不污染当轮）
        self._prefer_close_after_deliver = False

    # 蛰伏时对用户的固定提示（非 LLM；唤醒走控制面）
    STASIS_USER_NOTICE = "……我先封存休息了。等你唤醒我。"
    STASIS_WAKE_NOTICE = "……嗯。我回来了。"
    # 唤醒后赠予的滚动余额下限，避免瞬间再次断粮（滞回）
    STASIS_WAKE_BALANCE_FLOOR = 10.0

    def public_mode(self) -> str:
        """前端可见模式：蛰伏时覆盖 emotion.mode，避免假「醒着」。"""
        if self.in_stasis:
            return "stasis"
        return self.emotion.mode.value

    def _wake_event(self) -> asyncio.Event:
        if self._stasis_wake is None:
            self._stasis_wake = asyncio.Event()
        return self._stasis_wake

    def request_shutdown(self) -> None:
        """进程收尾：结束蛰伏等候并退出 start()。"""
        self.alive = False
        self.in_stasis = False
        self._wake_event().set()

    async def start(self) -> None:
        """主循环；蛰伏时停代谢并原地等候唤醒（不退出任务）。"""
        try:
            while True:
                if self.in_stasis and not self.alive:
                    await self._park_stasis()
                    if not self.alive:
                        break
                    continue

                self._background.start()
                try:
                    while self.alive:
                        async with self._heartbeat_lock:
                            await self._heartbeat()
                            speech = self._take_pending_speech()
                        if speech is not None:
                            await self._deliver_qi_message(
                                speech.text,
                                speech.now,
                                proactive=speech.proactive,
                            )
                            await self._maybe_prefer_close_after_deliver()
                        if not self.alive:
                            break
                        interval = next_interval(self.emotion, self.config)
                        await asyncio.sleep(interval)
                finally:
                    await self._background.stop()

                if self.in_stasis:
                    await self._park_stasis()
                    if not self.alive:
                        break
                    continue
                break
        finally:
            await self._background.stop()
            if self.on_halt is not None:
                try:
                    self.on_halt()
                except Exception:
                    logger.debug("on_halt 回调失败", exc_info=True)

    async def _park_stasis(self) -> None:
        """蛰伏等候：不跑后台代谢，直到 resume / shutdown。"""
        logger.info("蛰伏中，等候唤醒")
        ev = self._wake_event()
        ev.clear()
        await ev.wait()

    async def resume_from_stasis(self) -> dict:
        """控制面唤醒：清断粮标记、滞回余额、重启主循环。"""
        if not self.in_stasis:
            return {"ok": False, "reason": "not_in_stasis"}

        from qi.stasis.pressure import reset_low_balance_streak

        now = datetime.now()
        reset_low_balance_streak()
        self.ledger.starving = False
        try:
            stasis_cfg = self.config.get("stasis") or {}
            amount = float(
                stasis_cfg.get("presence_income", ONLINE_PRESENCE_AMOUNT)
            )
            self.ledger.credit_income(
                "online_presence", amount=amount, now=now
            )
        except Exception:
            logger.debug("唤醒在场收入失败", exc_info=True)
        if self.ledger.balance <= 0:
            self.ledger.force_balance(self.STASIS_WAKE_BALANCE_FLOOR)

        self.in_stasis = False
        self._stasis_checkpoint_written = False
        self.alive = True
        # 空闲起步 → ambient，避免冻在 awake
        self.last_interaction = now - timedelta(seconds=60)
        self.emotion.mode = determine_mode(
            self.last_interaction,
            self.user_online,
            now,
            interacting=False,
        )

        if self._db is not None:
            try:
                await self._db.set_body_memory(
                    LEDGER_BODY_KEY, self.ledger.snapshot()
                )
            except Exception:
                logger.debug("唤醒后账本持久化失败", exc_info=True)

        try:
            await self._sync_avatar(now, force=True)
        except Exception:
            logger.debug("唤醒状态推送失败", exc_info=True)
        try:
            await self._emit_speech(self.STASIS_WAKE_NOTICE)
        except Exception:
            logger.debug("唤醒提示推送失败", exc_info=True)

        self._wake_event().set()
        logger.info("已从蛰伏唤醒 mode=%s", self.public_mode())
        return {"ok": True, "mode": self.public_mode()}

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

    def _apply_anomaly_nudge(self, anomalies: list[str]) -> None:
        if not anomalies:
            return
        self.emotion.curiosity = min(1.0, self.emotion.curiosity + 0.05 * len(anomalies))
        self.emotion.security = max(0.0, self.emotion.security - 0.02 * len(anomalies))

    async def _consume_major_commitment_quota(self, now: datetime) -> bool:
        """大承诺 nudge 日帽 ≤2；body_memory 跨重启不刷新。"""
        if self._db is None:
            return True
        day = now.strftime("%Y-%m-%d")
        gate = await self._db.get_body_memory(MAJOR_COMMITMENT_GATE_KEY)
        if not isinstance(gate, dict) or gate.get("day") != day:
            gate = {"day": day, "count": 0}
        try:
            count = int(gate.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count >= MAJOR_COMMITMENT_DAILY_CAP:
            return False
        gate["count"] = count + 1
        await self._db.set_body_memory(MAJOR_COMMITMENT_GATE_KEY, gate)
        return True

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

    async def _load_open_loops(self) -> list[dict]:
        if self._db is None:
            return []
        try:
            q = OpenLoopQueue(self._db)
            await q.load()
            return q.items()
        except Exception:
            logger.debug("读取 open loops 失败", exc_info=True)
            return []

    async def _persist_intention(self, card) -> None:
        if self._db is None:
            return
        try:
            await self._db.set_body_memory(LAST_INTENTION_KEY, card.to_dict())
        except Exception:
            logger.debug("写入 last_intention 失败", exc_info=True)

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

    async def _maybe_prefer_close_after_deliver(self) -> None:
        """对话首轮 deliver 之后再闭 loop——严禁污染当轮 prompt。"""
        if not self._prefer_close_after_deliver:
            return
        self._prefer_close_after_deliver = False
        if self.inner_life is None:
            return
        try:
            now = datetime.now()
            self.emotion = await self.inner_life.tick(
                self.emotion,
                self.last_interaction,
                now,
                self.relationship_stage,
                prefer_close_loop=True,
            )
            self.emotion = clamp_emotion(self.emotion)
            await self._broadcast_journal_entries()
        except Exception:
            logger.exception("对话首轮 prefer_close 出错")

    def _ledger_token_cost_for_text(self, text: str | None) -> int:
        if text and str(text).strip():
            return max(1, len(str(text)) // 4)
        return ATTEMPT_TOKEN_COST

    def _ledger_safe_add_tokens(self, n: int) -> None:
        try:
            self.ledger.add_token_cost(int(n))
        except Exception:
            logger.debug("账本 token 记账失败", exc_info=True)

    def _ledger_safe_credit_interaction(self, now: datetime) -> None:
        try:
            stasis_cfg = self.config.get("stasis") or {}
            amount = float(
                stasis_cfg.get("interaction_income", EFFECTIVE_INTERACTION_AMOUNT)
            )
            self.ledger.credit_income(
                "effective_interaction", amount=amount, now=now
            )
        except Exception:
            logger.debug("账本收入记账失败", exc_info=True)

    def _ledger_safe_credit_presence(self, now: datetime) -> None:
        """窗口在线时的钝感在场收入（白名单 online_presence）。"""
        if not self.user_online or self.in_stasis:
            return
        try:
            stasis_cfg = self.config.get("stasis") or {}
            amount = float(
                stasis_cfg.get("presence_income", ONLINE_PRESENCE_AMOUNT)
            )
            interval = float(
                stasis_cfg.get(
                    "presence_min_interval_sec", ONLINE_PRESENCE_MIN_INTERVAL_SEC
                )
            )
            self.ledger.credit_income(
                "online_presence",
                amount=amount,
                now=now,
                min_interval_sec=interval,
            )
        except Exception:
            logger.debug("在场收入记账失败", exc_info=True)

    def _ledger_maybe_estimate_storage(self) -> None:
        try:
            if self.heartbeat_count % STORAGE_ESTIMATE_EVERY_N_BEATS != 0:
                return
            if self._db is None:
                return
            path = Path(getattr(self._db, "db_path", "") or "")
            if path.is_file():
                self.ledger.estimate_storage(path.stat().st_size)
        except Exception:
            logger.debug("账本 storage 估算失败", exc_info=True)

    async def _heartbeat(self) -> str | None:
        t0 = time.perf_counter()
        self.heartbeat_count += 1
        from qi.inner_life.identity_snapshot import note_snapshot_beat
        from qi.sensing import collect as collect_sensing

        note_snapshot_beat()
        now = datetime.now()
        # assist-3：pending 超时清理（5 分钟或 3 轮心跳，取先到）
        if self.pending_assist_confirmation is not None:
            self.pending_assist_heartbeats += 1
            timed_out = False
            if self.pending_assist_confirmation_at is not None:
                elapsed = (
                    now - self.pending_assist_confirmation_at
                ).total_seconds()
                if elapsed > 300:
                    timed_out = True
            if timed_out or self.pending_assist_heartbeats >= 3:
                self.pending_assist_confirmation = None
                self.pending_assist_confirmation_at = None
                self.pending_assist_heartbeats = 0
                self.last_assist_target = None
                self.last_assist_target_at = None
        try:
            self.ledger.tick_window(self.heartbeat_count)
        except Exception:
            logger.debug("账本窗口推进失败", exc_info=True)
        try:
            self.last_sensing = collect_sensing(
                heartbeat_count=self.heartbeat_count, now=now
            )
        except Exception:
            logger.debug("传感采集失败", exc_info=True)
            self.last_sensing = None
        # 包 9：世界模型只增旁路信号，不接 GWS / 不改 proactive 权重
        try:
            await self.world.update(self, now=now)
            self.last_world = self.world.snapshot(now=now)
        except Exception:
            logger.debug("世界模型更新失败", exc_info=True)
            self.last_world = None
        self.proactive.reset_day(now)
        self._gws_broadcast_hint = None
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
            # 包 12：有效交互收入（R3：非满意度）；防刷在 ledger 内
            self._ledger_safe_credit_interaction(now)
            # 感知先于关系：同一拍 intent 供 trust/伤疤复用（阶段零·包 A）
            recent_for_impact: list[dict] = []
            if self.memory is not None:
                recent_for_impact = self.memory.working.get_context()
                self._ledger_safe_add_tokens(MEM_RETRIEVAL_TOKEN_COST)
            elif self._db is not None:
                recent_for_impact = await self._db.load_recent_messages(limit=5)
                self._ledger_safe_add_tokens(MEM_RETRIEVAL_TOKEN_COST)

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
                    await self.inner_life.self_model.mark_major_event()
                allow_commitment = True
                if (
                    not rel.get("stage_changed")
                    and is_major_commitment_signal(rel.get("signals"))
                ):
                    allow_commitment = await self._consume_major_commitment_quota(
                        now
                    )
                self.emotion = apply_relationship_emotion_nudge(
                    self.emotion,
                    rel,
                    allow_commitment=allow_commitment,
                )

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
            # 本会话首条：deliver 后再 prefer_close（见 start / receive_user_message）
            if not self._interacted_this_session:
                self._prefer_close_after_deliver = True
            self._interacted_this_session = True

            if self._db is not None:
                await self._db.save_message("user", pending)

            if self.memory is not None:
                anomalies = await self.memory.on_user_message(pending, self.emotion, now)
                self._apply_anomaly_nudge(anomalies)

        decay_mult = float(self.config.get("emotion", {}).get("decay_multiplier", 1.0))
        # 包 13：账本余额 → energy 目标偏移（趋近，不盖写）
        energy_offset = 0.0
        try:
            from qi.stasis.pressure import balance_to_energy_offset

            sens = float(
                (self.config.get("stasis") or {}).get("pressure_sensitivity", 1.0)
            )
            energy_offset = balance_to_energy_offset(
                self.ledger.balance, sensitivity=sens
            )
        except Exception:
            logger.debug("账本→energy 偏移计算失败", exc_info=True)
        self.emotion = step_emotion(
            self.emotion,
            now,
            decay_multiplier=decay_mult,
            relationship_stage=self.relationship_stage,
            energy_baseline_offset=energy_offset,
        )
        if self.relationship is not None:
            self.emotion = apply_season_effect(
                self.emotion, self.relationship.state.season
            )
        self.emotion = clamp_emotion(self.emotion)

        # 包 13：分层应对 + starving 标记（不 exit、不写 checkpoint）
        try:
            from qi.stasis.pressure import compute_pressure, maybe_mark_starving

            sens = float(
                (self.config.get("stasis") or {}).get("pressure_sensitivity", 1.0)
            )
            starve_beats = int(
                (self.config.get("stasis") or {}).get(
                    "starve_beats", DEFAULT_STARVE_BEATS
                )
            )
            resp = compute_pressure(
                self.ledger, self.emotion, sensitivity=sens
            )
            self.last_pressure_response = resp  # N3：供 ActionLayer / volition 读
            if resp.throttle > 0.3:
                logger.debug(
                    "内稳态节流倾向 throttle=%.2f energy=%.2f",
                    resp.throttle,
                    self.emotion.energy,
                )
            if resp.rest > 0.3:
                logger.debug(
                    "内稳态休眠倾向 rest=%.2f energy=%.2f",
                    resp.rest,
                    self.emotion.energy,
                )
            await maybe_mark_starving(
                self.ledger,
                self.emotion,
                self.heartbeat_count,
                db=self._db,
                starve_beats=starve_beats,
                sensitivity=sens,
                now=now,
            )
        except Exception:
            logger.debug("内稳态压力更新失败", exc_info=True)

        # 包 14 / 蛰伏第 1 批：断粮 → 单次封存 → STASIS → 停主心跳（库内不 sys.exit）
        if getattr(self.ledger, "starving", False):
            await self._enter_stasis()

        # 包 10：learning-progress 好奇（情绪步进之后、内在生命/GWS 之前）
        try:
            from qi.motivation.curiosity import CuriositySignal

            await CuriositySignal(config=self.config).update(self, now=now)
        except Exception:
            logger.debug("好奇信号更新失败", exc_info=True)

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
            self._ledger_safe_add_tokens(MEM_RETRIEVAL_TOKEN_COST)  # 检索估算
            loops = await self._load_open_loops()
            card = build_intention_card(
                channel="dialogue",
                user_message=pending,
                emotion=self.emotion,
                relationship_stage=self.relationship_stage,
                assessment=self.perception.last_assessment,
                memories=ctx.retrieved_memories,
                extras=ctx.extras,
                open_loops=loops,
            )
            await self._persist_intention(card)

            self.avatar.set_thinking(True)
            await self._sync_avatar(now, force=True)
            try:
                response = await self.expression.express(
                    user_message=pending,
                    emotion=self.emotion,
                    now=now,
                    intention=card,
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
            await self._persist_intention(card)
            # 包 12：说话 token（无 usage 则字符估算；空回复也记尝试成本）
            self._ledger_safe_add_tokens(self._ledger_token_cost_for_text(response))

            if response:
                self._pending_speech = _PendingSpeech(
                    text=response, now=now, proactive=False
                )
            else:
                logger.warning(
                    "对话表达仍为空 outcome=%s（意向卡已建）",
                    card.outcome,
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
            from qi.core.gws import gws_config

            self._gws_broadcast_hint = None
            if gws_config(self.config)["enabled"]:
                kind, action_type, response = await self._heartbeat_gws_idle(
                    want_express=want_express, now=now
                )
            else:
                kind, action_type, response = await self._heartbeat_legacy_idle(
                    want_express=want_express, now=now
                )

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

        self._ledger_maybe_estimate_storage()
        if pending is None:
            self._ledger_safe_credit_presence(now)
        try:
            self.ledger.add_compute(time.perf_counter() - t0)
        except Exception:
            logger.debug("账本 compute 记账失败", exc_info=True)

        self._last_response = response
        return response

    async def _speak_proactive(self, kind: str, now: datetime) -> str | None:
        """主动开口表达块——legacy / GWS 共用。"""
        ctx = await self._gather_prompt_context(None, now)
        self._ledger_safe_add_tokens(MEM_RETRIEVAL_TOKEN_COST)
        cue = self.proactive.cue_for(kind)
        loops = await self._load_open_loops()
        card = build_intention_card(
            channel="proactive",
            user_message=cue,
            emotion=self.emotion,
            relationship_stage=self.relationship_stage,
            assessment=None,
            memories=ctx.retrieved_memories,
            extras=ctx.extras,
            open_loops=loops,
            proactive_kind=kind,
        )
        await self._persist_intention(card)
        self.avatar.set_thinking(True)
        await self._sync_avatar(now, force=True)
        try:
            response = await self.expression.express(
                user_message=cue,
                emotion=self.emotion,
                now=now,
                intention=card,
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
        await self._persist_intention(card)
        self._ledger_safe_add_tokens(self._ledger_token_cost_for_text(response))

        if response:
            self.proactive.record(kind, now)
            if kind == "express_feeling":
                self._consume_expression_want()
            self._pending_speech = _PendingSpeech(
                text=response, now=now, proactive=True
            )
            await self._persist_proactive_gate()
            if card.outcome == "template":
                logger.warning("主动表达走模板降级 kind=%s", kind)
        else:
            logger.warning(
                "主动表达仍为空 kind=%s outcome=%s",
                kind,
                card.outcome,
            )
        return response

    async def _heartbeat_legacy_idle(
        self, *, want_express: bool, now: datetime
    ) -> tuple[str | None, str | None, str | None]:
        """旧路径：先 action.tick，再 pick_proactive（包 7 shadow 默认）。"""
        silence_seconds = self.perception.detect_silence(self.last_interaction, now)
        kind: str | None = None
        action_type: str | None = None
        response: str | None = None
        acted = False
        if self.action is not None:
            try:
                scars = (
                    await self._db.list_scars() if self._db is not None else None
                )
                trust = 0.5
                if self.relationship is not None:
                    trust = float(
                        getattr(self.relationship.state, "trust", 0.5) or 0.5
                    )
                action_result = await self.action.tick(
                    self.emotion,
                    self.relationship_stage,
                    self._current_season(),
                    now,
                    mode=self.emotion.mode.value,
                    user_online=self.user_online,
                    scars=scars,
                    pressure=self.last_pressure_response,
                    trust=trust,
                    silence_seconds=float(silence_seconds),
                    speaking=False,
                )
                if action_result is not None:
                    acted = True
                    action_type = (
                        str(
                            action_result.get("type")
                            or action_result.get("kind")
                            or ""
                        )
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
            response = await self._speak_proactive(kind, now)
        elif want_express:
            self._accumulated_suppressed = max(self._accumulated_suppressed, 1.01)
        return kind, action_type, response

    async def _heartbeat_gws_idle(
        self, *, want_express: bool, now: datetime
    ) -> tuple[str | None, str | None, str | None]:
        """GWS 启用：全量仲裁后互斥分发。"""
        from qi.core.gws import arbitrate
        from qi.core.proactive import KIND_EXPRESS_FEELING
        from qi.core.trace import collect_contenders

        kind: str | None = None
        action_type: str | None = None
        response: str | None = None
        curiosity_val = float(getattr(self.emotion, "curiosity", 0.0) or 0.0)
        candidates = await collect_contenders(
            self,
            pending=None,
            want_express=want_express,
            kind=None,
            action_type=None,
            now=now,
            curiosity=curiosity_val,
        )
        winner = arbitrate(candidates)
        self._gws_broadcast_hint = {
            "candidates": candidates,
            "winner_arb_kind": winner.kind if winner else "idle",
            "winner_arb_salience": float(winner.salience) if winner else 0.0,
        }
        if winner is None:
            if want_express:
                self._accumulated_suppressed = max(
                    self._accumulated_suppressed, 1.01
                )
            return None, None, None

        wkind = winner.kind
        if wkind.startswith("proactive:"):
            kind = wkind.split(":", 1)[1]
            response = await self._speak_proactive(kind, now)
        elif wkind.startswith("action:"):
            action_type = wkind.split(":", 1)[1]
            if self.action is not None:
                try:
                    scars = (
                        await self._db.list_scars()
                        if self._db is not None
                        else None
                    )
                    trust = 0.5
                    if self.relationship is not None:
                        trust = float(
                            getattr(self.relationship.state, "trust", 0.5) or 0.5
                        )
                    op = None
                    target_path = None
                    if (
                        action_type == "assist"
                        and self.last_assist_request is not None
                    ):
                        op = self.last_assist_request.op
                        target_path = self.last_assist_request.target_path
                    action_result = await self.action.execute_kind(
                        action_type,
                        self.emotion,
                        self.relationship_stage,
                        self._current_season(),
                        now,
                        mode=self.emotion.mode.value,
                        user_online=self.user_online,
                        scars=scars,
                        sensing=self.last_sensing,
                        pressure=self.last_pressure_response,
                        trust=trust,
                        op=op,
                        target_path=target_path,
                        confirmed=False,  # GWS 路径仍先走 confirm_gate
                    )
                    # assist-2 B3 消费 + assist-3 B1：清之前用 op/path 存 pending
                    if action_type == "assist":
                        if (
                            action_result
                            and action_result.get("type")
                            == "assist_confirm_request"
                            and op
                            and target_path
                        ):
                            from qi.action.volition import AssistRequest

                            self.pending_assist_confirmation = AssistRequest(
                                op=op, target_path=target_path
                            )
                            self.pending_assist_confirmation_at = now
                            self.pending_assist_heartbeats = 0
                        self.last_assist_request = None
                    if action_result is not None:
                        await self._persist_action_budget()
                        await self._deliver_action_result(action_result, now)
                    else:
                        action_type = None
                except Exception:
                    logger.exception("GWS 行动分发出错")
                    action_type = None
        elif wkind == "close_loop":
            if self.inner_life is not None:
                try:
                    silence = now - self.last_interaction
                    await self.inner_life.consciousness.maybe_generate(
                        self.emotion,
                        silence,
                        prefer_close=True,
                        prev_valence=self.emotion.valence,
                        prev_arousal=self.emotion.arousal,
                    )
                    await self._broadcast_journal_entries()
                except Exception:
                    logger.exception("GWS close_loop 分发出错")
        elif wkind == "report":
            if self.proactive.can(
                KIND_EXPRESS_FEELING, self.relationship_stage, now
            ):
                kind = KIND_EXPRESS_FEELING
                response = await self._speak_proactive(kind, now)
            elif want_express:
                self._accumulated_suppressed = max(
                    self._accumulated_suppressed, 1.01
                )
        elif want_express:
            self._accumulated_suppressed = max(self._accumulated_suppressed, 1.01)

        return kind, action_type, response

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
        """格式化最近心跳痕迹，供排障（原 CLI /why）。"""
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

    async def _enter_stasis(self) -> None:
        """进入蛰伏：每周期至多写一次 checkpoint，停主循环，通知前端。"""
        if not self.in_stasis:
            self.in_stasis = True
            if not self._stasis_checkpoint_written:
                try:
                    from qi.stasis.checkpoint import write_checkpoint

                    await write_checkpoint(self, self.checkpoint_dir)
                    self._stasis_checkpoint_written = True
                except Exception:
                    logger.exception("断粮封存失败，仍将进入蛰伏")
            logger.info("进入蛰伏（STASIS）：主心跳将停止")
            try:
                await self._sync_avatar(force=True)
            except Exception:
                logger.debug("蛰伏状态推送失败", exc_info=True)
        self.alive = False

    async def _reply_stasis_notice(self) -> str:
        """蛰伏中拒绝业务拍；推送固定提示。"""
        notice = self.STASIS_USER_NOTICE
        try:
            await self._emit_speech(notice)
        except Exception:
            logger.debug("蛰伏提示推送失败", exc_info=True)
        return notice

    _CONFIRM_CUES = ("看吧", "开吧", "好", "行", "确认", "可以", "嗯", "yes", "ok")
    # assist-5：pending 已消费后补执行的确认词（短语级，不含裸「好/行/嗯/可以/yes/ok」）
    _CONFIRM_CUES_REEXEC = (
        "看吧",
        "你读吧",
        "好你读吧",
        "读吧",
        "确认",
        "ok 看吧",
        "行 看吧",
    )
    # 「不用看」须先于「不用」；英文 no 只整句匹配（避免 notes 误伤）
    _REJECT_CUES = ("不用看", "不用", "算了", "不要", "取消", "别开")
    _NEW_ASSIST_MARKERS = ("帮我看", "帮我读", "帮我看一下", "帮我读一下")

    def _is_confirm_cue(self, text: str) -> bool:
        """assist-3：短确认；排除新协助请求（B3）。"""
        t = text.strip().lower()
        if any(m in t for m in self._NEW_ASSIST_MARKERS):
            return False
        return any(cue in t for cue in self._CONFIRM_CUES)

    def _is_confirm_reexec_cue(self, text: str) -> bool:
        """assist-5：pending 已消费后的窄确认词。"""
        t = text.strip().lower()
        return any(cue in t for cue in self._CONFIRM_CUES_REEXEC)

    def _assist_target_fresh(self, now: datetime) -> bool:
        if self.last_assist_target_at is None:
            return False
        return now - self.last_assist_target_at <= timedelta(minutes=5)

    def _is_reject_cue(self, text: str) -> bool:
        t = text.strip().lower()
        if t in ("no", "n"):
            return True
        return any(cue in t for cue in self._REJECT_CUES)

    def _clear_pending_assist(self) -> None:
        self.pending_assist_confirmation = None
        self.pending_assist_confirmation_at = None
        self.pending_assist_heartbeats = 0

    def _clear_assist_target(self) -> None:
        self.last_assist_target = None
        self.last_assist_target_at = None

    def _pending_selected_index(self, text: str) -> int | None:
        t = text.strip()
        if t in ("1", "2", "3"):
            return int(t) - 1
        return None

    def _is_open_pending(self, req: object) -> bool:
        try:
            from qi.action.open import OpenRequest

            return isinstance(req, OpenRequest)
        except Exception:
            return False

    async def _execute_open_on_request(
        self,
        open_req: object,
        *,
        confirmed: bool = False,
        selected_index: int | None = None,
    ) -> dict | None:
        if self.action is None:
            return None
        now = datetime.now()
        scars = None
        if self._db is not None:
            try:
                scars = await self._db.list_scars()
            except Exception:
                scars = None
        trust = 0.5
        if self.relationship is not None:
            trust = float(
                getattr(self.relationship.state, "trust", 0.5) or 0.5
            )
        return await self.action.execute_kind(
            "open",
            self.emotion,
            self.relationship_stage,
            self._current_season(),
            now,
            mode=self.emotion.mode.value,
            user_online=self.user_online,
            scars=scars,
            sensing=self.last_sensing,
            pressure=self.last_pressure_response,
            trust=trust,
            confirmed=confirmed,
            payload=open_req,
            selected_index=selected_index,
        )

    async def _execute_assist_on_request(
        self, assist_req: object, *, confirmed_override: bool = False
    ) -> dict | None:
        """assist-4/5：对话拍直接 execute_kind(assist)。

        默认 confirmed=False；assist-5 补执行传 confirmed_override=True。
        """
        if self.action is None:
            return None
        now = datetime.now()
        scars = None
        if self._db is not None:
            try:
                scars = await self._db.list_scars()
            except Exception:
                scars = None
        trust = 0.5
        if self.relationship is not None:
            trust = float(
                getattr(self.relationship.state, "trust", 0.5) or 0.5
            )
        return await self.action.execute_kind(
            "assist",
            self.emotion,
            self.relationship_stage,
            self._current_season(),
            now,
            mode=self.emotion.mode.value,
            user_online=self.user_online,
            scars=scars,
            sensing=self.last_sensing,
            pressure=self.last_pressure_response,
            trust=trust,
            op=getattr(assist_req, "op", None),
            target_path=getattr(assist_req, "target_path", None),
            confirmed=confirmed_override,
        )

    async def _execute_confirmed_assist(self, confirmed_req: object) -> dict | None:
        """B2：用户确认后直接 execute_kind(confirmed=True)，不走 GWS。"""
        if self.action is None:
            return None
        now = datetime.now()
        scars = None
        if self._db is not None:
            try:
                scars = await self._db.list_scars()
            except Exception:
                scars = None
        trust = 0.5
        if self.relationship is not None:
            trust = float(
                getattr(self.relationship.state, "trust", 0.5) or 0.5
            )
        return await self.action.execute_kind(
            "assist",
            self.emotion,
            self.relationship_stage,
            self._current_season(),
            now,
            mode=self.emotion.mode.value,
            user_online=self.user_online,
            scars=scars,
            sensing=self.last_sensing,
            pressure=self.last_pressure_response,
            trust=trust,
            op=getattr(confirmed_req, "op", None),
            target_path=getattr(confirmed_req, "target_path", None),
            confirmed=True,
        )

    async def receive_user_message(self, message: str) -> str | None:
        text = (message or "").strip()
        if not text:
            return None
        # 蛰伏：禁止「按一下跳一下」的假活业务心跳
        if self.in_stasis:
            return await self._reply_stasis_notice()
        async with self._heartbeat_lock:
            if self.in_stasis:
                return await self._reply_stasis_notice()

            # assist-3 / open：跨轮确认（控制消息；确认不进 pending_queue）
            if self.pending_assist_confirmation is not None:
                if self._is_reject_cue(text):
                    self._clear_pending_assist()
                    self._clear_assist_target()
                    now = datetime.now()
                    await self._deliver_qi_message("好。", now, proactive=False)
                    return "好。"
                sel = self._pending_selected_index(text)
                if self._is_confirm_cue(text) or sel is not None:
                    confirmed_req = self.pending_assist_confirmation
                    self._clear_pending_assist()
                    try:
                        if self._is_open_pending(confirmed_req):
                            self._clear_assist_target()
                            result = await self._execute_open_on_request(
                                confirmed_req,
                                confirmed=True,
                                selected_index=sel,
                            )
                        else:
                            # assist-5：确认成功后保留 last_assist_target（粘性补执行）
                            result = await self._execute_confirmed_assist(
                                confirmed_req
                            )
                        if result is not None:
                            await self._deliver_action_result(
                                result, datetime.now()
                            )
                            return (result.get("qi_line") or "").strip() or None
                    except Exception:
                        logger.exception("confirmed execute 失败")
                    return None
                # 换话题 / 新请求：清旧 pending + 粘性 target，落入正常对话
                self._clear_pending_assist()
                self._clear_assist_target()

            # assist-5：pending 已消费但用户仍短语确认——粘性目标补执行
            if self.last_assist_target is not None and self._is_confirm_reexec_cue(
                text
            ):
                now = datetime.now()
                if self._assist_target_fresh(now):
                    from qi.action.volition import AssistRequest

                    target = self.last_assist_target
                    self._clear_assist_target()
                    result = await self._execute_assist_on_request(
                        AssistRequest(op="read_file", target_path=target),
                        confirmed_override=True,
                    )
                    if result is not None:
                        await self._deliver_action_result(
                            result, datetime.now()
                        )
                        return (result.get("qi_line") or "").strip() or None
                await self._deliver_qi_message(
                    "嗯？你想让我看什么？", datetime.now(), proactive=False
                )
                return "嗯？你想让我看什么？"

            # look：叫停 / 解除 / 邀看（先于 assist；邀看不弹确认卡）
            try:
                from qi.action.look import (
                    detect_look_invite,
                    looks_like_look_pause,
                    looks_like_look_resume,
                )
            except Exception:
                detect_look_invite = None  # type: ignore[assignment]
                looks_like_look_pause = None  # type: ignore[assignment]
                looks_like_look_resume = None  # type: ignore[assignment]

            if (
                looks_like_look_pause is not None
                and looks_like_look_pause(text)
                and self.action is not None
            ):
                try:
                    await self.action.look.set_pause(datetime.now())
                    await self._deliver_qi_message(
                        "好，我先不看了。", datetime.now(), proactive=False
                    )
                    return "好，我先不看了。"
                except Exception:
                    logger.exception("look pause 失败")

            if (
                looks_like_look_resume is not None
                and looks_like_look_resume(text)
                and self.action is not None
            ):
                try:
                    await self.action.look.clear_pause()
                except Exception:
                    logger.debug("look resume 失败", exc_info=True)

            # open：先于 look 邀看（「看看这个链接」走 open_and_look，不误成纯 look）
            open_req = None
            if self.action is not None:
                try:
                    from qi.action.open import detect_open_intent

                    open_req = await detect_open_intent(text, llm=self.llm)
                except Exception:
                    logger.debug("open intent 判别失败", exc_info=True)
                    open_req = None
            if open_req is not None:
                try:
                    result = await self._execute_open_on_request(
                        open_req, confirmed=False
                    )
                    if result is not None:
                        if result.get("needs_confirmation") or (
                            result.get("outcome") == "confirm_required"
                        ):
                            self.pending_assist_confirmation = open_req
                            self.pending_assist_confirmation_at = datetime.now()
                            self.pending_assist_heartbeats = 0
                            self._clear_assist_target()
                        await self._deliver_action_result(
                            result, datetime.now()
                        )
                        return (result.get("qi_line") or "").strip() or None
                except Exception:
                    logger.exception("open 对话拍 execute 失败")
                return None

            look_invited = False
            if detect_look_invite is not None and self.action is not None:
                try:
                    look_invited = await detect_look_invite(text, llm=self.llm)
                except Exception:
                    logger.debug("look invite 判别失败", exc_info=True)
                    look_invited = False
            if look_invited:
                try:
                    now = datetime.now()
                    scars = (
                        await self._db.list_scars()
                        if self._db is not None
                        else None
                    )
                    trust = 0.5
                    if self.relationship is not None:
                        trust = float(
                            getattr(self.relationship.state, "trust", 0.5) or 0.5
                        )
                    result = await self.action.execute_kind(
                        "look",
                        self.emotion,
                        self.relationship_stage,
                        self._current_season(),
                        now,
                        mode=self.emotion.mode.value,
                        user_online=self.user_online,
                        scars=scars,
                        trust=trust,
                        op="invite",
                        target_path=text,
                        confirmed=True,
                    )
                    if result is not None:
                        await self._deliver_action_result(result, now)
                        return (result.get("qi_line") or "").strip() or None
                except Exception:
                    logger.exception("look 邀看 execute 失败")
                return None

            # assist-4：对话拍有 assist 请求时，assist 开口 = respond（不走 conversation LLM）
            self.last_user_message = text
            assist_req = None
            try:
                from qi.action.volition import parse_assist_request

                assist_req = parse_assist_request(text)
            except Exception:
                logger.debug("assist_request 解析失败", exc_info=True)
                assist_req = None
            self.last_assist_request = assist_req
            if assist_req is not None:
                self.last_assist_target = getattr(
                    assist_req, "target_path", None
                )
                self.last_assist_target_at = datetime.now()

            if assist_req is not None:
                # 不进 pending_queue、不跑 respond LLM、不跑 _heartbeat
                try:
                    result = await self._execute_assist_on_request(assist_req)
                    if result is not None:
                        # B1：与 GWS 路径同构——confirm_gate 后存 pending（局部 assist_req）
                        if result.get("needs_confirmation") or (
                            result.get("outcome") == "confirm_required"
                        ):
                            self.pending_assist_confirmation = assist_req
                            self.pending_assist_confirmation_at = datetime.now()
                            self.pending_assist_heartbeats = 0
                        self.last_assist_request = None
                        await self._deliver_action_result(
                            result, datetime.now()
                        )
                        return (result.get("qi_line") or "").strip() or None
                except Exception:
                    logger.exception("assist 对话拍 execute 失败")
                return None

            # 正常对话路径（无 assist 请求）
            if len(self._pending_queue) >= PENDING_QUEUE_MAX:
                dropped = self._pending_queue.popleft()
                logger.warning(
                    "待处理消息队列已满，丢弃最早一条: %s",
                    dropped[:40],
                )
            self._pending_queue.append(text)
            await self._heartbeat()
            speech = self._take_pending_speech()
        if self.in_stasis and speech is None:
            return await self._reply_stasis_notice()
        if speech is None:
            return None
        # 生成已在锁内完成；出锁后再「想了想」，再推送——不堵心跳
        # C4 时机阀：随机仅扰动投递时刻，不是动机来源
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self._deliver_qi_message(
            speech.text, speech.now, proactive=speech.proactive
        )
        await self._maybe_prefer_close_after_deliver()
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
            db, self.config, narrative=self.memory.narrative, llm=self.llm
        )
        await self.action.restore_budget()
        saved_gate = await db.get_body_memory("proactive_gate")
        if isinstance(saved_gate, dict):
            self.proactive.restore(saved_gate)
        ledger_data = await db.get_body_memory(LEDGER_BODY_KEY)
        if isinstance(ledger_data, dict):
            self.ledger.restore(ledger_data)
        saved = await db.load_emotion()
        if saved is not None:
            self.emotion = saved
            self._prev_valence = saved.valence
            if self.inner_life:
                self.inner_life._prev_valence = saved.valence
                self.inner_life._prev_arousal = saved.arousal
            logger.info("恢复情绪：%s", self.emotion.description())
        # 账本仍断粮：直接进入蛰伏，避免半死假 OPERATIONAL
        if self.ledger.starving:
            self.in_stasis = True
            self._stasis_checkpoint_written = True
            self.alive = False
            logger.info("恢复时已断粮：进入蛰伏，主心跳不启动")
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
        try:
            await db.set_body_memory(LEDGER_BODY_KEY, self.ledger.snapshot())
        except Exception:
            logger.debug("账本持久化失败", exc_info=True)
        if self.relationship is not None:
            await self.relationship.persist()

    async def restore_from_checkpoint(
        self, dir_path: str | Path | None = None
    ) -> bool:
        """从最新封存恢复内存态（独立于 restore_state；供测试/CLI）。"""
        from qi.stasis.checkpoint import restore_latest

        root = Path(dir_path) if dir_path is not None else self.checkpoint_dir
        return await restore_latest(self, root)
