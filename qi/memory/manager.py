"""记忆管理器——Brain 只从这里进出记忆世界。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qi.memory.body_memory import BodyMemory
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import VectorStore
from qi.memory.working import WorkingMemory

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database


_SELF_DISCLOSURE = (
    "我最近", "我今天", "我在", "我学", "我工作", "我朋友", "我爸", "我妈",
    "我喜欢", "我讨厌", "我害怕", "我难过", "我开心", "我觉得", "我想",
    "分手", "换工作", "生病", "加班", "搬家", "考试", "面试",
)

_STRONG_EMOTION = (
    "好难过", "太开心", "真的很", "崩溃", "兴奋", "生气", "害怕",
    "想哭", "幸福", "绝望", "激动", "烦死", "开心死", "难受",
)

_RELATIONSHIP = (
    "有你在", "谢谢你", "想你", "喜欢你", "你烦", "陪我", "离不开",
    "删掉你", "需要你", "你真好", "别走", "在吗栖", "小栖",
)

_PROMISE = ("下次", "以后", "改天", "回头", "等我", "明天给你", "周末")


class MemoryManager:
    """统一入口，协调工作记忆、叙事记忆、身体记忆。"""

    def __init__(self, db: Database, config: dict, llm: LLMGateway | None = None):
        self.db = db
        self.config = config
        mem_cfg = config.get("memory", {})
        max_working = int(mem_cfg.get("max_working_memory", 20))
        chroma_dir = mem_cfg.get("chroma_path", "data/chroma")

        self.working = WorkingMemory(max_size=max_working)
        self.vector_store = VectorStore(persist_dir=chroma_dir)
        self.narrative = NarrativeMemory(db, self.vector_store, llm=llm)
        self.body = BodyMemory(db)
        self.llm = llm

    async def restore(self) -> None:
        """醒来时把最近对话装回工作记忆。"""
        recent = await self.db.load_recent_messages(
            limit=self.working.max_size
        )
        self.working.load_from_db(recent)

    async def save(
        self,
        content: str,
        importance: float,
        emotional_intensity: float = 0.5,
        tags: list[str] | None = None,
    ) -> int:
        return await self.narrative.save(
            content, importance, emotional_intensity, tags=tags
        )

    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        return await self.narrative.search(query, top_k)

    async def weave_narrative(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
    ) -> int | None:
        return await self.narrative.weave_narrative(emotion, relationship_stage)

    async def get_body_patterns(self) -> dict:
        keys = [
            "usual_active_hours",
            "greeting_pattern",
            "silence_tolerance",
            "typing_rhythm",
        ]
        patterns = {}
        for key in keys:
            val = await self.body.get_pattern(key)
            if val is not None:
                patterns[key] = val
        return patterns

    async def has_unprocessed_events(self) -> bool:
        return (await self.db.count_unprocessed_events()) > 0

    async def on_user_message(
        self,
        message: str,
        emotion: EmotionState,
        now: datetime | None = None,
    ) -> list[str]:
        """
        处理一条用户消息的记忆侧效应：
        工作记忆、筛选 raw_events、身体记忆、异常检测。
        返回异常描述列表（可影响感知）。
        """
        now = now or datetime.now()

        overflow = self.working.add("user", message)
        if overflow is not None:
            await self.db.save_raw_event(
                event_type="user_message" if overflow.role == "user" else "internal",
                content=overflow.content,
                timestamp=overflow.timestamp,
                attention_weight=0.5,
            )

        remember, importance = self.should_remember(message, emotion)
        weight = self.compute_attention_weight(message, emotion)
        if remember:
            impact = abs(emotion.valence) * 0.5 + emotion.arousal * 0.5
            await self.db.save_raw_event(
                event_type="user_message",
                content=message,
                emotional_impact=impact,
                attention_weight=weight,
                timestamp=now,
            )

        greeting_anomaly = await self.body.detect_greeting_anomaly(message)
        await self.body.record_interaction(now, message)
        anomalies = await self.body.detect_anomaly(now)
        if greeting_anomaly:
            anomalies.append(greeting_anomaly)
        return anomalies

    def on_qi_message(self, content: str) -> None:
        overflow = self.working.add("qi", content)
        # 栖自己的话溢出暂不进 raw_events（原料以用户侧为主）
        _ = overflow

    def should_remember(
        self, message: str, emotion: EmotionState
    ) -> tuple[bool, float]:
        text = message.strip()
        if not text or len(text) <= 1:
            return False, 0.0

        # 极短寒暄（精确匹配）
        if text in ("嗯", "好的", "哦", "哈哈", "呵呵", "在吗", "ok", "OK"):
            if not any(k in text for k in _RELATIONSHIP + _STRONG_EMOTION):
                return False, 0.0

        # 明显闲聊主题且无自我披露
        if any(k in text for k in ("天气", "几点了")) and not any(
            k in text for k in _SELF_DISCLOSURE
        ):
            return False, 0.0

        importance = 0.0
        if any(k in text for k in _SELF_DISCLOSURE):
            importance = max(importance, 0.65)
        if any(k in text for k in _STRONG_EMOTION) or abs(emotion.valence) > 0.5:
            importance = max(importance, 0.7)
        if any(k in text for k in _RELATIONSHIP):
            importance = max(importance, 0.75)
        if any(k in text for k in _PROMISE):
            importance = max(importance, 0.55)
        if any(k in text for k in ("分手", "换工作", "生病", "去世", "毕业")):
            importance = max(importance, 0.9)

        if importance <= 0:
            return False, 0.0
        return True, min(1.0, importance)

    def compute_attention_weight(self, message: str, emotion: EmotionState) -> float:
        text = message.strip()
        weight = 1.0

        sentiment = 0.0
        if any(k in text for k in _STRONG_EMOTION):
            sentiment = 0.8
        elif abs(emotion.valence) > 0.3:
            sentiment = abs(emotion.valence)
        weight += sentiment * 0.5

        disclosure = 1.0 if any(k in text for k in _SELF_DISCLOSURE) else 0.0
        weight += disclosure * 0.4

        relation = 1.0 if any(k in text for k in _RELATIONSHIP) else 0.0
        weight += relation * 0.6

        return weight
