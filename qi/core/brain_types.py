"""Brain 共享类型与常量——零行为；仅供结构拆分。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# 用户消息短队列上限：满则拒收最新并系统态告知（不静默丢最早）
PENDING_QUEUE_MAX = 3
# 情绪落盘最小间隔（秒）；用户来消息时仍立即写
EMOTION_SAVE_MIN_INTERVAL = 30.0
# 季节判定读取的情绪时间窗（小时）
SEASON_EMOTION_HOURS = 24.0


@dataclass
class _PendingSpeech:
    """生成已完成、待在心跳锁外推送的话语。"""

    text: str
    now: datetime
    proactive: bool
    # 对话流式：锁内已推 delta；出锁后 finish + 只落记忆、不再整段 emit
    stream: object | None = None


@dataclass
class PromptContext:
    """组装对话 prompt 的上下文——避免 7 元组位置解包。"""

    recent_messages: list[dict]
    retrieved_memories: list[dict]
    extras: dict[str, str]
    shared_culture: str
    relationship_hint: str
    scar_hint: str
    season_hint: str
