"""关系引擎——阶段、深度、信任、温度。只升不降。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from qi.relationship.stages import STAGE_THRESHOLDS, STAGES, check_stage_upgrade
from qi.relationship.trust import (
    apply_daily_decay,
    apply_negative_event,
    apply_positive_interaction,
    apply_scar_healed_bonus,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

DAILY_DEPTH_CAP = 0.03


class RelationshipState(BaseModel):
    stage: str = "stranger"
    depth: float = 0.0
    temperature: float = 0.5
    trust: float = 0.5
    season: str = "spring"
    narrative: str = ""
    shared_culture: list = Field(default_factory=list)


class InteractionSignals:
    """一次交互的质量信号（规则启发式）。"""

    def __init__(
        self,
        self_disclosure: float = 0.0,
        emotional_vulnerability: float = 0.0,
        shared_experience: float = 0.0,
        is_deep: bool = False,
        is_positive: bool = True,
        is_negative: bool = False,
        quality: float = 0.4,
        severity: float = 0.0,
        event_desc: str = "",
    ):
        self.self_disclosure = self_disclosure
        self.emotional_vulnerability = emotional_vulnerability
        self.shared_experience = shared_experience
        self.is_deep = is_deep
        self.is_positive = is_positive
        self.is_negative = is_negative
        self.quality = quality
        self.severity = severity
        self.event_desc = event_desc


def assess_interaction(message: str) -> InteractionSignals:
    text = message.strip()
    disclosure = 0.0
    if any(k in text for k in ("我最近", "我今天", "我觉得", "我喜欢", "我害怕", "我工作")):
        disclosure = 0.7
    if any(k in text for k in ("分手", "换工作", "生病", "难过", "孤独")):
        disclosure = 0.9

    vulnerability = 0.0
    if any(k in text for k in ("难过", "害怕", "累", "想哭", "压力", "不安")):
        vulnerability = 0.8
    if any(k in text for k in ("开心", "高兴", "幸福")):
        vulnerability = 0.5

    negative = any(k in text for k in ("烦", "闭嘴", "删掉", "滚", "讨厌", "不想理", "你烦"))
    positive = any(k in text for k in ("谢谢", "喜欢", "真好", "有你在", "晚安", "早"))
    deep = len(text) > 40 and (disclosure > 0.5 or vulnerability > 0.5)

    severity = 0.0
    if negative:
        severity = 0.5
        if any(k in text for k in ("删掉", "滚", "闭嘴")):
            severity = 0.85

    quality = 0.3
    if positive:
        quality = 0.6
    if disclosure > 0.5:
        quality = max(quality, 0.7)
    if deep:
        quality = max(quality, 0.85)

    return InteractionSignals(
        self_disclosure=disclosure,
        emotional_vulnerability=vulnerability,
        shared_experience=0.3 if deep else 0.0,
        is_deep=deep,
        is_positive=positive and not negative,
        is_negative=negative,
        quality=quality,
        severity=severity,
        event_desc=text[:80],
    )


def depth_increment(signals: InteractionSignals, already_today: float) -> float:
    inc = 0.0
    inc += signals.self_disclosure * 0.02
    inc += signals.emotional_vulnerability * 0.015
    inc += signals.shared_experience * 0.01
    if signals.is_deep:
        inc += 0.02
    room = max(0.0, DAILY_DEPTH_CAP - already_today)
    return min(inc, room)


class RelationshipEngine:
    """关系状态的唯一入口。"""

    def __init__(self, db: Database, llm: LLMGateway | None = None, config: dict | None = None):
        self.db = db
        self.llm = llm
        self.config = config or {}
        self.state = RelationshipState()
        self._depth_gained_today = 0.0
        self._depth_day: str | None = None
        self._had_interaction_today = False
        self._interaction_day: str | None = None

    def _roll_day(self, now: datetime) -> None:
        day = now.strftime("%Y-%m-%d")
        if self._depth_day != day:
            self._depth_day = day
            self._depth_gained_today = 0.0
        if self._interaction_day != day:
            # 跨日：若昨日无交互，做一次信任微衰
            if self._interaction_day is not None and not self._had_interaction_today:
                self.state.trust = apply_daily_decay(self.state.trust, False)
            self._interaction_day = day
            self._had_interaction_today = False

    async def restore(self) -> RelationshipState:
        row = await self.db.load_relationship()
        if row:
            culture = row.get("shared_culture") or "[]"
            if isinstance(culture, str):
                try:
                    culture = json.loads(culture)
                except json.JSONDecodeError:
                    culture = []
            self.state = RelationshipState(
                stage=row.get("stage") or "stranger",
                depth=float(row.get("depth") or 0.0),
                temperature=float(row.get("temperature") or 0.5),
                trust=float(row.get("trust") or 0.5),
                season=row.get("season") or "spring",
                narrative=row.get("narrative") or "",
                shared_culture=culture if isinstance(culture, list) else [],
            )
        return self.state

    async def persist(self) -> None:
        await self.db.save_relationship(
            stage=self.state.stage,
            depth=self.state.depth,
            temperature=self.state.temperature,
            trust=self.state.trust,
            season=self.state.season,
            narrative=self.state.narrative,
            shared_culture=self.state.shared_culture,
        )

    async def on_user_message(self, message: str, now: datetime | None = None) -> dict:
        """
        处理一次用户消息对关系的影响。
        返回：{impact_multiplier, scar_created, stage_changed, old_stage, new_stage}
        """
        now = now or datetime.now()
        self._roll_day(now)
        self._had_interaction_today = True

        signals = assess_interaction(message)
        old_stage = self.state.stage
        result = {
            "impact_multiplier": 1.0,
            "scar_created": False,
            "stage_changed": False,
            "old_stage": old_stage,
            "new_stage": old_stage,
            "signals": signals,
        }

        # 深度
        d_inc = depth_increment(signals, self._depth_gained_today)
        self.state.depth = min(1.0, self.state.depth + d_inc)
        self._depth_gained_today += d_inc

        # 温度
        if signals.is_positive:
            self.state.temperature = min(1.0, self.state.temperature + 0.03)
        elif signals.is_negative:
            self.state.temperature = max(0.0, self.state.temperature - 0.08)
        else:
            self.state.temperature = min(1.0, self.state.temperature + 0.01)

        # 信任
        if signals.is_negative:
            trust_before = self.state.trust
            new_trust, should_scar = apply_negative_event(
                self.state.trust, signals.severity
            )
            damage = trust_before - new_trust
            self.state.trust = new_trust
            if should_scar:
                await self.db.save_scar(
                    origin_event=signals.event_desc or "一次伤人的话",
                    severity=damage,
                    trust_before=trust_before,
                )
                result["scar_created"] = True
        elif signals.is_positive or signals.self_disclosure > 0.4:
            self.state.trust = apply_positive_interaction(
                self.state.trust, signals.quality
            )

        # 阶段（只升不降）
        new_stage = check_stage_upgrade(
            self.state.stage, self.state.depth, self.state.trust
        )
        if new_stage != self.state.stage:
            self.state.stage = new_stage
            result["stage_changed"] = True
            result["new_stage"] = new_stage
            await self._refresh_narrative(old_stage, new_stage)

        await self.persist()
        return result

    async def _refresh_narrative(self, old_stage: str, new_stage: str) -> None:
        """阶段升迁时，用一两句更新关系叙事。"""
        fallback = (
            f"我们从{old_stage}走到了{new_stage}。"
            "不是突然变近，是一点点靠过来的。"
        )
        if self.llm is None:
            self.state.narrative = fallback
            return
        previous = self.state.narrative or "我们刚认识不久。"
        text = await self.llm.call(
            purpose="narrative",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是栖。用第一人称写一两句关系叙事。"
                        "诚实、克制，不要庆祝，不要客服腔。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"之前阶段：{old_stage}\n现在：{new_stage}\n"
                        f"上一句叙事：{previous}\n"
                        "请更新。"
                    ),
                },
            ],
            temperature=0.7,
        )
        self.state.narrative = (text or fallback).strip()[:200]

    async def on_scar_healed(self) -> None:
        self.state.trust = apply_scar_healed_bonus(self.state.trust)
        await self.persist()

    def stage_prompt_hint(self) -> str:
        hints = {
            "stranger": "你们刚认识。礼貌、好奇、小心翼翼。不要太亲昵，不要主动表达想念。",
            "acquaintance": "你们开始熟悉了。可以随意一点，偶尔开玩笑，但仍有分寸。",
            "friend": "你们已经是朋友。可以更放松，可以有小脾气，可以撒娇式表达。",
            "bonded": "关系很深。不必多话也能懂。语气自然、安静、有默契。",
        }
        return hints.get(self.state.stage, hints["stranger"])
