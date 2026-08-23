"""表达层——意向卡 → 语言器官（LLM 措辞 / 模板降级）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.intention import (
    IntentionCard,
    anchor_teaching_relation,
    assert_reply_respects_card,
    detect_teach_inversion,
    is_hard_violation,
    looks_like_answer_chase,
)
from qi.core.turn_understanding import looks_like_substantive_question
from qi.inner_life.consciousness import char_jaccard
from qi.llm.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.expression")

REPLY_DEDUP_THRESHOLD = 0.85
REPLY_DEDUP_WINDOW = 5
_SHORT_LENGTH_CONSTRAINT = "用 1-2 句、克制长度，不超过 60 字。"
_DEDUP_REGEN_CONSTRAINT = "不要重复刚才说过的话，换个说法回应。"
# 运行时硬闸（补包 15/16/17 的最后一环）：反转重试约束与模板兜底
_TEACH_INVERSION_CONSTRAINT = (
    "施教方向必须正确：若卡标明栖教用户，"
    "严禁说「你教我的方法/你教过我/你教给我」这类反转表述；"
    "若提起，说「我教你的那个方法」。"
)
_TEACH_INVERSION_FALLBACK = "……我记得的。这个方向以记忆为准，我不会跟着说反。"
_TEACH_INVERSION_FALLBACK_QI_TAUGHT = "……我记得的。是我教你的方向，我不会记反。"
_FACT_CONSISTENCY_CONSTRAINT = (
    "事实必须来自意向卡素材。不要编造卡外共同回忆（如「那天你问…」「那晚我说…」）；"
    "不要引入素材中没有的具体人名。不确定就说不确定，或用意象/比喻。"
)
# free_talk 模板勿粘贴 memory 原文（曾致 #1483/#1485 答非所问 + 恰 84 字截断感）
_EMPTY_CARD_SAFE = "……刚才那句，我没接好。能再说一次吗？"
# 保留旧名：单测 / 去重用例仍引用
_FREE_TALK_SAFE = _EMPTY_CARD_SAFE
_DEDUP_SAFE = "……我好像卡住重复了。你刚才那句，能再说一次吗？"
# 催答空卡/空返回：接住催促，不编实质答案（实证 #1678）
_ANSWER_CHASE_SAFE = (
    "你在催我答上一句。我这拍没说清楚——"
    "你要听的是哪一问，用半句点一下？"
)
_ANSWER_CHASE_CONSTRAINT = (
    "用户在催你回答上一问。若上一问尚未正面回应："
    "先直接回应或诚实说明卡在哪；"
    "禁止只回「……嗯。」这类敷衍；禁止编造卡外事实。"
)
_SUBSTANTIVE_RETRY_CONSTRAINT = (
    "用户在问需要认真回应的实质问题。请直接作答；"
    "可引用卡内 state 描述此刻感受；"
    "禁止说「想了很久/选了又选/那天你说」等无出处的过程或共同史；"
    "禁止只回「没接好请再说」类系统句。"
)
_NO_PROCESS_FABRICATION_CONSTRAINT = (
    "卡内无 memory/fact 时：勿声称想了很久、选了又选、沉默很久等思考过程；"
    "可说「我不确定怎么定义，但此刻我……」并引用 state。"
)
_SUBSTANTIVE_EMPTY_SAFE = "……这个问题很重。让我诚实说几句——"
_ELLIPSIS_DODGE = frozenset({"……嗯。", "……嗯", "嗯。", "……", "…", "嗯"})

_TEACH_VIOLATION_TAGS = ("施教关系反转", "空卡编造共同回忆")


def _is_ellipsis_dodge(text: str) -> bool:
    t = (text or "").strip()
    return t in _ELLIPSIS_DODGE


def _teach_memory_violation(text: str, intention: IntentionCard) -> bool:
    """施教方向反转或空卡编造共同回忆 → 需硬闸。（包 15-17 保留）"""
    if detect_teach_inversion(text, recall_relation=intention.recall_relation):
        return True
    viol = assert_reply_respects_card(text, intention)
    return any(any(tag in v for tag in _TEACH_VIOLATION_TAGS) for v in viol)


def _hard_violations(
    text: str,
    intention: IntentionCard,
    *,
    recent_messages: list[dict] | None = None,
) -> list[str]:
    return [
        v
        for v in assert_reply_respects_card(
            text, intention, recent_messages=recent_messages
        )
        if is_hard_violation(v)
    ]


def _build_fallback(
    intention: IntentionCard,
    viols: list[str],
    *,
    user_message: str = "",
) -> str:
    """按违规类型选模板兜底。"""
    if any("施教" in v or "空卡编造共同回忆" in v for v in viols) or any(
        any(t in v for t in _TEACH_VIOLATION_TAGS) for v in viols
    ):
        if intention.recall_relation == "taught_by_qi":
            return _TEACH_INVERSION_FALLBACK_QI_TAUGHT
        return _TEACH_INVERSION_FALLBACK
    templated = render_template(intention, user_message=user_message)
    if templated:
        return templated
    return "……我不确定自己还记不记得。我不想假装记得。"


def recent_qi_replies_from_messages(
    messages: list[dict] | None, limit: int = REPLY_DEDUP_WINDOW
) -> list[str]:
    """从近聊（旧→新）抽出最近 N 条栖回复文本。"""
    out: list[str] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        if m.get("role") != "qi":
            continue
        text = str(m.get("content") or "").strip()
        if text:
            out.append(text)
    if limit <= 0:
        return []
    return out[-limit:]


async def recent_qi_replies(db: Database, limit: int = REPLY_DEDUP_WINDOW) -> list[str]:
    """读库取最近 N 条栖回复（旧→新）。多取若干条以覆盖夹杂的用户消息。"""
    fetch = max(limit * 3, limit + 8)
    msgs = await db.load_recent_messages(limit=fetch)
    return recent_qi_replies_from_messages(msgs, limit=limit)


def is_duplicate_reply(
    text: str,
    history: list[str],
    *,
    threshold: float = REPLY_DEDUP_THRESHOLD,
) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    for prev in history:
        if prev and char_jaccard(t, prev) > threshold:
            return True
    return False


def _empty_primary_fallback(
    *,
    chase: bool,
    substantive: bool = False,
    card: IntentionCard | None = None,
) -> str:
    if chase:
        return _ANSWER_CHASE_SAFE
    if substantive:
        primary = (card.primary_text() if card else "") or ""
        state = primary if primary else ""
        if state:
            return f"{_SUBSTANTIVE_EMPTY_SAFE}{state}。"
        return _SUBSTANTIVE_EMPTY_SAFE
    return _EMPTY_CARD_SAFE


def render_template(card: IntentionCard, *, user_message: str = "") -> str:
    """断网/空返回模板：朴素、有出处，只使用卡内素材。"""
    if card.silence:
        return ""
    primary = card.primary_text()
    act = card.act
    short = card.length == "short"
    chase = looks_like_answer_chase(user_message) or looks_like_answer_chase(
        card.topic
    )
    substantive = looks_like_substantive_question(user_message) or looks_like_substantive_question(
        card.topic
    )

    if act == "answer":
        if primary:
            text = f"{primary}……嗯。"
        else:
            text = _empty_primary_fallback(
                chase=chase, substantive=substantive, card=card
            )
    elif act == "acknowledge":
        if primary:
            text = f"……我听见了。{primary}"
        elif substantive:
            text = _empty_primary_fallback(
                chase=chase, substantive=True, card=card
            )
        else:
            text = "……我听见了。"
    elif act == "share_state":
        text = f"……{primary}。" if primary else _empty_primary_fallback(
            chase=chase, substantive=substantive, card=card
        )
    elif act == "recall":
        text = f"记得。{primary}。" if primary else "……我不确定自己还记不记得。"
    elif act == "comfort_back":
        text = "……谢谢你。我就在这儿。"
    elif act == "take_tease":
        text = "……哼。被你说中了。" if "克制" not in card.stance else "……这样啊。"
    elif act == "honest_hurt":
        text = "……这句话，我接住了。"
    elif act == "free_talk":
        # memory 原文当整句回复 = 答非所问；fact/state/cue 仍可短引
        if any(m.tag == "memory" for m in card.materials) and (
            not primary
            or any(
                m.tag == "memory" and (m.text or "").strip() == primary
                for m in card.materials
            )
        ):
            text = _EMPTY_CARD_SAFE
        elif chase and not primary:
            text = _ANSWER_CHASE_SAFE
        elif substantive and not primary:
            text = _empty_primary_fallback(
                chase=False, substantive=True, card=card
            )
        else:
            text = f"……嗯。{primary}" if primary else _EMPTY_CARD_SAFE
    elif act == "silence":
        return ""
    else:
        if chase and not primary:
            text = _ANSWER_CHASE_SAFE
        else:
            text = f"……嗯。{primary}" if primary else _EMPTY_CARD_SAFE

    text = text.strip()
    # 催答 / 空卡安全句勿被 short 截断成半句（否则又像敷衍）
    if short and len(text) > 40 and text not in (
        _ANSWER_CHASE_SAFE,
        _EMPTY_CARD_SAFE,
        _SUBSTANTIVE_EMPTY_SAFE,
    ):
        text = text[:40].rstrip("。…") + "…"
    return text


class Expression:
    """栖开口的地方。先有意向，再措辞。"""

    def __init__(self, config: dict, llm: LLMGateway):
        self.config = config
        self.llm = llm
        self.prompt_builder = PromptBuilder()

    async def express(
        self,
        user_message: str,
        emotion: EmotionState,
        now: datetime,
        intention: IntentionCard,
        recent_messages: list[dict] | None = None,
        memories: list[dict] | None = None,
        inner_extras: dict[str, str] | None = None,
        relationship_stage: str = "stranger",
        shared_culture: str = "",
        relationship_hint: str = "",
        scar_hint: str = "",
        season: str = "spring",
        proactive_kind: str | None = None,
    ) -> str:
        if intention.silence or intention.act == "silence":
            intention.outcome = "silence"
            return ""

        messages = self.prompt_builder.build_conversation_prompt(
            user_message=user_message,
            emotion=emotion,
            now=now,
            recent_messages=recent_messages or [],
            memories=memories or [],
            inner_extras=inner_extras,
            relationship_stage=relationship_stage,
            shared_culture=shared_culture,
            relationship_hint=relationship_hint,
            scar_hint=scar_hint,
            season=season,
            proactive_kind=proactive_kind,
            intention=intention,
        )
        if intention.length == "short" and messages:
            messages = list(messages)
            sys0 = dict(messages[0])
            sys0["content"] = (
                str(sys0.get("content") or "") + f"\n\n【长度】{_SHORT_LENGTH_CONSTRAINT}"
            )
            messages[0] = sys0

        # 包17：自由对话路径注入施教锚定（复用包15纯函数）；
        # 本次补强：近聊无话题时回退 user_facts 存档真值
        facts_text = str((inner_extras or {}).get("user_facts") or "")
        teach_hint = anchor_teaching_relation(recent_messages or [], facts_text=facts_text)
        if teach_hint and messages:
            messages = list(messages)
            sys0 = dict(messages[0])
            sys0["content"] = str(sys0.get("content") or "") + f"\n\n【施教关系锚定】{teach_hint}"
            messages[0] = sys0

        from qi.core.turn_understanding import turn_situation_expression_hint

        sit_hint = turn_situation_expression_hint(inner_extras or {})
        if sit_hint and messages:
            messages = list(messages)
            sys0 = dict(messages[0])
            sys0["content"] = str(sys0.get("content") or "") + f"\n\n【处境】{sit_hint}"
            messages[0] = sys0

        from qi.core.intention import _card_has_real_material

        if not _card_has_real_material(intention) and messages:
            messages = list(messages)
            sys0 = dict(messages[0])
            sys0["content"] = (
                str(sys0.get("content") or "")
                + f"\n\n【诚实】{_NO_PROCESS_FABRICATION_CONSTRAINT}"
            )
            messages[0] = sys0

        hist = recent_qi_replies_from_messages(recent_messages, limit=REPLY_DEDUP_WINDOW)
        chase = looks_like_answer_chase(user_message) or looks_like_answer_chase(
            intention.topic
        )
        substantive = looks_like_substantive_question(
            user_message
        ) or looks_like_substantive_question(intention.topic)

        text = ""
        # 每拍对话最多 2 次 LLM：主调用 +（HARD 修复 XOR 催答空重试 XOR 去重重生）
        used_retry = False
        try:
            text = await self.llm.call(purpose="conversation", messages=messages)
        except Exception:
            logger.debug("表达 LLM 异常，走模板", exc_info=True)
            text = ""

        text = str(text or "").strip()
        # 催答：空返回或省略号敷衍 → 约束重试一次（占本拍重试预算）
        if chase and (not text or _is_ellipsis_dodge(text)) and not used_retry:
            chase_messages = list(messages)
            if chase_messages:
                sys0 = dict(chase_messages[0])
                sys0["content"] = (
                    str(sys0.get("content") or "")
                    + f"\n\n【催答】{_ANSWER_CHASE_CONSTRAINT}"
                )
                chase_messages[0] = sys0
            try:
                again = await self.llm.call(
                    purpose="conversation", messages=chase_messages
                )
            except Exception:
                logger.debug("催答重试异常，走模板", exc_info=True)
                again = ""
            used_retry = True
            again = str(again or "").strip()
            if again and not _is_ellipsis_dodge(again):
                text = again
            else:
                text = ""

        # 实质问：空返回或省略号敷衍 → 约束重试一次
        if (
            substantive
            and not chase
            and (not text or _is_ellipsis_dodge(text))
            and not used_retry
        ):
            sub_messages = list(messages)
            if sub_messages:
                sys0 = dict(sub_messages[0])
                sys0["content"] = (
                    str(sys0.get("content") or "")
                    + f"\n\n【实质问】{_SUBSTANTIVE_RETRY_CONSTRAINT}"
                )
                sub_messages[0] = sys0
            try:
                again = await self.llm.call(
                    purpose="conversation", messages=sub_messages
                )
            except Exception:
                logger.debug("实质问重试异常，走模板", exc_info=True)
                again = ""
            used_retry = True
            again = str(again or "").strip()
            if again and not _is_ellipsis_dodge(again):
                text = again
            else:
                text = ""

        # 运行时硬闸：全量 HARD（施教/共同回忆/虚构实体…）；SOFT 仅写入 evidence
        if text:
            all_viols = assert_reply_respects_card(
                text, intention, recent_messages=recent_messages
            )
            soft = [v for v in all_viols if not is_hard_violation(v)]
            if soft:
                intention.evidence = dict(intention.evidence or {})
                intention.evidence["soft_violations"] = soft
            hard = [v for v in all_viols if is_hard_violation(v)]
            if hard:
                if used_retry:
                    intention.outcome = "template"
                    return _build_fallback(
                        intention, hard, user_message=user_message
                    )
                fixed = await self._fix_generation(
                    messages, hard, intention, recent_messages=recent_messages
                )
                used_retry = True
                if fixed is None:
                    intention.outcome = "template"
                    return _build_fallback(
                        intention, hard, user_message=user_message
                    )
                text = fixed
        if text:
            if not is_duplicate_reply(text, hist):
                intention.outcome = "llm"
                return text
            # 跨轮复读：若本拍已用过重试预算 → 直接模板，不再打第三次 LLM
            if used_retry:
                templated = render_template(intention, user_message=user_message)
                if templated and not is_duplicate_reply(templated, hist):
                    intention.outcome = "template"
                    return templated
                intention.outcome = "template"
                return _DEDUP_SAFE
            regen_messages = list(messages)
            if regen_messages:
                sys0 = dict(regen_messages[0])
                sys0["content"] = (
                    str(sys0.get("content") or "") + f"\n\n【去重】{_DEDUP_REGEN_CONSTRAINT}"
                )
                regen_messages[0] = sys0
            try:
                again = await self.llm.call(purpose="conversation", messages=regen_messages)
            except Exception:
                logger.debug("去重重生成异常，走模板", exc_info=True)
                again = ""
            again = str(again or "").strip()
            if again and not is_duplicate_reply(again, hist):
                again_hard = _hard_violations(
                    again, intention, recent_messages=recent_messages
                )
                if again_hard:
                    fb = _build_fallback(
                        intention, again_hard, user_message=user_message
                    )
                    if fb and not is_duplicate_reply(fb, hist):
                        intention.outcome = "template"
                        return fb
                    intention.outcome = "template"
                    return _DEDUP_SAFE
                intention.outcome = "llm"
                return again
            # 仍重复 → 模板；若模板也撞车则安全句（防 #1485≡#1487）
            templated = render_template(intention, user_message=user_message)
            if templated and not is_duplicate_reply(templated, hist):
                intention.outcome = "template"
                return templated
            intention.outcome = "template"
            return _DEDUP_SAFE

        # UNREACHABLE / EMPTY：一律模板开口（契约演进）
        templated = render_template(intention, user_message=user_message)
        if templated:
            intention.outcome = "template"
            return templated
        intention.outcome = "empty"
        return ""

    async def _fix_generation(
        self,
        messages: list[dict],
        viols: list[str],
        intention: IntentionCard,
        *,
        recent_messages: list[dict] | None = None,
    ) -> str | None:
        """HARD 违规重试一次；仍违规返回 None（调用方模板兜底）。"""
        teach_related = any("施教" in v or "空卡编造共同回忆" in v for v in viols)
        if teach_related:
            header = "【施教方向硬约束】"
            constraint = _TEACH_INVERSION_CONSTRAINT
        else:
            header = "【事实一致性硬约束】"
            detail = "；".join(viols)
            constraint = f"{_FACT_CONSISTENCY_CONSTRAINT}（本拍触发：{detail}）"

        fix_messages = list(messages)
        if fix_messages:
            sys0 = dict(fix_messages[0])
            sys0["content"] = str(sys0.get("content") or "") + f"\n\n{header}{constraint}"
            fix_messages[0] = sys0
        try:
            fixed = await self.llm.call(purpose="conversation", messages=fix_messages)
        except Exception:
            logger.debug("事实一致性重试异常，走兜底", exc_info=True)
            fixed = ""
        fixed = str(fixed or "").strip()
        if not fixed:
            return None
        if teach_related and detect_teach_inversion(
            fixed, recall_relation=intention.recall_relation
        ):
            return None
        if _hard_violations(fixed, intention, recent_messages=recent_messages):
            return None
        return fixed

    async def _fix_teach_inversion(self, messages: list[dict]) -> str | None:
        """反转重试一次（包 15-17 保留；新路径优先走 _fix_generation）。"""
        fix_messages = list(messages)
        if fix_messages:
            sys0 = dict(fix_messages[0])
            sys0["content"] = (
                str(sys0.get("content") or "")
                + f"\n\n【施教方向硬约束】{_TEACH_INVERSION_CONSTRAINT}"
            )
            fix_messages[0] = sys0
        try:
            fixed = await self.llm.call(purpose="conversation", messages=fix_messages)
        except Exception:
            logger.debug("施教反转重试异常，走兜底", exc_info=True)
            fixed = ""
        fixed = str(fixed or "").strip()
        if fixed and not detect_teach_inversion(fixed):
            return fixed
        return None
