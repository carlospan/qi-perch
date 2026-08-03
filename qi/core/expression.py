"""表达层——意向卡 → 语言器官（LLM 措辞 / 模板降级）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.intention import (
    IntentionCard,
    anchor_teaching_relation,
    detect_sleep_teach_inversion,
)
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
    "施教方向必须正确：入睡方法是栖教给用户的。严禁说「你教我的方法/你教过我」"
    "这类反转表述；若提起，说「我教你的那个方法」。"
)
_TEACH_INVERSION_FALLBACK = (
    "……我记得的。入睡那件事，是我教你的——允许自己躺着，不强迫。这个方向我不会记反。"
)


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


def render_template(card: IntentionCard) -> str:
    """断网/空返回模板：朴素、有出处，只使用卡内素材。"""
    if card.silence:
        return ""
    primary = card.primary_text()
    act = card.act
    short = card.length == "short"

    if act == "answer":
        if primary:
            text = f"{primary}……嗯。"
        else:
            text = "……嗯，这个我现在想不清楚。"
    elif act == "acknowledge":
        text = f"……我听见了。{primary}" if primary else "……我听见了。"
    elif act == "share_state":
        text = f"……{primary}。" if primary else "……嗯。"
    elif act == "recall":
        text = f"记得。{primary}。" if primary else "……我不确定自己还记不记得。"
    elif act == "comfort_back":
        text = "……谢谢你。我就在这儿。"
    elif act == "take_tease":
        text = "……哼。被你说中了。" if "克制" not in card.stance else "……这样啊。"
    elif act == "honest_hurt":
        text = "……这句话，我接住了。"
    elif act == "free_talk":
        text = f"……嗯。{primary}" if primary else "……嗯。"
    elif act == "silence":
        return ""
    else:
        text = f"……嗯。{primary}" if primary else "……嗯。"

    text = text.strip()
    if short and len(text) > 40:
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
                str(sys0.get("content") or "")
                + f"\n\n【长度】{_SHORT_LENGTH_CONSTRAINT}"
            )
            messages[0] = sys0

        # 包17：自由对话路径注入施教锚定（复用包15纯函数）；
        # 本次补强：近聊无话题时回退 user_facts 存档真值
        facts_text = str((inner_extras or {}).get("user_facts") or "")
        teach_hint = anchor_teaching_relation(
            recent_messages or [], facts_text=facts_text
        )
        if teach_hint and messages:
            messages = list(messages)
            sys0 = dict(messages[0])
            sys0["content"] = (
                str(sys0.get("content") or "")
                + f"\n\n【施教关系锚定】{teach_hint}"
            )
            messages[0] = sys0

        hist = recent_qi_replies_from_messages(
            recent_messages, limit=REPLY_DEDUP_WINDOW
        )

        text = ""
        try:
            text = await self.llm.call(purpose="conversation", messages=messages)
        except Exception:
            logger.debug("表达 LLM 异常，走模板", exc_info=True)
            text = ""

        text = str(text or "").strip()
        # 运行时硬闸：方向反转先于去重处理（方向错比复读重）
        if text and detect_sleep_teach_inversion(text):
            fixed = await self._fix_teach_inversion(messages)
            if fixed is None:
                intention.outcome = "template"
                return _TEACH_INVERSION_FALLBACK
            text = fixed
        if text:
            if not is_duplicate_reply(text, hist):
                intention.outcome = "llm"
                return text
            # 跨轮复读：轻量重生成一次
            regen_messages = list(messages)
            if regen_messages:
                sys0 = dict(regen_messages[0])
                sys0["content"] = (
                    str(sys0.get("content") or "")
                    + f"\n\n【去重】{_DEDUP_REGEN_CONSTRAINT}"
                )
                regen_messages[0] = sys0
            try:
                again = await self.llm.call(
                    purpose="conversation", messages=regen_messages
                )
            except Exception:
                logger.debug("去重重生成异常，走模板", exc_info=True)
                again = ""
            again = str(again or "").strip()
            if again and not is_duplicate_reply(again, hist):
                if detect_sleep_teach_inversion(again):
                    intention.outcome = "template"
                    return _TEACH_INVERSION_FALLBACK
                intention.outcome = "llm"
                return again
            # 仍重复 → 模板降级（acknowledge/share_state 简版路径）
            templated = render_template(intention)
            if templated:
                intention.outcome = "template"
                return templated
            intention.outcome = "empty"
            return ""

        # UNREACHABLE / EMPTY：一律模板开口（契约演进）
        templated = render_template(intention)
        if templated:
            intention.outcome = "template"
            return templated
        intention.outcome = "empty"
        return ""

    async def _fix_teach_inversion(self, messages: list[dict]) -> str | None:
        """反转重试一次：加强约束再生成；仍反转返回 None（调用方模板兜底）。"""
        fix_messages = list(messages)
        if fix_messages:
            sys0 = dict(fix_messages[0])
            sys0["content"] = (
                str(sys0.get("content") or "")
                + f"\n\n【施教方向硬约束】{_TEACH_INVERSION_CONSTRAINT}"
            )
            fix_messages[0] = sys0
        try:
            fixed = await self.llm.call(
                purpose="conversation", messages=fix_messages
            )
        except Exception:
            logger.debug("施教反转重试异常，走兜底", exc_info=True)
            fixed = ""
        fixed = str(fixed or "").strip()
        if fixed and not detect_sleep_teach_inversion(fixed):
            return fixed
        return None
