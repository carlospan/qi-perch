"""Brain 后台协程——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.brain_types import SEASON_EMOTION_HOURS
from qi.relationship.culture import detect_shared_culture
from qi.relationship.drift import build_updated_user_model, detect_user_drift
from qi.relationship.season import determine_season

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")


class BackgroundTasks:
    """Brain 的 8 个后台协程：统一 start/stop。"""

    def __init__(self, brain: Brain) -> None:
        self._brain = brain
        self._tasks: list[asyncio.Task] = []

    def start(self) -> None:
        b = self._brain
        self._tasks = [
            asyncio.create_task(b._background_narrative_weaving()),
            asyncio.create_task(b._background_memory_decay()),
            asyncio.create_task(b._background_self_reflection()),
            asyncio.create_task(b._background_dream_decay()),
            asyncio.create_task(b._background_culture_detection()),
            asyncio.create_task(b._background_season_detection()),
            asyncio.create_task(b._background_scar_healing()),
            asyncio.create_task(b._background_user_drift()),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []


async def narrative_weaving(brain: Brain) -> None:
    mem_cfg = brain.config.get("memory", {})
    interval = float(mem_cfg.get("narrative_weave_interval", 21600))
    backlog_threshold = int(mem_cfg.get("narrative_weave_backlog_threshold", 8))
    backlog_interval = float(mem_cfg.get("narrative_weave_backlog_interval", 900))
    check_period = float(mem_cfg.get("narrative_weave_check_period", 3600))
    while brain.alive:
        pending = await brain._pending_event_count()
        if pending >= backlog_threshold:
            # 积压够：短周期
            await asyncio.sleep(backlog_interval)
        else:
            # 积压不够：长睡 interval，但拆成 check_period 小段复查；
            # 积压中途涨够就提前跳出，不再干等满 interval（W4）
            waited = 0.0
            while brain.alive and waited < interval:
                chunk = min(check_period, interval - waited)
                await asyncio.sleep(chunk)
                waited += chunk
                if await brain._pending_event_count() >= backlog_threshold:
                    break
        # 睡眠已在分支内完成，这里直接织——不再二次 sleep
        if not brain.alive or brain.memory is None:
            continue
        try:
            if await brain.memory.has_unprocessed_events():
                await brain.memory.weave_narrative(
                    brain.emotion, brain.relationship_stage
                )
        except Exception:
            logger.exception("叙事编织后台出错")


async def pending_event_count(brain: Brain) -> int:
    if brain.memory is None:
        return 0
    try:
        return await brain.memory.unprocessed_event_count()
    except Exception:
        logger.exception("统计未编织事件失败")
        return 0


async def memory_decay(brain: Brain) -> None:
    interval = float(brain.config.get("memory", {}).get("decay_interval", 86400))
    while brain.alive:
        await asyncio.sleep(interval)
        if not brain.alive or brain.memory is None:
            continue
        try:
            await brain.memory.narrative.decay()
        except Exception:
            logger.exception("记忆褪色后台出错")


async def self_reflection(brain: Brain) -> None:
    """
    定期询问是否该反思。门控在 should_reflect（周间隔 / 重大事件标志），
    这里用短轮询，避免 mark_major_event 后要等将近一周才轮到。
    """
    interval = float(
        brain.config.get("inner_life", {}).get("self_reflection_interval", 604800)
    )
    # 轮询周期：默认 60s；若配置的反思间隔更短则跟着走
    poll = min(60.0, max(5.0, interval))
    await asyncio.sleep(poll)
    while brain.alive:
        if brain.inner_life is not None:
            try:
                await brain.inner_life.self_model.maybe_reflect(
                    brain.emotion, brain.relationship_stage
                )
            except Exception:
                logger.exception("自我反思后台出错")
        await asyncio.sleep(poll)


async def dream_decay(brain: Brain) -> None:
    while brain.alive:
        await asyncio.sleep(3600)
        if not brain.alive or brain.inner_life is None:
            continue
        try:
            await brain.inner_life.dreams.decay_all()
        except Exception:
            logger.exception("梦境衰减后台出错")


async def resume_interval_wait(
    brain: Brain, key: str, interval: float, default_first: float
) -> float:
    """检测类后台任务的首次等待：距上次检测不足周期则补足。

    重启不重置检测节奏——频繁重启时短首跑延迟会把「每天/每三天一轮」
    变成「每次重启一轮」，小样本误报被反复制造（实证：漂移/文化误报）。
    与 proactive gate、depth 日帽同构，落 body_memory。
    """
    if brain._db is None:
        return min(default_first, interval)
    try:
        last = await brain._db.get_body_memory(key)
        if last:
            elapsed = (
                datetime.now() - datetime.fromisoformat(str(last))
            ).total_seconds()
            if elapsed >= 0:
                return max(60.0, interval - elapsed)
    except (TypeError, ValueError):
        pass
    except Exception:
        logger.exception("读取检测节奏 %s 失败，用默认首跑延迟", key)
    return min(default_first, interval)


async def mark_interval_done(brain: Brain, key: str) -> None:
    if brain._db is None:
        return
    try:
        await brain._db.set_body_memory(key, datetime.now().isoformat())
    except Exception:
        logger.exception("写入检测节奏 %s 失败", key)


async def culture_detection(brain: Brain) -> None:
    interval = float(
        brain.config.get("relationship", {}).get("culture_detection_interval", 86400)
    )
    await asyncio.sleep(
        await brain._resume_interval_wait("last_culture_check", interval, 120.0)
    )
    while brain.alive:
        if brain.relationship is not None and brain._db is not None:
            try:
                msgs = await brain._db.load_recent_messages(limit=200)
                culture = detect_shared_culture(
                    msgs, brain.relationship.state.shared_culture
                )
                brain.relationship.state.shared_culture = culture
                await brain.relationship.persist()
                await brain._mark_interval_done("last_culture_check")
            except Exception:
                logger.exception("共同文化检测出错")
        await asyncio.sleep(interval)


async def season_detection(brain: Brain) -> None:
    interval = float(
        brain.config.get("relationship", {}).get("season_detection_interval", 86400)
    )
    await asyncio.sleep(min(180.0, interval))
    while brain.alive:
        if brain.relationship is not None and brain._db is not None:
            try:
                hours = float(
                    brain.config.get("relationship", {}).get(
                        "season_emotion_hours", SEASON_EMOTION_HOURS
                    )
                )
                history = await brain._db.load_recent_emotions(
                    since_hours=hours, limit=200
                )
                old = brain.relationship.state.season
                new = determine_season(history)
                if new != old:
                    brain.relationship.state.season = new
                    await brain.relationship.persist()
                    from qi.inner_life.identity_snapshot import (
                        mark_identity_snapshot_stale,
                    )

                    await mark_identity_snapshot_stale(brain._db)
                    if brain.inner_life is not None:
                        await _enqueue_and_think(
                            brain,
                            kind="season_change",
                            seed=f"从{old}偏到了{new}",
                        )
            except Exception:
                logger.exception("季节判定出错")
        await asyncio.sleep(interval)


async def scar_healing(brain: Brain) -> None:
    interval = float(
        brain.config.get("relationship", {}).get("scar_healing_interval", 86400)
    )
    await asyncio.sleep(min(240.0, interval))
    while brain.alive:
        if brain.scars is not None and brain.relationship is not None:
            try:
                healed = await brain.scars.check_healing(brain.relationship.state.trust)
                if healed:
                    await brain.relationship.on_scar_healed()
            except Exception:
                logger.exception("伤疤愈合检查出错")
        await asyncio.sleep(interval)


async def user_drift(brain: Brain) -> None:
    interval = float(
        brain.config.get("relationship", {}).get("drift_detection_interval", 259200)
    )
    await asyncio.sleep(
        await brain._resume_interval_wait("last_drift_check", interval, 300.0)
    )
    while brain.alive:
        if brain._db is not None:
            try:
                model = await brain._db.load_user_model() or {}
                msgs = await brain._db.load_recent_messages(limit=100)
                signals = detect_user_drift(model, msgs)
                updated = build_updated_user_model(msgs, signals)
                await brain._db.save_user_model(**updated)
                await brain._mark_interval_done("last_drift_check")
                if signals:
                    brain._drift_signals = signals
                    if brain.inner_life is not None:
                        await _enqueue_and_think(
                            brain,
                            kind="user_drift",
                            seed="；".join(signals)[:60],
                        )
            except Exception:
                logger.exception("用户漂移检测出错")
        await asyncio.sleep(interval)


async def _enqueue_and_think(brain: Brain, *, kind: str, seed: str) -> None:
    """季节/漂移：enqueue + 即时 generate（模板可兜底），不再裸写独白。"""
    now = datetime.now()
    silence = now - brain.last_interaction
    thought = await brain.inner_life.consciousness.maybe_generate(
        brain.emotion,
        silence,
        force_trigger=kind,
        force_seed=seed,
    )
    if thought:
        brain.inner_life.last_journal_entries = [
            {
                "kind": "独白",
                "text": thought.strip(),
                "at": int(now.timestamp() * 1000),
            }
        ]
        await brain._broadcast_journal_entries()
