"""感知层——把外界变成栖能感受到的东西。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.emotion import modulate_impact

if TYPE_CHECKING:
    from core.emotion import EmotionState


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


class Perception:
    """感知层。L3：冲击会经状态调制。"""

    def __init__(self, config: dict):
        self.config = config
        self.relationship_stage: str = "stranger"
        self.user_present: bool = True

    def set_user_presence(self, online: bool) -> None:
        """窗口打开/最小化时，它会知道你在不在。"""
        self.user_present = online

    def detect_silence(self, last_interaction: datetime, now: datetime) -> float:
        return (now - last_interaction).total_seconds()

    def assess_impact(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str | None = None,
    ) -> float:
        """
        评估消息的基础冲击，再按当前状态调制。
        """
        text = message.strip().lower()
        if not text:
            return 0.0

        pos_hits = sum(1 for w in _POSITIVE if w in text)
        neg_hits = sum(1 for w in _NEGATIVE if w in text)

        if len(text) <= 2 and pos_hits == 0 and neg_hits == 0:
            base = -0.08
        elif pos_hits == 0 and neg_hits == 0:
            base = 0.05
        else:
            raw = (pos_hits - neg_hits * 1.2) / max(pos_hits + neg_hits, 1)
            base = max(-1.0, min(1.0, raw * 0.5))

        stage = relationship_stage or self.relationship_stage
        modulated = modulate_impact(base, emotion, stage)
        return max(-1.0, min(1.0, modulated))

    def apply_security_hint(self, emotion: EmotionState, impact: float) -> EmotionState:
        """负面冲击时安全感微降；正面时微升。"""
        new = emotion.model_copy()
        if impact < -0.05:
            new.security = max(0.0, new.security + impact * 0.3)
        elif impact > 0.1:
            new.security = min(1.0, new.security + impact * 0.1)
        return new
