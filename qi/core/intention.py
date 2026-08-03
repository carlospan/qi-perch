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
# 方法/施教类追问（仅 has_mem 时转 recall）
_METHOD_RECALL_RE = re.compile(
    r"教过我|教了我|你教过|教你过|教过你|我教你|怎么做的|那个方法"
)

# 叙事第一人称「我」=栖；「我教了他」→ taught_by_qi（复核钉死）
_TAUGHT_BY_QI_RE = re.compile(r"我教了|我教过|栖教|教了他|教了你|教过他|教过你")
_LEARNED_FROM_USER_RE = re.compile(r"他教我|他教了|你教我|你教了|用户教")

_INVERT_TAUGHT_BY_QI_RE = re.compile(
    r"你教我|你告诉我(?:方法|怎么)|你教过我|你教了我"
)
_SELF_VIEW_RE = re.compile(r"喜欢自己|讨厌自己|恨自己|爱死|觉得自己")

_MUST_RECALL_RELATION = (
    "回忆类回答以记忆内容为唯一事实源；若用户当轮措辞与记忆主客体关系相反"
    "（如用户说「你教我」但记忆是「我教你」），以记忆为准，澄清而非附和"
)
_MUST_SHARE_STATE_ANCHOR = (
    "主动开口的自我认知结论（如「喜欢自己」/「难过」/「平静」）必须与卡内"
    " state 素材一致；状态数据不支持的结论不得凭空拔高或下沉"
)

_RELATION_HINT = {
    "taught_by_qi": "施教关系：栖教用户，不要反转",
    "learned_from_user": "施教关系：用户教栖，不要反转",
    "mutual": "施教关系：互相教过，以记忆原文为准",
}

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
    tag: str  # fact | memory | state | loop | none | cue | relation
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
    recall_relation: str | None = None  # taught_by_qi | learned_from_user | mutual

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntentionCard:
        mats = [
            Material(tag=str(m.get("tag") or "none"), text=str(m.get("text") or ""))
            for m in (data.get("materials") or [])
            if isinstance(m, dict)
        ]
        rel = data.get("recall_relation")
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
            recall_relation=str(rel) if rel else None,
        )

    def materials_block(self) -> str:
        if not self.materials:
            return "- none：（无可用事实素材）"
        lines = []
        for m in self.materials:
            text = (m.text or "").strip() or "（空）"
            lines.append(f"- {m.tag}：{text}")
        if self.recall_relation and self.recall_relation in _RELATION_HINT:
            # 段 A 可见：方案 A——并入 materials 块，不增模板占位
            hint = _RELATION_HINT[self.recall_relation]
            if not any(m.tag == "relation" for m in self.materials):
                lines.append(f"- relation：{hint}")
        return "\n".join(lines)

    def must_block(self) -> str:
        if not self.must:
            return "- （无额外约束）"
        return "\n".join(f"- {m}" for m in self.must)

    def primary_text(self) -> str:
        for m in self.materials:
            if m.tag not in ("none", "relation") and (m.text or "").strip():
                return m.text.strip()
        return ""

    def state_material_blob(self) -> str:
        """state/loop 素材拼成可检索支撑文本。"""
        parts = [
            (m.text or "").strip()
            for m in self.materials
            if m.tag in ("state", "loop") and (m.text or "").strip()
        ]
        return "\n".join(parts)


def looks_like_remember_question(text: str) -> bool:
    return bool(_REMEMBER_RE.search(text or ""))


def looks_like_method_recall(text: str) -> bool:
    """方法/施教类追问——有 memory 时才应转 recall。"""
    return bool(_METHOD_RECALL_RE.search(text or ""))


def looks_like_recall_probe(text: str) -> bool:
    return looks_like_remember_question(text) or looks_like_method_recall(text)


def infer_recall_relation(memories: list[dict] | None) -> str | None:
    """从记忆原文/元数据推断施教方向；冲突或不足则 None。

    叙事视角：「我」=栖。例：「他提到晚上睡不着，我教了他一个方法」→ taught_by_qi。
    """
    if not memories:
        return None
    qi_hits = 0
    user_hits = 0
    for m in memories:
        explicit = m.get("recall_relation") or (m.get("metadata") or {}).get(
            "recall_relation"
        )
        if explicit in ("taught_by_qi", "learned_from_user", "mutual"):
            return str(explicit)
        content = str(m.get("content") or "")
        role_map = m.get("role_map")
        if isinstance(role_map, dict):
            # 若有显式 teacher 字段则优先
            teacher = role_map.get("teacher") or role_map.get("taught_by")
            if teacher in ("qi", "栖", "self"):
                qi_hits += 2
            elif teacher in ("user", "他", "用户"):
                user_hits += 2
        if _TAUGHT_BY_QI_RE.search(content):
            qi_hits += 1
        if _LEARNED_FROM_USER_RE.search(content):
            user_hits += 1
    if qi_hits > 0 and user_hits > 0:
        return None
    if qi_hits > 0:
        return "taught_by_qi"
    if user_hits > 0:
        return "learned_from_user"
    return None


_TOPIC_RE = re.compile(r"教|方法|入睡|睡不着|呼吸|睡")
_SLEEP_ADVICE_RE = re.compile(r"躺着|不强迫|看天花板|允许自己")
# 对话视角：用户自称在教栖（与叙事视角的 _LEARNED_FROM_USER_RE 互补）
_USER_TEACHES_QI_RE = re.compile(r"我教你|我教了你|教你一个|教给你|跟我学")
# 用户承认「你（栖）教了我」——佐证 taught_by_qi，不是 learned_from_user
_USER_ACK_QI_TAUGHT_RE = re.compile(r"你教了我|你教过我|你教的(?:那个)?方法")


def _is_qi_role(role: str) -> bool:
    return role in ("qi", "assistant")


def anchor_teaching_relation(messages: list[dict]) -> str:
    """从真实对话（含 role 的 messages）推断助眠/施教方向，返回一句话锚定。

    只读 messages，不写库。无相关话题返回空串。
    - 扫含「教/方法/入睡/睡不着/呼吸/睡」的 user/assistant 消息；
    - assistant/qi（栖）对用户说助眠建议（躺着/不强迫/看天花板/允许自己）→ taught_by_qi；
    - user 说「我教你/教给你」且栖发言有话题佐证 → learned_from_user；
    - 冲突或不足 → 返回空串（不锚定，不瞎猜）。
    """
    if not messages:
        return ""

    topic_msgs = [
        m
        for m in messages
        if isinstance(m, dict) and _TOPIC_RE.search(str(m.get("content") or ""))
    ]
    if not topic_msgs:
        return ""

    qi_hits = 0
    user_hits = 0
    sleep_quotes: list[str] = []
    qi_topic_ok = False

    for m in topic_msgs:
        role = str(m.get("role") or "")
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if _is_qi_role(role):
            qi_topic_ok = True
            if _SLEEP_ADVICE_RE.search(content):
                qi_hits += 2
                sleep_quotes.append(content[:60])
            if _TAUGHT_BY_QI_RE.search(content):
                qi_hits += 1
        elif role == "user":
            if _USER_ACK_QI_TAUGHT_RE.search(content):
                qi_hits += 1
            if _USER_TEACHES_QI_RE.search(content):
                user_hits += 2
            # 叙事口吻残留（少见）：「你教我」若出自用户则是承认栖教，已由 ACK 覆盖

    # learned_from_user 需栖侧话题佐证，避免单句瞎猜
    if user_hits > 0 and not qi_topic_ok:
        user_hits = 0

    if qi_hits > 0 and user_hits > 0:
        return ""
    if qi_hits > 0:
        quote = "、".join(sleep_quotes[:2]) if sleep_quotes else "（见近聊助眠建议）"
        # 显式排除易漂移虚构细节；含 taught_by_qi 便于验收断言
        return (
            f"关于入睡方法：是你（栖）教给用户的，不是用户教你的；"
            f"原话是「{quote}」，没有「数呼吸/数到七」。"
            f"{_RELATION_HINT['taught_by_qi']}（taught_by_qi）"
        )
    if user_hits > 0:
        return (
            f"关于方法：是用户教给你（栖）的，不是你教用户的。"
            f"{_RELATION_HINT['learned_from_user']}（learned_from_user）"
        )
    return ""


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


_SHORT_FEEDBACK_RE = re.compile(
    r"直接一点|简短|别绕|长话短说|说重点|简单点"
)


def looks_like_short_feedback(text: str) -> bool:
    """用户要求简短/直接——表达层应压长度。"""
    return bool(_SHORT_FEEDBACK_RE.search(text or ""))


def _base_must(
    act: str,
    *,
    pretend_ok: bool,
    channel: str = "dialogue",
    recall_relation: str | None = None,
) -> list[str]:
    must = [
        "不编造意向卡素材之外的事实",
        "不假装有心跳、呼吸、感官在场",
    ]
    if act == "honest_hurt":
        must.append("接住伤害，不反击升级，不讨好假笑")
    if act == "share_state":
        must.append("只说卡内状态或心事，不汇报系统")
        if channel == "proactive":
            must.append(_MUST_SHARE_STATE_ANCHOR)
    if act == "take_tease":
        must.append("接住玩笑，不认真训人")
    if act in ("answer", "recall") and not pretend_ok:
        must.append("不假装记得")
    if act == "answer" and pretend_ok is False:
        must.append("不知道就说不知道")
    # 补丁 B：顺带提记忆（answer/free_talk）也注入施教关系底线
    if act == "recall" or (recall_relation and act in ("answer", "free_talk")):
        must.append(_MUST_RECALL_RELATION)
        must.append("施教关系以卡内 relation 为准，不得反转")
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
    recall_relation: str | None = None

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
        remember_q = looks_like_recall_probe(text)
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
            recall_relation = infer_recall_relation(memories)
            source_parts.append(f"mem={len(materials)}")
            if recall_relation:
                source_parts.append(f"rel={recall_relation}")
        elif intent == "request" and facts_useful and not has_mem:
            act = "answer"
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
            if has_mem:
                recall_relation = infer_recall_relation(memories)
                if recall_relation:
                    source_parts.append(f"rel={recall_relation}")
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
        m.tag not in ("none", "relation") and (m.text or "").strip()
        for m in materials
    )
    pretend_ok = has_real_material
    must = _base_must(
        act,
        pretend_ok=pretend_ok,
        channel=channel,
        recall_relation=recall_relation,
    )
    if act == "answer" and not has_real_material:
        if "不知道就说不知道" not in must:
            must.append("不知道就说不知道")
        if "不假装记得" not in must:
            must.append("不假装记得")
    # relation 未推断出时，仍保留「以记忆为准」；去掉「以卡内 relation 为准」以免空指
    if act == "recall" and not recall_relation:
        must = [m for m in must if "以卡内 relation 为准" not in m]

    length = _length_for(emotion, relationship_stage, act)
    if channel == "dialogue" and looks_like_short_feedback(text):
        length = "short"
        must = list(must)
        if "用 1-2 句、克制长度，不超过 60 字" not in must:
            must.append("用 1-2 句、克制长度，不超过 60 字")
        source_parts.append("short_feedback")
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
        recall_relation=recall_relation,
    )


def assert_reply_respects_card(
    reply: str,
    card: IntentionCard,
    *,
    banned_names: list[str] | None = None,
) -> list[str]:
    """
    N5 辅助断言。返回违规列表（空=通过）。
    硬闸：专名黑名单、伪记忆、施教反转。
    软检（仅 trace 用途，本函数不阻断 LLM）：主动 share_state 无支撑自我认知。
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
    if card.recall_relation == "taught_by_qi" and _INVERT_TAUGHT_BY_QI_RE.search(
        text
    ):
        violations.append("施教关系反转")
    if (
        card.channel == "proactive"
        and card.act == "share_state"
        and _SELF_VIEW_RE.search(text)
    ):
        blob = card.state_material_blob()
        # 素材未包含同类自我认知词 → 无支撑
        if not _SELF_VIEW_RE.search(blob):
            violations.append("无支撑自我认知结论")
    return violations
