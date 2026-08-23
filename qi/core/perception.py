"""感知层——把外界变成栖能感受到的东西。

过渡止血——冲击主路径改 LLM JSON 判别；关键词仅作超时/离线/失败回退、
明显辱骂短路，以及澄清句对 tease 误判的否决（不跳过 LLM 主判）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from qi.core.emotion import modulate_impact
from qi.prompts import read_prompt

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway

logger = logging.getLogger("qi.perception")

_POSITIVE = (
    "谢谢", "喜欢", "真棒", "很好", "不错", "开心", "高兴",
    "爱你", "想你", "辛苦了", "真好", "厉害", "棒", "温暖",
    "陪我", "你好", "早", "晚安", "哈哈", "嘻嘻",
)

_NEGATIVE = (
    "烦", "闭嘴", "走开", "滚", "讨厌", "无聊", "没用",
    "删掉", "关掉", "别说", "不想理", "冷", "失望", "生气",
    "胡说", "傻逼", "笨",
)

# 明显辱骂/驱逐——带感叹类标点时可短路，不调 LLM
_STRONG_NEGATIVE = ("滚", "闭嘴", "删掉", "傻逼")

# 纯寒暄/确认——即使命中正向关键词也不值得打感知 LLM（Stage6）
_TRIVIAL_UTTERANCES = frozenset(
    {
        "你好",
        "您好",
        "早",
        "早安",
        "晚安",
        "在吗",
        "在不在",
        "嗯嗯",
        "哈哈",
        "呵呵",
        "好的",
        "收到",
        "ok",
        "OK",
        "嗨",
        "hi",
        "hello",
        "嗯",
        "啊",
        "哦",
        "喔",
    }
)
_TRIVIAL_ONLY_RE = re.compile(r"^[\s\.。…!！?？~～哈呵嗯啊哦喔]+$")

# 用户在纠正笔误或澄清本意——启发式否决层（不代替 LLM 主判，只纠错 tease 误判）
_META_CLARIFICATION_RE = re.compile(
    r"打错[了了]?字|说错[了了]?|写错[了了]?|"
    r"是\s*.+\s*才对|应该是|"
    r"我不是那个意思|不是那个意思|"
    r"你理解错了|你误会了|误会你了|"
    r"我的意思是|我想说的是"
)


def looks_like_typo_correction(text: str) -> bool:
    """弱信号：像用户在纠正笔误或澄清本意（供否决层 / 回合调制，非唯一入口）。"""
    return bool(_META_CLARIFICATION_RE.search((text or "").strip()))


# 别名：语义上含打错字与意图澄清
looks_like_user_clarification = looks_like_typo_correction

_EXCLAIM = ("！", "!", "…", "...", "？", "?")
_IMPACT_LLM_TIMEOUT = 2.0
_CONTEXT_DEFAULT = 4

# 否定前缀：「不讨厌」≠「讨厌」——实证：用户说「不讨厌」被判负面留下假疤
_NEG_PREFIX_CHARS = "不没"

IntentKind = Literal[
    "tease", "comfort", "disclosure", "request", "neutral", "hurt"
]
_VALID_INTENTS = frozenset(
    {"tease", "comfort", "disclosure", "request", "neutral", "hurt"}
)


def veto_clarification_intent(
    intent: IntentKind | None, text: str
) -> IntentKind | None:
    """LLM 将澄清句误判 tease 时否决为 neutral；不代替 LLM 主判。"""
    if intent == "tease" and looks_like_user_clarification(text):
        return "neutral"
    return intent


@dataclass
class ImpactAssessment:
    """一次冲击判别的完整结果——供关系层复用 intent。"""

    impact: float
    intent: IntentKind | None = None
    intimacy: float = 0.0
    ambiguous: bool = False
    source: str = "keyword"  # keyword | llm | llm_veto | short_circuit


def keyword_fallback_assessment(text: str, keyword_value: float) -> ImpactAssessment:
    """LLM 不可用时的关键词回退；澄清弱信号补 neutral intent。"""
    intent_fb: IntentKind | None = None
    if looks_like_user_clarification(text):
        intent_fb = "neutral"
    return ImpactAssessment(
        impact=keyword_value,
        intent=intent_fb,
        source="keyword",
    )


def count_hits_negation_aware(text: str, words: tuple[str, ...]) -> int:
    """统计命中次数，跳过被否定修饰的词（前一字为「不/没」）。"""
    hits = 0
    for w in words:
        start = 0
        while True:
            i = text.find(w, start)
            if i == -1:
                break
            if not (i > 0 and text[i - 1] in _NEG_PREFIX_CHARS):
                hits += 1
            start = i + 1
    return hits


def apply_intent_modulation(raw: float, intent: IntentKind) -> float:
    """按 intent 调整 LLM 原始 impact（tease 仅打折，不做转正）。"""
    if intent == "tease" and raw < 0:
        return raw * 0.3
    if intent == "comfort" and raw < 0:
        return 0.0  # 归零不转正
    # hurt / disclosure / request / neutral：保持
    return raw


class Perception:
    """感知层。过渡：LLM 主路径 + 关键词回退；失败不抛到 brain。"""

    def __init__(self, config: dict, llm: LLMGateway | None = None):
        self.config = config
        self.llm = llm
        self.relationship_stage: str = "stranger"
        self.user_present: bool = True
        self.last_assessment: ImpactAssessment | None = None
        perc = (config or {}).get("perception") or {}
        self._context_n = int(perc.get("context_messages", _CONTEXT_DEFAULT))

    def set_user_presence(self, online: bool) -> None:
        """窗口打开/最小化时，它会知道你在不在。"""
        self.user_present = online

    def detect_silence(self, last_interaction: datetime, now: datetime) -> float:
        return (now - last_interaction).total_seconds()

    def _keyword_base(self, text: str) -> tuple[float, int, int]:
        pos_hits = count_hits_negation_aware(text, _POSITIVE)
        neg_hits = count_hits_negation_aware(text, _NEGATIVE)

        if len(text) <= 2 and pos_hits == 0 and neg_hits == 0:
            base = -0.08
        elif pos_hits == 0 and neg_hits == 0:
            base = 0.05
        else:
            raw = (pos_hits - neg_hits * 1.2) / max(pos_hits + neg_hits, 1)
            base = max(-1.0, min(1.0, raw * 0.5))
        return base, pos_hits, neg_hits

    def _is_trivial_shortcircuit(self, text: str, pos_hits: int, neg_hits: int) -> bool:
        """寒暄/确认短路，不调感知 LLM。

        - 负向命中永不短路
        - 固定寒暄表（可含「你好」等正向词）
        - ≤2 字且无情感命中
        - 纯标点/语气词短串
        """
        t = (text or "").strip()
        if not t or neg_hits > 0:
            return bool(not t)
        if t in _TRIVIAL_UTTERANCES:
            return True
        if len(t) <= 2 and pos_hits == 0:
            return True
        if len(t) <= 6 and _TRIVIAL_ONLY_RE.fullmatch(t):
            return True
        return False

    def _is_abuse_shortcircuit(self, text: str, neg_hits: int) -> bool:
        """明显负面词 + 感叹类标点 → 关键词直判。"""
        if neg_hits <= 0:
            return False
        if not any(m in text for m in _EXCLAIM):
            return False
        return any(w in text for w in _STRONG_NEGATIVE)

    def assess_impact(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str | None = None,
    ) -> float:
        """
        评估消息的基础冲击，再按当前状态调制（关键词路径）。
        """
        text = message.strip().lower()
        if not text:
            return 0.0

        base, _, _ = self._keyword_base(text)
        stage = relationship_stage or self.relationship_stage
        modulated = modulate_impact(base, emotion, stage)
        return max(-1.0, min(1.0, modulated))

    async def assess_impact_async(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str | None = None,
        recent_messages: list[dict] | None = None,
    ) -> float:
        """
        过渡主路径：LLM JSON 判别 + intent 调制；超时/失败/短路回退关键词。
        永不向 brain 抛异常。
        """
        text = (message or "").strip()
        if not text:
            self.last_assessment = ImpactAssessment(impact=0.0, source="keyword")
            return 0.0

        base, pos_hits, neg_hits = self._keyword_base(text.lower())
        stage = relationship_stage or self.relationship_stage
        keyword_value = max(-1.0, min(1.0, modulate_impact(base, emotion, stage)))

        if self.llm is None:
            self.last_assessment = ImpactAssessment(
                impact=keyword_value, source="keyword"
            )
            return keyword_value

        if self._is_trivial_shortcircuit(text, pos_hits, neg_hits):
            self.last_assessment = ImpactAssessment(
                impact=keyword_value, source="short_circuit"
            )
            return keyword_value

        if self._is_abuse_shortcircuit(text, neg_hits):
            self.last_assessment = ImpactAssessment(
                impact=keyword_value, source="short_circuit"
            )
            return keyword_value

        try:
            parsed = await asyncio.wait_for(
                self._llm_assess(text, stage, recent_messages),
                timeout=_IMPACT_LLM_TIMEOUT,
            )
        except Exception:
            logger.debug("冲击 LLM 失败，回退关键词", exc_info=True)
            self.last_assessment = keyword_fallback_assessment(text, keyword_value)
            return keyword_value

        if parsed is None:
            self.last_assessment = keyword_fallback_assessment(text, keyword_value)
            return keyword_value

        raw, intent, intimacy, ambiguous = parsed
        source = "llm"
        vetoed = veto_clarification_intent(intent, text)
        if vetoed != intent:
            intent = vetoed
            source = "llm_veto"
        modulated_raw = apply_intent_modulation(raw, intent)
        llm_value = max(
            -1.0, min(1.0, modulate_impact(modulated_raw, emotion, stage))
        )

        if ambiguous:
            # 较保守：绝对值更小者
            final = (
                keyword_value
                if abs(keyword_value) <= abs(llm_value)
                else llm_value
            )
        else:
            final = llm_value

        self.last_assessment = ImpactAssessment(
            impact=final,
            intent=intent,
            intimacy=intimacy,
            ambiguous=ambiguous,
            source=source,
        )
        return final

    async def _llm_assess(
        self,
        message: str,
        stage: str,
        recent_messages: list[dict] | None,
    ) -> tuple[float, IntentKind, float, bool] | None:
        assert self.llm is not None
        recent_dialogue = self._format_recent(recent_messages)
        template = read_prompt("perception.txt")
        content = template.format(
            recent_dialogue=recent_dialogue,
            message=message,
            stage=stage,
        )
        raw = await self.llm.call(
            purpose="fact",
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
        )
        if not raw or not str(raw).strip():
            return None
        return self._parse_assessment_json(str(raw))

    def _format_recent(self, recent_messages: list[dict] | None) -> str:
        if not recent_messages:
            return "（无）"
        n = max(1, min(5, self._context_n))
        slice_ = recent_messages[-n:]
        lines: list[str] = []
        for m in slice_:
            role = m.get("role") or "user"
            label = "栖" if role in ("qi", "assistant") else "用户"
            text = (m.get("content") or "").strip()
            if text:
                lines.append(f"{label}：{text}")
        return "\n".join(lines) if lines else "（无）"

    def _parse_assessment_json(
        self, raw: str
    ) -> tuple[float, IntentKind, float, bool] | None:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试截取第一个 {...}
            m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if not m:
                return None
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        if not isinstance(data, dict):
            return None
        try:
            impact = float(data.get("impact"))
        except (TypeError, ValueError):
            return None
        if impact < -1.0 or impact > 1.0:
            return None
        intent_raw = str(data.get("intent") or "").strip().lower()
        if intent_raw not in _VALID_INTENTS:
            return None
        intent: IntentKind = intent_raw  # type: ignore[assignment]
        try:
            intimacy = float(data.get("intimacy", 0.0))
        except (TypeError, ValueError):
            intimacy = 0.0
        intimacy = max(0.0, min(1.0, intimacy))
        ambiguous = bool(data.get("ambiguous", False))
        return impact, intent, intimacy, ambiguous

    def apply_security_hint(self, emotion: EmotionState, impact: float) -> EmotionState:
        """负面冲击时安全感微降；正面时微升。"""
        new = emotion.model_copy()
        if impact < -0.05:
            new.security = max(0.0, new.security + impact * 0.3)
        elif impact > 0.1:
            new.security = min(1.0, new.security + impact * 0.1)
        return new
