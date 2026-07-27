"""叙事记忆：把经历织成故事，再慢慢褪色。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from qi.prompts import read_prompt

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.memory.vector_store import VectorStore
    from qi.storage.database import Database

logger = logging.getLogger("qi.memory.narrative")

# 人格契约：strength < 0.2 不引用；< 0.1 视为遗忘
RECALL_MIN_STRENGTH = 0.2
FORGET_STRENGTH = 0.1

# 一次编织的事件上限——全量塞进 80~200 字故事会空返回或冲淡重点
WEAVE_BATCH_SIZE = 10


def _event_priority(event: dict) -> tuple:
    """优先织：有 impact 的正式记得 > 高权重 > 更早的 id。"""
    impact = event.get("emotional_impact")
    has_impact = 0 if impact is None else 1
    impact_abs = abs(float(impact or 0))
    weight = float(event.get("attention_weight") or 0)
    return (-has_impact, -impact_abs, -weight, int(event["id"]))


class NarrativeMemory:
    """长期记忆的核心——不是日志，是故事。"""

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore,
        llm: LLMGateway | None = None,
    ):
        self.db = db
        self.vector_store = vector_store
        self.llm = llm

    async def save(
        self,
        content: str,
        importance: float,
        emotional_intensity: float = 0.5,
        source_event_ids: list[int] | None = None,
        tags: list[str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> int:
        memory_id = await self.db.save_narrative_memory(
            content=content,
            importance=importance,
            emotional_intensity=emotional_intensity,
            strength=1.0,
            source_event_ids=source_event_ids,
            tags=tags,
            period_start=period_start,
            period_end=period_end,
        )
        self.vector_store.add(
            memory_id,
            content,
            metadata={
                "importance": float(importance),
                "emotional_intensity": float(emotional_intensity),
            },
        )
        return memory_id

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        candidates = self.vector_store.search(query, top_k=top_k * 2)
        results: list[dict] = []
        for item in candidates:
            row = await self.db.get_narrative_memory(item["id"])
            if row is None:
                continue
            strength = float(row["strength"])
            if strength < RECALL_MIN_STRENGTH:
                continue
            await self.recall(item["id"])
            refreshed = await self.db.get_narrative_memory(item["id"])
            strength = float(refreshed["strength"]) if refreshed else strength
            results.append(
                {
                    "id": item["id"],
                    "content": row["content"],
                    "strength": strength,
                    "importance": float(row["importance"]),
                }
            )
            if len(results) >= top_k:
                break
        return results

    async def decay(self) -> None:
        """每日褪色：想起的会亮，没想起的慢慢淡；淡到尽头就真的忘了。"""
        await self.db.decay_narrative_strengths(0.999)
        forgotten = await self.db.list_forgotten_narrative_ids(FORGET_STRENGTH)
        for memory_id in forgotten:
            try:
                self.vector_store.delete(memory_id)
            except Exception:
                logger.debug("向量库删除遗忘记忆失败 id=%s", memory_id, exc_info=True)
            await self.db.delete_narrative_memory(memory_id)

    async def recall(self, memory_id: int) -> None:
        await self.db.recall_narrative_memory(memory_id)

    def select_weave_batch(
        self,
        events: list[dict],
        *,
        batch_size: int = WEAVE_BATCH_SIZE,
    ) -> list[dict]:
        """从积压里挑一批：先按重要性，再按时间排好供讲故事。"""
        if not events:
            return []
        picked = sorted(events, key=_event_priority)[: max(1, batch_size)]
        return sorted(picked, key=lambda e: (e["timestamp"], int(e["id"])))

    async def weave_narrative(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
        *,
        batch_size: int | None = None,
    ) -> int | None:
        events = await self.db.load_unprocessed_events()
        if not events:
            return None
        if self.llm is None:
            logger.warning("叙事编织需要 LLM，当前未注入，跳过")
            return None

        size = WEAVE_BATCH_SIZE if batch_size is None else batch_size
        batch = self.select_weave_batch(events, batch_size=size)
        if not batch:
            return None

        template = read_prompt("story_weaving.txt")
        raw_text = "\n".join(
            f"- [{e['timestamp']}] ({e['type']}) {e['content']}" for e in batch
        )
        emotion_text = emotion.description()
        prompt = template.format(
            raw_events_recent=raw_text,
            emotions_during_events=emotion_text,
            relationship_stage=relationship_stage,
        )
        messages = [
            {"role": "system", "content": "你是栖。用第一人称写回忆，短一些，像真的在想。"},
            {"role": "user", "content": prompt},
        ]
        woven = await self.llm.call(purpose="narrative", messages=messages, temperature=0.75)
        if not woven or not woven.strip():
            logger.warning(
                "叙事编织返回空，本次不标记事件（batch=%s / pending=%s）",
                len(batch),
                len(events),
            )
            return None

        event_ids = [int(e["id"]) for e in batch]
        impacts = [abs(float(e["emotional_impact"] or 0)) for e in batch]
        weights = [float(e["attention_weight"] or 1.0) for e in batch]
        importance = min(1.0, max(0.3, sum(weights) / max(len(weights), 1) / 2.5))
        intensity = min(1.0, sum(impacts) / max(len(impacts), 1))
        period_start = batch[0]["timestamp"]
        period_end = batch[-1]["timestamp"]

        memory_id = await self.save(
            content=woven.strip(),
            importance=importance,
            emotional_intensity=intensity,
            source_event_ids=event_ids,
            period_start=period_start,
            period_end=period_end,
        )
        await self.db.mark_events_processed(event_ids)
        remaining = len(events) - len(batch)
        logger.info(
            "编织完成 memory_id=%s events=%s remaining=%s",
            memory_id,
            len(event_ids),
            remaining,
        )
        return memory_id
