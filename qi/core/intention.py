"""表达意向卡——规则引擎产出导演指示；零 LLM。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.core.perception import ImpactAssessment

LAST_INTENTION_KEY = "last_intention"

_REMEMBER_RE = re.compile(r"还记得|记得吗|记不记得|你还记得")

_INTENT_DEFAULT_ACT = {
    "request": "answer",
    "disclosure": "acknowledge",
    "comfort": "comfort_back",
    "tease": "take_tease",
    "hurt": "honest_hurt",
    "neutral": "free_talk",
}


@dataclass
class Material:
    tag: str  # fact | memory | state | loop | none | cue
    text: str


@dataclass
class IntentionCard:
    """导演给演员的指示，不是台词本。"""

    act: str
    topic: str
    materials: list[Material] = field(default_factory=list)
    stance: str = "自然"
    must: list[str] = field(default_factory=list)
    length: str = "normal"  # short | normal
    source: str = ""
    channel: str = "dialogue"  # dialogue | proactive
    silence: bool = False
    outcome: str | None = None  # llm | template | empty | silence；建卡后回填

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentionCard:
        mats = [
            Material(tag=str(m.get("tag") or "none"), text=str(m.get("text") or ""))
            for m in (data.get("materials") or [])
            if isinstance(m, dict)
        ]
        return cls(
            act=str(data.get("act") or "free_talk"),
            topic=str(data.get("topic") or ""),
            materials=mats,
            stance=str(data.get("stance") or "自然"),
            must=list(data.get("must") or []),
            length=str(data.get("length") or "normal"),
            source=str(data.get("source") or ""),
            channel=str(data.get("channel") or "dialogue"),
            silence=bool(data.get("silence")),
            outcome=data.get("outcome"),
        )

    def materials_block(self) -> str:
        if not self.materials:
            return "- none：（无可用事实素材）"
        lines = []
        for m in self.materials:
            text = (m.text or "").strip() or "（空）"
            lines.append(f"- {m.tag}：{text}")
        return "\n".join(lines)

    def must_block(self) -> str:
        if not self.must:
            return "- （无额外约束）"
        return "\n".join(f"- {m}" for m in self.must)

    def primary_text(self) -> str:
        for m in self.materials:
            if m.tag != "none" and (m.text or "").strip():
                return m.text.strip()
        return ""


def looks_like_remember_question(text: str) -> bool:
    return bool(_REMEMBER_RE.search(text or ""))


def _short_emotion(emotion: EmotionState) -> str:
    desc = emotion.description()
    if len(desc) > 24:
        return desc[:24] + "…"
    return desc or "平静"


def _stance_for(
    emotion: EmotionState,
    stage: str,
    act: str,
) -> str:
    parts = [_short_emotion(emotion)]
    if stage == "stranger":
        parts.append("克制礼貌")
    elif stage == "bonded":
        parts.append("更近一点")
    elif stage == "friend":
        parts.append("轻松些")
    if emotion.energy < 0.35:
        parts.append("偏短")
    if act == "honest_hurt":
        parts.append("受伤但诚实")
    elif act == "take_tease":
        parts.append("接得住玩笑" if stage != "stranger" else "礼貌接住")
    elif act == "share_state":
        parts.append("轻轻说自己")
    return " / ".join(parts)


def _length_for(emotion: EmotionState, stage: str, act: str) -> str:
    if act == "honest_hurt":
        return "short"
    if emotion.energy < 0.35:
        return "short"
    if stage == "stranger":
        return "short"
    return "normal"


def _base_must(act: str, *, pretend_ok: bool) -> list[str]:
    must = [
        "不编造意向卡素材之外的事实",
        "不假装有心跳、呼吸、感官在场",
    ]
    if act == "honest_hurt":
        must.append("接住伤害，不反击升级，不讨好假笑")
    if act == "share_state":
        must.append("只说卡内状态或心事，不汇报系统")
    if act == "take_tease":
        must.append("接住玩笑，不认真训人")
    if act in ("answer", "recall") and not pretend_ok:
        must.append("不假装记得")
    if act == "answer" and pretend_ok is False:
        must.append("不知道就说不知道")
    return must


def build_intention_card(
    *,
    channel: str,
    user_message: str,
    emotion: EmotionState,
    relationship_stage: str,
    assessment: ImpactAssessment | None = None,
    memories: list[dict] | None = None,
    extras: dict[str, str] | None = None,
    open_loops: list[dict] | None = None,
    proactive_kind: str | None = None,
) -> IntentionCard:
    """从已有器官状态建卡——决策内生，不问 LLM。"""
    extras = extras or {}
    memories = memories or []
    loops = open_loops or []
    text = (user_message or "").strip()
    intent = None
    if assessment is not None:
        intent = assessment.intent

    materials: list[Material] = []
    act = "free_talk"
    topic = text[:40] if text else "（无明确话题）"
    source_parts: list[str] = [f"channel={channel}"]

    if channel == "proactive":
        source_parts.append(f"kind={proactive_kind or '?'}")
        if loops:
            loop = loops[0]
            act = "share_state"
            concern = str(loop.get("concern") or "")[:80]
            materials.append(Material(tag="loop", text=concern))
            topic = concern[:40] or "心里有件事"
            source_parts.append(f"loop={loop.get('id')}")
        elif proactive_kind == "express_feeling":
            act = "share_state"
            materials.append(
                Material(tag="state", text=_short_emotion(emotion))
            )
            topic = "想轻轻说一句自己的状态"
        else:
            act = "free_talk"
            topic = "轻轻搭一句话" if proactive_kind == "reach_out" else "轻轻关心一句"
            materials.append(Material(tag="cue", text=text[:60] if text else topic))
    else:
        source_parts.append(f"intent={intent or 'none'}")
        default_act = _INTENT_DEFAULT_ACT.get(intent or "neutral", "free_talk")
        remember_q = looks_like_remember_question(text)
        has_mem = bool(memories)
        facts = extras.get("user_facts") or ""
        facts_useful = bool(
            facts
            and "还不太了解" not in facts
            and facts.strip() not in ("", "（你还不太了解他）")
        )

        if remember_q and not has_mem and not facts_useful:
            act = "answer"
            materials.append(Material(tag="none", text=""))
            source_parts.append("remember_miss")
        elif has_mem and (intent == "request" or remember_q):
            act = "recall"
            for m in memories[:2]:
                content = str(m.get("content") or "").strip()[:100]
                if content:
                    materials.append(Material(tag="memory", text=content))
            source_parts.append(f"mem={len(materials)}")
        elif intent == "request" and facts_useful and not has_mem:
            act = "answer"
            # 取 facts 首行非空
            line = ""
            for raw in facts.splitlines():
                s = raw.strip().lstrip("- ").strip()
                if s and not s.startswith("（"):
                    line = s[:100]
                    break
            if line:
                materials.append(Material(tag="fact", text=line))
            else:
                materials.append(Material(tag="none", text=""))
        else:
            act = default_act
            if has_mem and act in ("free_talk", "acknowledge", "answer"):
                content = str(memories[0].get("content") or "").strip()[:80]
                if content and act == "answer":
                    materials.append(Material(tag="memory", text=content))
            if not materials:
                if act == "share_state":
                    materials.append(
                        Material(tag="state", text=_short_emotion(emotion))
                    )
                else:
                    materials.append(Material(tag="none", text=""))

    if not materials:
        materials.append(Material(tag="none", text=""))

    has_real_material = any(
        m.tag != "none" and (m.text or "").strip() for m in materials
    )
    pretend_ok = has_real_material  # 有素材才允许「记得」类表述
    # answer+none：不知道；remember_miss：不假装记得
    must = _base_must(act, pretend_ok=pretend_ok)
    if act == "answer" and not has_real_material:
        if "不知道就说不知道" not in must:
            must.append("不知道就说不知道")
        if "不假装记得" not in must:
            must.append("不假装记得")

    length = _length_for(emotion, relationship_stage, act)
    stance = _stance_for(emotion, relationship_stage, act)
    source_parts.append(f"act={act}")
    source_parts.append(f"stage={relationship_stage}")

    return IntentionCard(
        act=act,
        topic=topic,
        materials=materials,
        stance=stance,
        must=must,
        length=length,
        source="; ".join(source_parts),
        channel=channel,
        silence=False,
        outcome=None,
    )


def assert_reply_respects_card(
    reply: str,
    card: IntentionCard,
    *,
    banned_names: list[str] | None = None,
) -> list[str]:
    """
    N5 辅助断言。返回违规列表（空=通过）。
    硬闸场景：模板路径 + 专名黑名单；「不假装记得」句式。
    """
    violations: list[str] = []
    text = reply or ""
    for name in banned_names or []:
        if name and name in text:
            violations.append(f"卡外专名:{name}")
    if any("不假装记得" in m for m in card.must):
        if re.search(r"你(那天|之前|曾经)?(说过|提到过|跟我说)", text):
            if not card.primary_text():
                violations.append("伪记忆句式")
    return violations
