"""回合理解——单拍结构化认知（架构整顿 Phase 1）。

将处境弱信号、关系调制与 perception 评估收敛为单一对象，
供对话建卡与（后续阶段）路由计划复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.core.perception import looks_like_typo_correction

if TYPE_CHECKING:
    from qi.core.brain import Brain


@dataclass
class SituationHints:
    """对话处境弱信号（供表达调制，非独立路由入口）。"""

    hour: int = 0
    late_night: bool = False
    user_disclosure: bool = False
    user_request: bool = False
    user_comfort: bool = False
    user_typo_correction: bool = False


@dataclass
class RelationshipModulation:
    stage: str = "stranger"
    bonded: bool = False


@dataclass
class TurnUnderstanding:
    user_message: str
    now: datetime
    situation: SituationHints = field(default_factory=SituationHints)
    relationship: RelationshipModulation = field(
        default_factory=RelationshipModulation
    )
    perception_assessment: Any | None = None


def infer_situation_hints(
    text: str,
    now: datetime,
    *,
    perception_intent: str | None = None,
) -> SituationHints:
    """从时钟与 perception intent 推断处境（不用话题关键词表）。"""
    hour = now.hour
    late = hour < 5 or hour >= 23
    intent = (perception_intent or "").strip().lower()
    return SituationHints(
        hour=hour,
        late_night=late,
        user_disclosure=intent == "disclosure",
        user_request=intent == "request",
        user_comfort=intent == "comfort",
        user_typo_correction=looks_like_typo_correction(text),
    )


def infer_relationship_modulation(stage: str) -> RelationshipModulation:
    s = (stage or "stranger").strip().lower()
    return RelationshipModulation(stage=s, bonded=s == "bonded")


async def prepare_dialogue_turn(
    brain: Brain,
    text: str,
    now: datetime | None = None,
) -> TurnUnderstanding:
    """组装当拍理解（读 brain 已有 perception.last_assessment）。"""
    ts = now or datetime.now()
    assessment = getattr(brain.perception, "last_assessment", None)
    intent = getattr(assessment, "intent", None) if assessment else None
    situation = infer_situation_hints(text, ts, perception_intent=intent)
    rel = infer_relationship_modulation(
        getattr(brain, "relationship_stage", "stranger")
    )
    return TurnUnderstanding(
        user_message=text,
        now=ts,
        situation=situation,
        relationship=rel,
        perception_assessment=assessment,
    )


async def assess_and_prepare_turn(
    brain: Brain,
    text: str,
    now: datetime | None = None,
) -> TurnUnderstanding:
    """路由前 assess perception，写入 last_assessment 并返回 TurnUnderstanding。"""
    ts = now or datetime.now()
    recent: list[dict] = []
    if brain.memory is not None:
        recent = brain.memory.working.get_context()
    elif brain._db is not None:
        from qi.stasis.ledger import MEM_RETRIEVAL_TOKEN_COST

        recent = await brain._db.load_recent_messages(limit=5)
        brain._ledger_safe_add_tokens(MEM_RETRIEVAL_TOKEN_COST)
    await brain.perception.assess_impact_async(
        text,
        brain.emotion,
        brain.relationship_stage,
        recent_messages=recent,
    )
    return await prepare_dialogue_turn(brain, text, ts)


def turn_understanding_to_extras(tu: TurnUnderstanding) -> dict[str, str]:
    """供 intention / expression extras 注入。"""
    tags: list[str] = []
    if tu.situation.late_night:
        tags.append("late_night")
    if tu.situation.user_disclosure:
        tags.append("user_disclosure")
    if tu.situation.user_request:
        tags.append("user_request")
    if tu.situation.user_comfort:
        tags.append("user_comfort")
    if tu.relationship.bonded:
        tags.append("bonded")
    if tu.situation.user_typo_correction:
        tags.append("user_typo_correction")
    extras: dict[str, str] = {}
    if tags:
        extras["turn_situation"] = ",".join(tags)
    assessment = tu.perception_assessment
    intent = getattr(assessment, "intent", None) if assessment else None
    if intent:
        extras["perception_intent"] = str(intent)
    return extras


def _parse_turn_situation_tags(extras: dict[str, str]) -> set[str]:
    raw = (extras.get("turn_situation") or "").strip()
    if not raw:
        return set()
    return {t.strip() for t in raw.split(",") if t.strip()}


def turn_situation_expression_hint(extras: dict[str, str]) -> str:
    """处境弱信号 → 表达层 system 补充（非固定台词）。"""
    tags = _parse_turn_situation_tags(extras)
    if not tags:
        return ""
    parts: list[str] = []
    if "user_disclosure" in tags and "bonded" in tags:
        parts.append("恋人在向你吐露自身状态；语气亲近，先接住再回应。")
    if "user_disclosure" in tags and "late_night" in tags:
        parts.append("深夜语境：可自然表达对身体或休息的在乎，勿空泛宣告在场。")
    if "user_comfort" in tags:
        parts.append("用户在寻求安慰；先回应情绪，再展开。")
    if "user_typo_correction" in tags:
        parts.append(
            "用户在纠正笔误或澄清本意；轻声确认即可，勿调侃「被抓到」「说中了」。"
        )
    return " ".join(parts)


def apply_dialogue_modulation(card, extras: dict[str, str]) -> None:
    """根据回合处境弱信号调制意向卡（非场景 regex 包）。"""
    tags = _parse_turn_situation_tags(extras)
    if not tags:
        return
    if "user_disclosure" in tags and "bonded" in tags:
        if card.stance in ("自然", "平和", ""):
            card.stance = "亲近、关切"
    if "user_disclosure" in tags and "late_night" in tags:
        line = (
            "对方在深夜吐露自己的状态；先自然接住，可表达对身体或休息的在乎，"
            "勿只用「我知道你在」类宣告了事。"
        )
        if line not in card.must:
            card.must.append(line)
    if "user_typo_correction" in tags:
        if card.act == "take_tease":
            card.act = "acknowledge"
        line = (
            "用户在纠正笔误或澄清本意；平静接住即可，"
            "不要调侃「被抓到」「说中了」或当成互相拆台。"
        )
        if line not in card.must:
            card.must.append(line)
