"""记忆管理器——Brain 只从这里进出记忆世界。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from qi.memory.body_memory import BodyMemory
from qi.memory.facts import FactNoticer, FactStore, stage_at_least
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

# 求助 / 健康困扰：用户开口求助是有分量的交换——日后会问「你上次说的那个方法」。
_HELP_HEALTH = (
    "怎么办", "睡不着", "失眠", "睡不好", "熬夜", "头疼", "头痛",
    "焦虑", "压力大", "累死", "撑不住", "怎么才能", "有没有办法",
    "教我", "帮我想", "给点建议", "怎么解决",
)

# 显式追问记忆：叙事空时允许回翻 messages（不当日常检索）
_RECALL_PROBE = (
    "还记得", "记得吗", "记不记得", "上次", "那次", "那件事",
    "你教过", "你教了", "你说过", "你跟我说过", "你告诉过", "跟你说",
)

_RECALL_STOP = (
    "我", "你", "他", "她", "的", "了", "吗", "呢", "啊", "吧", "在", "有",
    "和", "与", "就", "都", "也", "很", "会", "能", "一个", "一下", "时候",
    "有时候", "然后", "说过", "教了", "告诉", "方法", "事情", "这件事",
)

_FORGET_ACK = ("不记得", "够不到", "空白", "没印象", "记不清", "没有留下痕迹")


class MemoryManager:
    """统一入口，协调工作记忆、叙事记忆、身体记忆、用户事实。"""

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
        self.facts = FactStore(db)
        self.fact_noticer = FactNoticer(self.facts, llm=llm)
        self.llm = llm

    async def restore(self) -> None:
        """醒来时把最近对话装回工作记忆。事实按需从 DB 读，不必预装。"""
        recent = await self.db.load_recent_messages(
            limit=self.working.max_size
        )
        self.working.load_from_db(recent)

    async def notice_facts(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str,
        now: datetime | None = None,
    ) -> list[dict]:
        # 当前句尚未 on_user_message，用既有工作记忆作多拍上下文
        recent = [
            {"role": m.role, "content": m.content}
            for m in self.working.get_messages()
        ]
        return await self.fact_noticer.notice(
            message,
            emotion,
            relationship_stage,
            now=now,
            recent_messages=recent,
        )

    async def active_facts(self, fact_type: str | None = None) -> list[dict]:
        return await self.facts.active_facts(fact_type)

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

    async def retrieve_for_prompt(self, query: str, top_k: int = 3) -> list[dict]:
        """对话用召回：先叙事；显式追问且叙事未命中主题时，回翻 messages。"""
        memories = await self.retrieve(query, top_k=top_k)
        if not self.is_recall_probe(query):
            return memories
        keys = self.recall_keywords(query)
        if memories and keys:
            blob = "\n".join(m.get("content") or "" for m in memories)
            if any(k in blob for k in keys):
                return memories
        fallback = await self.recall_from_messages(query, top_k=top_k)
        return fallback if fallback else memories

    @staticmethod
    def is_recall_probe(text: str) -> bool:
        return any(k in text for k in _RECALL_PROBE)

    @staticmethod
    def recall_keywords(text: str) -> list[str]:
        """从追问句抽出检索词：优先求助/健康锚点，再取剩余中文块。"""
        keys: list[str] = []
        for k in _HELP_HEALTH + ("入睡", "助眠", "方法"):
            if k in text and k not in keys:
                keys.append(k)
        cleaned = text
        for p in _RECALL_PROBE + _RECALL_STOP:
            cleaned = cleaned.replace(p, " ")
        for part in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
            if part not in keys and part not in _RECALL_STOP:
                keys.append(part)
        return keys

    async def recall_from_messages(self, query: str, top_k: int = 3) -> list[dict]:
        """显式「还记得吗」时扫聊天流水，拼成可注入的回忆片段。"""
        keywords = self.recall_keywords(query)
        if not keywords:
            return []
        msgs = await self.db.load_messages(limit=300)
        if not msgs:
            return []
        # 当前追问句本身不参与命中
        if msgs and msgs[-1].get("role") == "user" and msgs[-1].get("content") == query:
            msgs = msgs[:-1]

        scored: list[tuple[int, int, dict]] = []
        for i, m in enumerate(msgs):
            content = m.get("content") or ""
            # 追问句本身不是回忆内容
            if m.get("role") == "user" and self.is_recall_probe(content):
                continue
            # 否认记忆的回复也会带主题词，不能当回忆
            if m.get("role") == "qi" and any(k in content for k in _FORGET_ACK):
                continue
            hits = sum(1 for k in keywords if k in content)
            if hits:
                scored.append((hits, i, m))
        if not scored:
            return []
        # 命中多者优先；同命中取更早（「上次」）
        scored.sort(key=lambda x: (-x[0], x[1]))

        results: list[dict] = []
        used_ids: set[int] = set()
        for _hits, i, m in scored:
            mid = int(m["id"])
            if mid in used_ids:
                continue
            if m["role"] == "user":
                qi_bit = ""
                if i + 1 < len(msgs) and msgs[i + 1].get("role") == "qi":
                    qi_msg = msgs[i + 1]
                    qi_text = qi_msg.get("content") or ""
                    if not any(k in qi_text for k in _FORGET_ACK):
                        used_ids.add(int(qi_msg["id"]))
                        qi_bit = f"\n你当时回过：{qi_text[:160]}"
                # 用户原话里的“你/我”是他的视角（你=栖、我=他），加锤点防栖读反
                snippet = (
                    f"他曾说（他口中的「你」是你、「我」是他）："
                    f"{(m.get('content') or '')[:100]}{qi_bit}"
                )
            else:
                snippet = f"你曾说过：{(m.get('content') or '')[:180]}"
            used_ids.add(mid)
            results.append(
                {
                    "id": mid,
                    "content": snippet,
                    "strength": 0.85,
                    "importance": 0.7,
                    "source": "messages_recall",
                }
            )
            if len(results) >= top_k:
                break
        return results

    async def weave_narrative(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
    ) -> int | None:
        mem_cfg = self.config.get("memory", {})
        batch = mem_cfg.get("narrative_weave_batch_size")
        batch_size = int(batch) if batch is not None else None
        return await self.narrative.weave_narrative(
            emotion,
            relationship_stage,
            batch_size=batch_size,
        )

    async def unprocessed_event_count(self) -> int:
        return await self.db.count_unprocessed_events()

    async def has_unprocessed_events(self) -> bool:
        return (await self.unprocessed_event_count()) > 0

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

    async def body_rhythm_hint(self, stage: str) -> str:
        """身体节奏 hint：整段（含标题）进 placeholder；空则整段不出现。"""
        if not stage_at_least(stage, "acquaintance"):
            return ""
        patterns = await self.get_body_patterns()
        hours = patterns.get("usual_active_hours") or {}
        if int(hours.get("samples") or 0) < 5:
            return ""
        start = int(hours.get("start", 9))
        end = int(hours.get("end", 23))
        return (
            "【他的身体节奏】\n"
            f"你隐约知道他通常 {start}–{end} 点比较活跃。"
            "知道就好，不要主动评论他的作息。"
        )

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

        # 异常检测必须在 record 之前：否则 _last_interaction 已更新，沉默 gap≈0
        greeting_anomaly = await self.body.detect_greeting_anomaly(message)
        anomalies = await self.body.detect_anomaly(now)
        if greeting_anomaly:
            anomalies.append(greeting_anomaly)
        await self.body.record_interaction(now, message)
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

        # 明显闲聊主题且无自我披露 / 求助
        if any(k in text for k in ("天气", "几点了")) and not any(
            k in text for k in _SELF_DISCLOSURE + _HELP_HEALTH
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
        if any(k in text for k in _HELP_HEALTH):
            importance = max(importance, 0.6)
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

        help_ask = 1.0 if any(k in text for k in _HELP_HEALTH) else 0.0
        weight += help_ask * 0.35

        relation = 1.0 if any(k in text for k in _RELATIONSHIP) else 0.0
        weight += relation * 0.6

        return weight
