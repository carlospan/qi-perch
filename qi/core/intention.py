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
_METHOD_RECALL_RE = re.compile(r"教过我|教了我|你教过|教你过|教过你|我教你|怎么做的|那个方法")

# 叙事第一人称「我」=栖；「我教了他」→ taught_by_qi（复核钉死）
_TAUGHT_BY_QI_RE = re.compile(r"我教了|我教过|栖教|教了他|教了你|教过他|教过你")
_LEARNED_FROM_USER_RE = re.compile(r"他教我|他教了|你教我|你教了|用户教")

_INVERT_TAUGHT_BY_QI_RE = re.compile(
    # 「你教给我」口语高频；旧闸只认「你教我/教过我/教了我」会漏 #1377
    r"你(?:之前|曾经|那天|那次)?(?:教给(?:过|了)?我|教(?:过|了)?我)"
    r"|你告诉我(?:方法|怎么)"
    r"|你教我的(?:那个)?(?:法子|方法)?"
)
_SELF_VIEW_RE = re.compile(r"喜欢自己|讨厌自己|恨自己|爱死|觉得自己")

_MUST_RECALL_RELATION = (
    "回忆类回答以记忆内容为唯一事实源；若用户当轮措辞与记忆主客体关系相反"
    "（如用户说「你教我」但记忆是「我教你」），以记忆为准，澄清而非附和"
)
_MUST_NO_FABRICATE_SHARED = (
    "无卡内 memory/fact 素材时：不编造共同回忆"
    "（如「你教过我」「你教给我」「那天你说过」「我试了你教的方法」）；不知道就说不知道或不提起"
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
    # 可观测：检索是否命中（分析/溯源用；不进 prompt）
    evidence: dict[str, Any] = field(default_factory=dict)

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
            evidence=dict(data.get("evidence") or {})
            if isinstance(data.get("evidence"), dict)
            else {},
        )

    def materials_block(self) -> str:
        """原文短引（≤80 字/条）+ 诚实边界；不做生动扩写。"""
        if not self.materials:
            body = "- none：（无可用事实素材）"
        else:
            lines = []
            for m in self.materials:
                text = (m.text or "").strip() or "（空）"
                if len(text) > 80:
                    text = text[:80].rstrip() + "…"
                lines.append(f"- {m.tag}：{text}")
            if self.recall_relation and self.recall_relation in _RELATION_HINT:
                # 段 A 可见：方案 A——并入 materials 块，不增模板占位
                hint = _RELATION_HINT[self.recall_relation]
                if not any(m.tag == "relation" for m in self.materials):
                    lines.append(f"- relation：{hint}")
            body = "\n".join(lines)
        return (
            "【你此刻知道的事】\n"
            f"{body}\n"
            "【诚实边界】你此刻知道的人和事仅有以上。"
            "若想引用「那晚/那天/你说过/我问过…」类的共同回忆——"
            "请确认以上素材中确实有那段对话；若不确定，请不要假装记得。"
            "不确定时可以用意象、比喻或诚实地说「我不确定」。"
        )

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
        explicit = m.get("recall_relation") or (m.get("metadata") or {}).get("recall_relation")
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


_TOPIC_RE = re.compile(r"教|方法|入睡|睡不着|助眠|失眠|法子")
# 对话视角：用户自称在教栖（与叙事视角的 _LEARNED_FROM_USER_RE 互补）
_USER_TEACHES_QI_RE = re.compile(r"我教你|我教了你|教你一个|教给你|跟我学")
# 用户承认「你（栖）教了我」——佐证 taught_by_qi，不是 learned_from_user
_USER_ACK_QI_TAUGHT_RE = re.compile(r"你教了我|你教过我|你教的(?:那个)?方法")
# 无卡时：反转句式 + 入睡/方法话题才拦（避免误伤其他真实请教）
_SLEEP_TOPIC_RE = re.compile(r"入睡|睡不着|失眠|睡")
_INVERT_TOPIC_RE = re.compile(r"入睡|睡不着|失眠|睡|方法|法子")
# facts 兜底：存档真值的方向匹配（「不是他教栖」的否定式须排除；
# 紧邻式匹配避免跨句误伤，如「栖教他的（…），不是他教栖」中的前一个「他」）
_FACT_QI_TEACH_RE = re.compile(r"栖[^。\n]{0,16}教")
_FACT_USER_TEACH_RE = re.compile(r"(?<!不是)他教栖|(?<!不是)用户教栖")


def detect_teach_inversion(text: str, *, recall_relation: str | None = None) -> bool:
    """回复里把施教方向说反了吗？（原 detect_sleep_teach_inversion）

    卡内 taught_by_qi：只查反转句式（不靠话题启发式）。
    无卡：反转句式 + 入睡/方法/法子 联判，避免误伤「你教我写代码」。
    实证：#1020/#1028/#1285（「你之前教过我一个法子」）。
    """
    t = str(text or "")
    if not t:
        return False
    if not _INVERT_TAUGHT_BY_QI_RE.search(t):
        return False
    if recall_relation == "taught_by_qi":
        return True
    return bool(_INVERT_TOPIC_RE.search(t))


# 向后兼容别名（包 15-17 测试可能引用旧名）
detect_sleep_teach_inversion = detect_teach_inversion


def _is_qi_role(role: str) -> bool:
    return role in ("qi", "assistant")


def anchor_teaching_relation(messages: list[dict], facts_text: str = "") -> str:
    """推断助眠/施教方向，返回一句话锚定。

    优先从真实对话（含 role 的 messages）推断；近聊无话题时回退 user_facts
    存档真值（如 tools/repair_teaching_fact.py 写入的方向事实）。
    只读不写库。无相关话题返回空串。
    """
    hint = _anchor_from_messages(messages)
    if hint:
        return hint
    return _anchor_from_facts(facts_text)


def _infer_relation_from_facts(facts_text: str) -> str | None:
    """从 user_facts 存档推断施教方向；冲突则 None。"""
    text = str(facts_text or "")
    if not text:
        return None
    qi_teach = bool(_FACT_QI_TEACH_RE.search(text))
    user_teach = bool(_FACT_USER_TEACH_RE.search(text))
    if qi_teach and user_teach:
        return None
    if qi_teach:
        return "taught_by_qi"
    if user_teach:
        return "learned_from_user"
    return None


def _anchor_from_facts(facts_text: str) -> str:
    """facts 兜底：近聊无话题可扫时，靠存档真值钉方向。"""
    text = str(facts_text or "")
    if not text:
        return ""
    qi_teach = _FACT_QI_TEACH_RE.search(text)
    user_teach = _FACT_USER_TEACH_RE.search(text)
    if qi_teach and user_teach:
        return ""
    if qi_teach:
        return (
            f"关于方法：是你（栖）教给用户的，不是用户教你的。"
            f"{_RELATION_HINT['taught_by_qi']}（taught_by_qi）"
        )
    if user_teach:
        return (
            f"关于方法：是用户教给你（栖）的，不是你教用户的。"
            f"{_RELATION_HINT['learned_from_user']}（learned_from_user）"
        )
    return ""


def _anchor_from_messages(messages: list[dict]) -> str:
    """从真实对话（含 role 的 messages）推断施教方向。

    - 扫含「教/方法/入睡/睡不着/助眠…」的 user/assistant 消息；
    - 话题窗扩一格以纳入夹在中间的栖发言；
    - 栖显式「我教了」强分；其它非敷衍栖发言弱分（不绑助眠词面）；
    - user 说「我教你/教给你」且栖发言有话题佐证 → learned_from_user；
    - 冲突或不足 → 返回空串（不锚定，不瞎猜）。
    """
    if not messages:
        return ""

    indexed = [(i, m) for i, m in enumerate(messages) if isinstance(m, dict)]
    topic_idxs = [i for i, m in indexed if _TOPIC_RE.search(str(m.get("content") or ""))]
    if not topic_idxs:
        return ""

    lo = max(0, min(topic_idxs) - 1)
    hi = min(len(messages) - 1, max(topic_idxs) + 1)
    topic_msgs = [messages[i] for i in range(lo, hi + 1) if isinstance(messages[i], dict)]

    qi_hits = 0
    user_hits = 0
    teach_quotes: list[str] = []
    qi_topic_ok = False

    def _qi_ack_only(text: str) -> bool:
        """敷衍附和不算栖施教证据（避免与「用户教栖」冲突）。"""
        if _TAUGHT_BY_QI_RE.search(text):
            return False
        if len(text) <= 24 and re.match(r"^(?:好的?|嗯+|收到)", text):
            return True
        return bool(re.match(r"^(?:好的?|嗯+).{0,12}记住", text))

    for m in topic_msgs:
        role = str(m.get("role") or "")
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if _is_qi_role(role):
            qi_topic_ok = True
            if _TAUGHT_BY_QI_RE.search(content):
                qi_hits += 2
                teach_quotes.append(content[:60])
            elif len(content) >= 8 and not _qi_ack_only(content):
                qi_hits += 1
                teach_quotes.append(content[:60])
        elif role == "user":
            if _USER_ACK_QI_TAUGHT_RE.search(content):
                qi_hits += 1
            if _USER_TEACHES_QI_RE.search(content):
                user_hits += 2

    # learned_from_user 需栖侧话题佐证，避免单句瞎猜
    if user_hits > 0 and not qi_topic_ok:
        user_hits = 0

    if qi_hits > 0 and user_hits > 0:
        return ""
    if qi_hits > 0:
        quote = "、".join(teach_quotes[:2]) if teach_quotes else "（见近聊相关发言）"
        return (
            f"关于方法：是你（栖）教给用户的，不是用户教你的；"
            f"原话是「{quote}」，不得添加原话没有的细节。"
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


_SHORT_FEEDBACK_RE = re.compile(r"直接一点|简短|别绕|长话短说|说重点|简单点")


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
            materials.append(Material(tag="state", text=_short_emotion(emotion)))
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
            facts and "还不太了解" not in facts and facts.strip() not in ("", "（你还不太了解他）")
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
            fact_rel = _infer_relation_from_facts(facts) if facts_useful else None
            if fact_rel:
                recall_relation = fact_rel
                source_parts.append(f"fact_rel={fact_rel}")
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
            # 存档真值优先于可能被污染的叙事检索（包15/17）
            fact_rel = _infer_relation_from_facts(facts) if facts_useful else None
            if fact_rel:
                recall_relation = fact_rel
                source_parts.append(f"fact_rel={fact_rel}")
            # N5：有检索命中则必须进卡（free_talk 也不例外）；仅 answer 才注入是旧洞
            # 若存档真值钉了方向而检索文含反转措辞，改用 facts 行进卡（防污染叙事当事实源）
            if has_mem and act in ("free_talk", "acknowledge", "answer"):
                content = str(memories[0].get("content") or "").strip()[:80]
                use_fact_instead = (
                    fact_rel == "taught_by_qi"
                    and content
                    and _INVERT_TAUGHT_BY_QI_RE.search(content)
                    and facts_useful
                )
                if use_fact_instead:
                    for raw in facts.splitlines():
                        s = raw.strip().lstrip("- ").strip()
                        if not s or s.startswith("（"):
                            continue
                        if _FACT_QI_TEACH_RE.search(s):
                            materials.append(Material(tag="fact", text=s[:100]))
                            source_parts.append("fact_over_polluted_mem")
                            break
                if not materials and content:
                    materials.append(Material(tag="memory", text=content))
                    source_parts.append("mem=1")
            # 近聊/话题触及施教且无 mem 时，用 facts 真值进卡（防空卡编共同史）
            if (
                not materials
                and facts_useful
                and (_TOPIC_RE.search(text) or looks_like_recall_probe(text))
            ):
                for raw in facts.splitlines():
                    s = raw.strip().lstrip("- ").strip()
                    if not s or s.startswith("（"):
                        continue
                    if _FACT_QI_TEACH_RE.search(s) or _FACT_USER_TEACH_RE.search(s):
                        materials.append(Material(tag="fact", text=s[:100]))
                        if not recall_relation:
                            recall_relation = _infer_relation_from_facts(s)
                        source_parts.append("fact_teach")
                        break
            if not materials:
                if act == "share_state":
                    materials.append(Material(tag="state", text=_short_emotion(emotion)))
                else:
                    materials.append(Material(tag="none", text=""))

    if not materials:
        materials.append(Material(tag="none", text=""))

    has_real_material = any(
        m.tag not in ("none", "relation") and (m.text or "").strip() for m in materials
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
    if channel == "dialogue" and not has_real_material:
        if _MUST_NO_FABRICATE_SHARED not in must:
            must.append(_MUST_NO_FABRICATE_SHARED)
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

    evidence: dict[str, Any] = {}
    if channel == "dialogue":
        evidence = {
            "has_mem": bool(memories),
            "mem_n": len(memories),
            "facts_useful": bool(
                (extras.get("user_facts") or "")
                and "还不太了解" not in (extras.get("user_facts") or "")
            ),
            "has_real_material": has_real_material,
            "recall_relation": recall_relation,
        }
        source_parts.append(f"has_mem={int(bool(memories))}")

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
        evidence=evidence,
    )


# ----- N5 硬闸扩展：共同回忆声明 + 实体一致性（包 N5）-----

# 确定回忆句式（不绑 must「不假装记得」；不含「你教我」——施教闸已覆盖）
_DECLARATIVE_MEMORY_RE = re.compile(
    r"那天|那晚|凌晨|你问过|你说过|你问我|你问「|你问『"
    r"|我说了|我说过|会问你|记得你那次|记得你曾经|上次你|记得那个凌晨"
)

_HARD_VIOLATION_PREFIXES = (
    "卡外专名:",
    "伪记忆句式",
    "施教关系反转",
    "空卡编造共同回忆",
    "虚构实体:",
    "共同回忆",
)

_ENTITY_WHITELIST: frozenset[str] = frozenset(
    {
        # 意象
        "深水",
        "石子",
        "树叶",
        "窗子",
        "羽毛",
        "涟漪",
        "余烬",
        "黄昏",
        "水面",
        "微风",
        "水底",
        "晴空",
        "薄云",
        "回音",
        "光线",
        "暗流",
        "缝隙",
        "树梢",
        "月光",
        "清晨",
        "叶子",
        # 情绪
        "安静",
        "温柔",
        "紧张",
        "珍惜",
        "愿意",
        "恍惚",
        "酸涩",
        "柔软",
        "低落",
        "平静",
        # 功能词
        "谢谢",
        "可以",
        "不确定",
        "对不起",
        "没关系",
        "好像",
        "也许",
        "大概",
        "记得",
        "不知道",
    }
)

_HAN_NGRAM_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")
_BOOK_TITLE_RE = re.compile(r"《([^》]+)》")
_CALLED_NAME_RE = re.compile(r"叫([\u4e00-\u9fff]{2,4})(?:的|，|。|？|！|$)")


def is_hard_violation(violation: str) -> bool:
    """HARD 闸：expression 重生/模板；SOFT 不进此判断。"""
    v = violation or ""
    return any(v.startswith(p) for p in _HARD_VIOLATION_PREFIXES)


def _normalize_for_match(s: str) -> str:
    s = s or ""
    s = re.sub(r"[\s\W_]+", "", s, flags=re.UNICODE)
    return s.lower()


def _card_has_real_material(card: IntentionCard) -> bool:
    return any(m.tag in ("memory", "fact") and (m.text or "").strip() for m in card.materials)


def _materials_blob(materials: list[Material]) -> str:
    return "".join((m.text or "") for m in materials)


def _key_phrase_in_materials(text: str, materials: list[Material]) -> bool:
    """声明中的关键短语（引号内容或匹配后子句）须能在 materials 中子串命中。"""
    blob = _normalize_for_match(_materials_blob(materials))
    if not blob:
        return False
    for q in re.findall(r"[「『\"“]([^」』\"”]+)[」』\"”]", text or ""):
        nq = _normalize_for_match(q)
        if len(nq) >= 2 and nq in blob:
            return True
    m = _DECLARATIVE_MEMORY_RE.search(text or "")
    if not m:
        return True
    rest = (text or "")[m.end() :]
    clause = re.split(r"[。？！?\n]", rest, maxsplit=1)[0]
    norm = _normalize_for_match(clause)
    if len(norm) > 15:
        norm = norm[:15]
    if len(norm) >= 3 and norm in blob:
        return True
    for i in range(0, max(0, len(norm) - 3)):
        if norm[i : i + 4] in blob:
            return True
    return False


def _build_known_set(materials: list[Material]) -> set[str]:
    known: set[str] = set(_ENTITY_WHITELIST)
    blob = _materials_blob(materials)
    for g in _HAN_NGRAM_RE.findall(blob):
        known.add(g)
    for title in _BOOK_TITLE_RE.findall(blob):
        known.add(title)
        for g in _HAN_NGRAM_RE.findall(title):
            known.add(g)
    return known


def _extract_novel_entities(reply: str, known: set[str]) -> list[str]:
    """只收集「叫××」中的名字候选（避免非重叠 n-gram 切碎专名）。"""
    seen: list[str] = []
    for m in _CALLED_NAME_RE.finditer(reply or ""):
        e = m.group(1)
        if e in known or e in _ENTITY_WHITELIST:
            continue
        if e not in seen:
            seen.append(e)
    return seen


def _is_definite_name_entity(e: str, known: set[str], reply: str) -> bool:
    """宁漏勿杀：候选已来自「叫××」；再排除已知集。"""
    if not e or e in known or e in _ENTITY_WHITELIST:
        return False
    return bool(re.search(rf"叫{re.escape(e)}", reply or ""))


def assert_reply_respects_card(
    reply: str,
    card: IntentionCard,
    *,
    banned_names: list[str] | None = None,
) -> list[str]:
    """
    N5 辅助断言。返回违规列表（空=通过）。
    HARD：专名黑名单、伪记忆、施教反转、空卡编造、共同回忆声明、虚构实体。
    SOFT（仅 trace，expression 不阻断）：主动 share_state 无支撑自我认知。
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
    # 施教反转：卡内 taught_by_qi 或无卡话题启发式
    if detect_teach_inversion(text, recall_relation=card.recall_relation):
        violations.append("施教关系反转")
    elif (
        not card.primary_text()
        and _INVERT_TAUGHT_BY_QI_RE.search(text)
        and (_INVERT_TOPIC_RE.search(text) or "试了" in text)
    ):
        violations.append("空卡编造共同回忆")
    # 共同回忆声明闸（主闸；与 must「不假装记得」解耦）
    if _DECLARATIVE_MEMORY_RE.search(text):
        if not _card_has_real_material(card):
            violations.append("共同回忆无出处")
        elif not _key_phrase_in_materials(text, card.materials):
            violations.append("共同回忆关键短语不在素材中")
    # 实体一致性辅助闸（宁漏勿杀）
    known = _build_known_set(card.materials)
    for e in _extract_novel_entities(text, known):
        if _is_definite_name_entity(e, known, text):
            violations.append(f"虚构实体:{e}")
    if card.channel == "proactive" and card.act == "share_state" and _SELF_VIEW_RE.search(text):
        blob = card.state_material_blob()
        # 素材未包含同类自我认知词 → 无支撑
        if not _SELF_VIEW_RE.search(blob):
            violations.append("无支撑自我认知结论")
    return violations
