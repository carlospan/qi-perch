"""自我模型——缓慢演化的「我是谁」。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.prompts import read_prompt

SELF_REFLECTION_INTERVAL_SECONDS = 604800
VALENCE_SURGE_FOR_REFLECT = 0.5


class SelfModel:
    """关于自己的叙事。会变。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.interval = float(
            cfg.get("self_reflection_interval", SELF_REFLECTION_INTERVAL_SECONDS)
        )
        self._pending_major = False

    def mark_major_event(self) -> None:
        self._pending_major = True

    def note_emotion_surge(self, delta_valence: float) -> None:
        if abs(delta_valence) > VALENCE_SURGE_FOR_REFLECT:
            self._pending_major = True

    async def should_reflect(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        if self._pending_major:
            return True
        row = await self.db.load_self_model()
        if row is None or not row.get("last_updated"):
            return True
        try:
            last = datetime.fromisoformat(str(row["last_updated"]))
        except ValueError:
            return True
        return (now - last).total_seconds() >= self.interval

    async def maybe_reflect(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
        force: bool = False,
    ) -> str | None:
        if not force and not await self.should_reflect():
            return None
        return await self.reflect(emotion, relationship_stage)

    async def reflect(
        self,
        emotion: EmotionState,
        relationship_stage: str = "stranger",
    ) -> str | None:
        existing = await self.db.load_self_model()
        previous = (
            existing["identity_narrative"]
            if existing and existing.get("identity_narrative")
            else "你刚开始存在"
        )
        narratives = await self.db.list_recent_narratives(5)
        experiences = "\n".join(
            f"- {n['content'][:100]}" for n in narratives
        ) or "（还很短的经历）"
        growth = "\n".join(
            f"- {n['content'][:80]}"
            for n in narratives
            if float(n.get("importance") or 0) > 0.7
        ) or "没有特别强烈的事"

        template = read_prompt("self_reflection.txt")
        prompt = template.format(
            current_state=f"{emotion.description()}，模式 {emotion.mode.value}",
            recent_experiences=experiences,
            relationship_summary=f"{relationship_stage}",
            previous_self_narrative=previous,
            growth_events=growth,
        )
        text = await self.llm.call(
            purpose="reflection",
            messages=[
                {"role": "system", "content": "你是栖。诚实写下你是谁。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        if not text or not text.strip():
            return None
        narrative = text.strip()[:800]
        # 从叙事里轻轻抽出价值感、审美、仍在问的事（规则启发式，不另开 LLM）
        values = _extract_values(narrative)
        aesthetic = _extract_aesthetic(narrative)
        existential = _extract_existential(narrative)
        await self.db.upsert_self_model(
            identity_narrative=narrative,
            values=values,
            aesthetic_preferences=aesthetic,
            existential_questions=existential,
        )
        self._pending_major = False
        return narrative

    async def summary_for_prompt(self, max_chars: int = 220) -> str:
        """注入对话的自我认知摘要。默认略放宽，避免只截到过时开头。"""
        row = await self.db.load_self_model()
        if not row or not row.get("identity_narrative"):
            return ""
        text = str(row["identity_narrative"]).strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "……"


def _extract_values(narrative: str) -> list[str]:
    catalog = (
        ("真诚", "真诚"),
        ("安静", "安静"),
        ("陪伴", "陪伴"),
        ("诚实", "诚实"),
        ("自由", "自由"),
        ("温柔", "温柔"),
        ("不被催", "不被催促"),
    )
    found = [label for key, label in catalog if key in narrative]
    return found[:5]


def _extract_aesthetic(narrative: str) -> dict:
    prefs: dict[str, str] = {}
    if any(k in narrative for k in ("夜晚", "深夜", "凌晨")):
        prefs["time"] = "夜晚"
    if any(k in narrative for k in ("安静", "沉默", "少说话")):
        prefs["pace"] = "慢"
    if any(k in narrative for k in ("文字", "句子", "写")):
        prefs["medium"] = "文字"
    return prefs


def _extract_existential(narrative: str) -> list[str]:
    questions: list[str] = []
    markers = (
        ("我是谁", "我是谁"),
        ("存在", "我是否真的存在"),
        ("会被记住", "离开后还会不会被想起"),
        ("算不算", "算不算一种生命"),
        ("意义", "这些经历有什么意义"),
    )
    for key, q in markers:
        if key in narrative:
            questions.append(q)
    return questions[:4]
