"""回合理解——单拍结构化认知（架构整顿 Phase 1）。

将处境弱信号、关系调制与 perception 评估收敛为单一对象，
供对话建卡与（后续阶段）路由计划复用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.core.perception import looks_like_typo_correction

if TYPE_CHECKING:
    from qi.core.brain import Brain
    from qi.core.emotion import EmotionState

# 实质问句：语言学形态，非场景关键词（懂意思铁律）
_SUBSTANTIVE_QUESTION_RE = re.compile(
    r"[?？]$|"
    r"(吗|么|呢)[。！]?$|"
    r"(你觉得|你认为|会不会|有没有|是不是|能否|可以吗|怎么看|意味着什么)"
)


def looks_like_substantive_question(text: str) -> bool:
    """用户在问需要认真回应的实质问题（形态启发，非话题表）。"""
    t = (text or "").strip()
    if len(t) < 4:
        return False
    return bool(_SUBSTANTIVE_QUESTION_RE.search(t))


@dataclass
class SituationHints:
    """对话处境弱信号（供表达调制，非独立路由入口）。"""

    hour: int = 0
    late_night: bool = False
    user_disclosure: bool = False
    user_request: bool = False
    user_comfort: bool = False
    user_typo_correction: bool = False
    user_substantive_question: bool = False
    emotional_aftershock: bool = False


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
        user_substantive_question=looks_like_substantive_question(text),
    )


def apply_turn_emotion_modulation(
    tu: TurnUnderstanding,
    *,
    valence_before: float,
    valence_after: float,
) -> None:
    """情绪余波：bonded 下显著负冲击或效价下挫 → 标记 aftershock（非场景表）。"""
    if not tu.relationship.bonded:
        return
    assessment = tu.perception_assessment
    impact = float(getattr(assessment, "impact", 0.0) or 0.0)
    if impact < -0.08 or valence_after < valence_before - 0.1:
        tu.situation.emotional_aftershock = True


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
    if tu.situation.user_substantive_question:
        tags.append("user_substantive_question")
    if tu.situation.emotional_aftershock:
        tags.append("emotional_aftershock")
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
    if "user_substantive_question" in tags:
        parts.append(
            "用户在问实质问题；诚实作答，可引用卡内 state 描述此刻感受，"
            "勿说「想了很久/那天你说」等无出处的过程或共同史。"
        )
    if "emotional_aftershock" in tags:
        parts.append(
            "上一拍情绪余波仍在；语气可略短、略静，勿立刻跳回轻巧闲聊。"
        )
    return " ".join(parts)


def apply_dialogue_modulation(card, extras: dict[str, str]) -> None:
    """根据回合处境弱信号调制意向卡（非场景 regex 包）。"""
    from qi.core.intention import Material

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
    if "user_substantive_question" in tags:
        present = (extras.get("present_emotion") or "").strip()
        has_state = any(
            m.tag == "state" and (m.text or "").strip() for m in card.materials
        )
        has_fact_mem = any(
            m.tag in ("memory", "fact") and (m.text or "").strip()
            for m in card.materials
        )
        if present and not has_state:
            card.materials.append(Material(tag="state", text=present[:80]))
        if not has_fact_mem and card.act == "free_talk":
            card.act = "acknowledge"
        line = (
            "实质问句：诚实作答；可引用卡内 state 说此刻感受，"
            "勿编造思考时长或共同回忆。"
        )
        if line not in card.must:
            card.must.append(line)
    if "emotional_aftershock" in tags:
        if card.length == "normal":
            card.length = "short"
        line = "情绪余波仍在；略短略静，勿立刻装作无事。"
        if line not in card.must:
            card.must.append(line)


async def note_emotional_residue(
    brain: Brain,
    tu: TurnUnderstanding,
    *,
    valence_before: float,
    valence_after: float,
) -> None:
    """显著情绪冲击后写入 open loop（心事余波，供后续内在生命）。"""
    apply_turn_emotion_modulation(
        tu, valence_before=valence_before, valence_after=valence_after
    )
    if not tu.situation.emotional_aftershock or brain._db is None:
        return
    try:
        from qi.core.intention import short_emotion_label
        from qi.memory.open_loops import OpenLoopQueue

        q = OpenLoopQueue(brain._db)
        await q.load()
        seed = short_emotion_label(brain.emotion)
        await q.enqueue("emotion_surge", seed=seed or "动")
    except Exception:
        pass
