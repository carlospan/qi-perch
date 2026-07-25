"""感知层——把外界变成栖能感受到的东西。"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from qi.core.emotion import modulate_impact

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

_EXCLAIM = ("！", "!", "…", "...", "？", "?")
_IMPACT_LLM_TIMEOUT = 2.0


class Perception:
    """感知层。L3：冲击会经状态调制；低置信时可选 LLM 旁路。"""

    def __init__(self, config: dict, llm: LLMGateway | None = None):
        self.config = config
        self.llm = llm
        self.relationship_stage: str = "stranger"
        self.user_present: bool = True

    def set_user_presence(self, online: bool) -> None:
        """窗口打开/最小化时，它会知道你在不在。"""
        self.user_present = online

    def detect_silence(self, last_interaction: datetime, now: datetime) -> float:
        return (now - last_interaction).total_seconds()

    def _keyword_base(self, text: str) -> tuple[float, int, int]:
        pos_hits = sum(1 for w in _POSITIVE if w in text)
        neg_hits = sum(1 for w in _NEGATIVE if w in text)

        if len(text) <= 2 and pos_hits == 0 and neg_hits == 0:
            base = -0.08
        elif pos_hits == 0 and neg_hits == 0:
            base = 0.05
        else:
            raw = (pos_hits - neg_hits * 1.2) / max(pos_hits + neg_hits, 1)
            base = max(-1.0, min(1.0, raw * 0.5))
        return base, pos_hits, neg_hits

    def _needs_llm_impact(self, text: str, pos_hits: int, neg_hits: int) -> bool:
        if pos_hits > 0 and neg_hits > 0:
            return True
        if pos_hits == 0 and neg_hits == 0 and len(text) > 40:
            return True
        if neg_hits > 0 and any(m in text for m in _EXCLAIM):
            return True
        return False

    def assess_impact(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str | None = None,
    ) -> float:
        """
        评估消息的基础冲击，再按当前状态调制（关键词主路径）。
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
    ) -> float:
        """关键词为主；低置信才问 LLM，超时/失败回退关键词值。"""
        text = (message or "").strip()
        if not text:
            return 0.0

        base, pos_hits, neg_hits = self._keyword_base(text.lower())
        stage = relationship_stage or self.relationship_stage
        keyword_value = max(-1.0, min(1.0, modulate_impact(base, emotion, stage)))

        if self.llm is None or not self._needs_llm_impact(text, pos_hits, neg_hits):
            return keyword_value

        try:
            llm_base = await asyncio.wait_for(
                self._llm_impact_base(text),
                timeout=_IMPACT_LLM_TIMEOUT,
            )
        except Exception:
            logger.debug("冲击 LLM 旁路失败，回退关键词", exc_info=True)
            return keyword_value

        if llm_base is None:
            return keyword_value
        return max(-1.0, min(1.0, modulate_impact(llm_base, emotion, stage)))

    async def _llm_impact_base(self, text: str) -> float | None:
        assert self.llm is not None
        raw = await self.llm.call(
            purpose="fact",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "评估下面这句话对倾听者的情绪冲击。"
                        "只输出一个 -1.0 到 1.0 之间的小数（负=伤人/沉重，正=温暖/积极）。"
                        f"\n\n句子：{text}"
                    ),
                }
            ],
            temperature=0.3,
        )
        if not raw:
            return None
        m = re.search(r"-?\d+(?:\.\d+)?", str(raw))
        if not m:
            return None
        try:
            val = float(m.group(0))
        except ValueError:
            return None
        if val < -1.0 or val > 1.0:
            return None
        return val

    def apply_security_hint(self, emotion: EmotionState, impact: float) -> EmotionState:
        """负面冲击时安全感微降；正面时微升。"""
        new = emotion.model_copy()
        if impact < -0.05:
            new.security = max(0.0, new.security + impact * 0.3)
        elif impact > 0.1:
            new.security = min(1.0, new.security + impact * 0.1)
        return new
