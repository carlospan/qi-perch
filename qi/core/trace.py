"""广播痕迹 + 显著性评分——GWS 数据地基（阶段二·包 6）。

只记录竞争者与分数，不仲裁、不改行为。
winner 仍由现状心跳逻辑（pending > action > proactive > idle）决定。
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.core.emotion import STAGE_BASELINES, baseline_for
from qi.core.proactive import (
    KIND_CHECK_IN,
    KIND_EXPRESS_FEELING,
    KIND_REACH_OUT,
    ProactiveGate,
)

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.trace")


@dataclass(frozen=True)
class Contender:
    """竞争者快照——只建模，本包不仲裁。"""

    kind: str
    salience: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def salience_respond(*, has_pending: bool) -> float:
    """用户消息：在则恒 1.0，不在则 0.0。"""
    return 1.0 if has_pending else 0.0


def salience_action(*, priority: float) -> float:
    """自主行动：直接用 Intention.priority，夹到 0–1。"""
    return _clamp01(priority)


def salience_close_loop(*, open_loop_count: int) -> float:
    """未闭合念头：积压 0→0；≥1 给 baseline 0.3；满 5→1（补丁 C）。"""
    n = int(open_loop_count)
    if n <= 0:
        return 0.0
    return _clamp01(max(0.3, n / 5.0))


def salience_proactive_express(*, want_express: bool) -> float:
    return 0.85 if want_express else 0.0


def salience_proactive_check_in(
    *,
    silence_seconds: float,
    security: float,
    attachment: float,
) -> float:
    """安静 + 不安/惦记 → 关心；分数确定性、无随机。"""
    s = 0.0
    if silence_seconds >= 1800:
        s = 0.5
    if silence_seconds >= 3600:
        s = 0.65
    if security < 0.45:
        s = min(1.0, s + 0.2)
    if attachment > 0.55:
        s = min(1.0, s + 0.15)
    return _clamp01(s)


def salience_proactive_reach_out(
    *,
    silence_seconds: float,
    relationship_stage: str,
) -> float:
    if silence_seconds < 3600:
        return 0.0
    if relationship_stage not in ("friend", "bonded"):
        return 0.0
    return 0.55 if silence_seconds < 7200 else 0.7


def salience_report(
    *,
    energy: float,
    security: float,
    uptime_seconds: float | None = None,
    uptime_report_seconds: float = 3 * 3600,
) -> float:
    """极简内稳态报告：低能量、低安全、或在线过久才响。"""
    score = 0.0
    if energy < 0.3:
        score = max(score, 0.5 + (0.3 - energy))
    if security < 0.35:
        score = max(score, 0.4 + (0.35 - security))
    if uptime_seconds is not None and uptime_seconds >= uptime_report_seconds:
        # 补丁 C：在线>3h 给 baseline 0.3；不另开 LLM
        overtime = (uptime_seconds - uptime_report_seconds) / 3600.0
        score = max(score, _clamp01(0.3 + min(0.2, overtime * 0.05)))
    return _clamp01(score)


def salience(kind: str, **signals: Any) -> float:
    """按 kind 分发显著性（纯规则、确定性）。"""
    if kind == "respond":
        return salience_respond(has_pending=bool(signals.get("has_pending")))
    if kind.startswith("action:"):
        return salience_action(priority=float(signals.get("action_priority") or 0))
    if kind == "close_loop":
        return salience_close_loop(
            open_loop_count=int(signals.get("open_loop_count") or 0)
        )
    if kind == f"proactive:{KIND_EXPRESS_FEELING}" or kind == "proactive:express_feeling":
        return salience_proactive_express(
            want_express=bool(signals.get("want_express"))
        )
    if kind == f"proactive:{KIND_CHECK_IN}" or kind == "proactive:check_in":
        return salience_proactive_check_in(
            silence_seconds=float(signals.get("silence_seconds") or 0),
            security=float(signals.get("security") or 0.5),
            attachment=float(signals.get("attachment") or 0.3),
        )
    if kind == f"proactive:{KIND_REACH_OUT}" or kind == "proactive:reach_out":
        return salience_proactive_reach_out(
            silence_seconds=float(signals.get("silence_seconds") or 0),
            relationship_stage=str(signals.get("relationship_stage") or "stranger"),
        )
    if kind == "report":
        uptime = signals.get("uptime_seconds")
        return salience_report(
            energy=float(signals.get("energy") or 0.6),
            security=float(signals.get("security") or 0.5),
            uptime_seconds=float(uptime) if uptime is not None else None,
            uptime_report_seconds=float(
                signals.get("uptime_report_seconds") or 3 * 3600
            ),
        )
    if kind == "curiosity":
        return _clamp01(float(signals.get("curiosity") or 0))
    return 0.0


def winner_from_legacy(
    *,
    pending: str | None,
    kind: str | None,
    action_type: str | None,
    candidates: list[Contender],
) -> tuple[str, float]:
    """现状优先级决定 winner——不取 salience 最大者。"""
    by_kind = {c.kind: c.salience for c in candidates}
    if pending:
        return "respond", by_kind.get("respond", 1.0)
    if action_type:
        k = f"action:{action_type}"
        return k, by_kind.get(k, salience_action(priority=0.5))
    if kind:
        k = f"proactive:{kind}"
        return k, by_kind.get(k, 0.5)
    return "idle", 0.0


def outcome_from_legacy(
    *,
    pending: str | None,
    kind: str | None,
    action_type: str | None,
    want_express: bool,
) -> str:
    if pending:
        return "responded"
    if action_type:
        return "action"
    if kind:
        return "proactive"
    if want_express:
        return "suppressed"
    return "idle"


def motive_snapshot(
    brain: Brain,
    *,
    want_express: bool,
) -> dict[str, Any]:
    e = brain.emotion
    pressure = 1.0 if want_express else _clamp01(
        float(getattr(brain, "_accumulated_suppressed", 0) or 0) / 3.0
    )
    snap: dict[str, Any] = {
        "homeostasis": {
            "energy": round(e.energy, 4),
            "security": round(e.security, 4),
            "attachment": round(e.attachment, 4),
            "valence": round(e.valence, 4),
        },
        "curiosity": round(e.curiosity, 4),
        "express_pressure": round(pressure, 4),
    }
    sensing = getattr(brain, "last_sensing", None)
    if sensing is not None:
        snap["sensing_uptime"] = round(float(sensing.uptime_seconds), 3)
    world = getattr(brain, "last_world", None)
    if world is not None:
        snap["world_surprise"] = round(
            float(world.get("online_rhythm", {}).get("surprise", 0.0)),
            4,
        )
        if isinstance(world, dict):
            et = world.get("emotion_trajectory") or {}
            surp = et.get("surprise") or {}
            if isinstance(surp, dict) and surp:
                snap["emotion_trajectory_surprise"] = {
                    k: round(float(v), 4) for k, v in surp.items()
                }
    closed = None
    if brain.action is not None:
        closed = getattr(brain.action, "last_closed_loop", None)
    if isinstance(closed, dict) and closed.get("op"):
        after = closed.get("after") or {}
        delta = ""
        if closed.get("op") == "archive":
            delta = f"archived_ids={after.get('archived_ids')}"
        elif closed.get("op") == "budget_tune":
            delta = f"weights={after.get('kind_weights')}"
        elif closed.get("op") == "journal":
            delta = f"stream_id={after.get('stream_id')}"
        elif closed.get("op") == "explore":
            delta = f"entries={len(after.get('entries') or [])}"
        else:
            delta = str(after)[:120]
        snap["closed_loop"] = {
            "op": closed.get("op"),
            "delta": delta,
            "sensing_uptime": snap.get("sensing_uptime"),
        }
    return snap


def _observe_proactive_candidates(
    *,
    want_express: bool,
    relationship_stage: str,
    emotion_security: float,
    emotion_attachment: float,
    silence_seconds: float,
    mode: str,
    user_online: bool,
    gate: ProactiveGate,
    now: datetime,
    actual_kind: str | None,
) -> list[Contender]:
    """重放 pick 条件（只读，不 gate.record）。"""
    out: list[Contender] = []
    if not user_online or mode == "dreaming" or relationship_stage == "stranger":
        if actual_kind:
            out.append(
                Contender(
                    kind=f"proactive:{actual_kind}",
                    salience=0.5,
                    reason="本拍实际选中（门控外观测补记）",
                )
            )
        return out

    seen: set[str] = set()

    def add(sub: str, score: float, reason: str) -> None:
        k = f"proactive:{sub}"
        if k in seen:
            return
        seen.add(k)
        out.append(Contender(kind=k, salience=score, reason=reason))

    if want_express and gate.can(KIND_EXPRESS_FEELING, relationship_stage, now):
        add(
            KIND_EXPRESS_FEELING,
            salience_proactive_express(want_express=True),
            "表达欲过阈且门控可",
        )
    if (
        silence_seconds >= 1800
        and (emotion_security < 0.45 or emotion_attachment > 0.55)
        and gate.can(KIND_CHECK_IN, relationship_stage, now)
    ):
        add(
            KIND_CHECK_IN,
            salience_proactive_check_in(
                silence_seconds=silence_seconds,
                security=emotion_security,
                attachment=emotion_attachment,
            ),
            "安静一阵且不安/惦记",
        )
    if (
        silence_seconds >= 3600
        and relationship_stage in ("friend", "bonded")
        and gate.can(KIND_REACH_OUT, relationship_stage, now)
    ):
        add(
            KIND_REACH_OUT,
            salience_proactive_reach_out(
                silence_seconds=silence_seconds,
                relationship_stage=relationship_stage,
            ),
            "更久的安静，轻轻搭话",
        )

    if actual_kind and f"proactive:{actual_kind}" not in seen:
        add(actual_kind, 0.5, "本拍实际选中")
    return out


async def collect_contenders(
    brain: Brain,
    *,
    pending: str | None,
    want_express: bool,
    kind: str | None,
    action_type: str | None,
    now: datetime,
    curiosity: float = 0.0,
) -> list[Contender]:
    """只读收集本拍竞争者——不算 winner。"""
    del curiosity  # 形参保留（调用方仍传）；包 10 contender 注入已回退，本函数不再消费
    candidates: list[Contender] = []
    silence = 0.0
    try:
        silence = float(brain.perception.detect_silence(brain.last_interaction, now))
    except Exception:
        logger.debug("broadcast 读沉默失败", exc_info=True)

    if pending:
        candidates.append(
            Contender(
                kind="respond",
                salience=salience_respond(has_pending=True),
                reason="用户消息在队",
            )
        )

    # proactive 观测候选
    try:
        candidates.extend(
            _observe_proactive_candidates(
                want_express=want_express,
                relationship_stage=brain.relationship_stage,
                emotion_security=brain.emotion.security,
                emotion_attachment=brain.emotion.attachment,
                silence_seconds=silence,
                mode=brain.emotion.mode.value,
                user_online=brain.user_online,
                gate=brain.proactive,
                now=now,
                actual_kind=kind,
            )
        )
    except Exception:
        logger.debug("broadcast 观测 proactive 失败", exc_info=True)
        if kind:
            candidates.append(
                Contender(
                    kind=f"proactive:{kind}",
                    salience=0.5,
                    reason="本拍实际选中",
                )
            )

    # action 观测：尽量列出 intentions；失败则仅记已执行类型
    try:
        if brain.action is not None and pending is None:
            from qi.action.volition import action_intentions

            scars = None
            if brain._db is not None:
                try:
                    scars = await brain._db.list_scars()
                except Exception:
                    scars = None
            undelivered = None
            try:
                undelivered = await brain.action.db.load_unshared_creation()
            except Exception:
                pass
            tend_occasion = None
            try:
                season = brain._current_season()
                tend_occasion = await brain.action.detect_tend_occasion(season, now)
                scale = brain.action.season_scale(season)
            except Exception:
                season = "spring"
                scale = 1.0
            archivable_count = 0
            try:
                archivable = await brain.action.db.list_archivable_narratives(
                    limit=3
                )
                archivable_count = len(archivable)
            except Exception:
                archivable_count = 0
            open_loop_n = 0
            try:
                open_loop_n = len(await brain._load_open_loops())
            except Exception:
                open_loop_n = 0
            uptime = None
            sensing = getattr(brain, "last_sensing", None)
            if sensing is not None:
                uptime = float(sensing.uptime_seconds)
            # N3：内稳态压力软调制 explore 候选 priority
            pressure = getattr(brain, "last_pressure_response", None)
            intents = action_intentions(
                mode=brain.emotion.mode.value,
                relationship_stage=brain.relationship_stage,
                curiosity=float(brain.emotion.curiosity),
                valence=float(brain.emotion.valence),
                has_undelivered_creation=undelivered is not None,
                tend_occasion=tend_occasion,
                user_message=getattr(brain, "last_user_message", None),
                budget=brain.action.budget,
                now=now,
                season_scale=scale,
                scars=scars,
                user_online=brain.user_online,
                archivable_count=archivable_count,
                open_loop_count=open_loop_n,
                sensing_uptime_seconds=uptime,
                energy=float(brain.emotion.energy),
                pressure=pressure,
            )
            # B1：assist 放行进 GWS（响应式候选；assist-1 已接执行骨架）
            for it in intents:
                candidates.append(
                    Contender(
                        kind=f"action:{it.kind}",
                        salience=salience_action(priority=it.priority),
                        reason=it.reason or it.kind,
                    )
                )
        if action_type and not any(
            c.kind == f"action:{action_type}" for c in candidates
        ):
            candidates.append(
                Contender(
                    kind=f"action:{action_type}",
                    salience=salience_action(priority=0.5),
                    reason="本拍已执行",
                )
            )
    except Exception:
        logger.debug("broadcast 观测 action 失败", exc_info=True)
        if action_type:
            candidates.append(
                Contender(
                    kind=f"action:{action_type}",
                    salience=0.5,
                    reason="本拍已执行",
                )
            )

    # open loops
    loop_n = 0
    try:
        loops = await brain._load_open_loops()
        loop_n = len(loops)
        if loop_n > 0:
            candidates.append(
                Contender(
                    kind="close_loop",
                    salience=salience_close_loop(open_loop_count=loop_n),
                    reason=f"未闭合念头 {loop_n}",
                )
            )
    except Exception:
        logger.debug("broadcast 读 open_loops 失败", exc_info=True)

    # 极简内稳态报告（含在线过久）
    uptime_s = None
    sensing = getattr(brain, "last_sensing", None)
    if sensing is not None:
        uptime_s = float(sensing.uptime_seconds)
    report_s = salience_report(
        energy=brain.emotion.energy,
        security=brain.emotion.security,
        uptime_seconds=uptime_s,
    )
    if report_s > 0:
        # 相对阶段锚的 attachment 偏差仅写入 reason，不另开随机
        stage = brain.relationship_stage
        att_base = float(
            STAGE_BASELINES.get(stage, {}).get("attachment")
            or baseline_for("attachment", stage)
        )
        delta = abs(brain.emotion.attachment - att_base)
        reason = f"内稳态压力 energy/security；attΔ={delta:.2f}"
        if uptime_s is not None and uptime_s >= 3 * 3600:
            reason += f"；在线过久 {uptime_s / 3600:.1f}h"
        candidates.append(
            Contender(
                kind="report",
                salience=report_s,
                reason=reason,
            )
        )

    return candidates


async def persist_broadcast(
    brain: Brain,
    *,
    pending: str | None,
    want_express: bool,
    kind: str | None,
    action_type: str | None,
    now: datetime,
    candidates: list[Contender] | None = None,
    winner_arb_kind: str | None = None,
    winner_arb_salience: float | None = None,
) -> None:
    """每拍写一条 broadcast_traces（含 GWS shadow 对照）；失败不抛。"""
    if brain._db is None:
        return
    try:
        from qi.core.gws import (
            arbitrate,
            executable_contenders,
            gws_config,
            record_shadow_beat,
            shadow_match,
        )

        hint = getattr(brain, "_gws_broadcast_hint", None)
        if candidates is None and isinstance(hint, dict):
            candidates = hint.get("candidates")
            if winner_arb_kind is None:
                winner_arb_kind = hint.get("winner_arb_kind")
                winner_arb_salience = hint.get("winner_arb_salience")
        if candidates is None:
            curiosity_val = float(
                getattr(getattr(brain, "emotion", None), "curiosity", 0.0) or 0.0
            )
            candidates = await collect_contenders(
                brain,
                pending=pending,
                want_express=want_express,
                kind=kind,
                action_type=action_type,
                now=now,
                curiosity=curiosity_val,
            )
        winner_kind, winner_salience = winner_from_legacy(
            pending=pending,
            kind=kind,
            action_type=action_type,
            candidates=candidates,
        )
        outcome = outcome_from_legacy(
            pending=pending,
            kind=kind,
            action_type=action_type,
            want_express=want_express,
        )

        gcfg = gws_config(brain.config)
        # Shadow 对照：未启用时用可执行子集；启用后优先用分发时的全量仲裁结果
        if winner_arb_kind is None:
            shadow_pool = (
                candidates
                if gcfg["enabled"]
                else executable_contenders(candidates)
            )
            arb = arbitrate(shadow_pool)
            winner_arb_kind = arb.kind if arb else "idle"
            winner_arb_salience = float(arb.salience) if arb else 0.0
        matched = shadow_match(winner_kind, winner_arb_kind)
        await record_shadow_beat(
            brain._db, matched=matched, config=brain.config
        )

        await brain._db.insert_broadcast_trace(
            beat=int(brain.heartbeat_count),
            timestamp=now,
            winner_kind=winner_kind,
            winner_salience=float(winner_salience),
            candidates=[c.to_dict() for c in candidates],
            motive=motive_snapshot(brain, want_express=want_express),
            outcome=outcome,
            winner_arb=winner_arb_kind,
            winner_arb_salience=winner_arb_salience,
            arb_matches_legacy=matched,
        )
    except Exception:
        logger.debug("写入 broadcast_traces 失败", exc_info=True)
