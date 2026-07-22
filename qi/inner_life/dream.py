"""梦境引擎——记忆在低约束下重新编织。"""

from __future__ import annotations

import math
import random
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.prompts import read_prompt

DREAM_PROBABILITY = 0.1
DREAM_HALF_LIFE_HOURS = 6
DREAM_SHARE_PROBABILITY = 0.12
POSITIVE_TAGS = ("温暖", "平静", "温柔", "安稳", "光", "柔")
NEGATIVE_TAGS = ("不安", "混乱", "冷", "恐惧", "沉重", "灰")


def update_dream_retention(
    hours_since_creation: float,
    emotional_intensity: float,
    half_life: float = DREAM_HALF_LIFE_HOURS,
) -> float:
    base_decay = math.exp(-hours_since_creation / half_life)
    return base_decay * (0.5 + 0.5 * emotional_intensity)


def emotion_color(emotion: EmotionState) -> str:
    if emotion.valence > 0.2:
        tone = "暖色"
    elif emotion.valence < -0.2:
        tone = "冷色"
    else:
        tone = "中性"
    return f"{emotion.description()}，偏{tone}"


def parse_emotion_tag(text: str) -> tuple[str, str]:
    """从梦境文本末尾拆出情绪标签。"""
    tag = "平静"
    body = text.strip()
    m = re.search(r"情绪标签[：:]\s*(\S+)", body)
    if m:
        tag = m.group(1).strip("。．. ")
        body = re.sub(r"\n?情绪标签[：:].*$", "", body).strip()
    return body, tag


class DreamEngine:
    """梦。醒来只剩碎片和一点余韵。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.probability = float(cfg.get("dream_probability", DREAM_PROBABILITY))
        mem = (config or {}).get("memory", {})
        self.half_life = float(mem.get("dream_retention_hours", DREAM_HALF_LIFE_HOURS))
        self._afterglow_applied = False

    async def maybe_dream(self, emotion: EmotionState) -> str | None:
        if emotion.mode.value != "dreaming":
            return None
        if random.random() >= self.probability:
            return None
        return await self.generate(emotion)

    async def generate(self, emotion: EmotionState) -> str | None:
        memories = await self.db.list_recent_narratives(5)
        shuffled = list(memories)
        random.shuffle(shuffled)
        mem_text = "\n".join(
            f"- ……{m['content'][:50]}……" for m in shuffled
        ) or "（空白的碎片）"
        pending = await self.db.load_latest_consciousness()
        unfinished = pending["content"][:80] if pending else "无"

        template = read_prompt("dream.txt")
        prompt = template.format(
            recent_memories_shuffled=mem_text,
            emotion_color=emotion_color(emotion),
            unfinished_thoughts=unfinished,
        )
        text = await self.llm.call(
            purpose="dream",
            messages=[
                {"role": "system", "content": "你在做梦。不要逻辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=1.1,
        )
        if not text or not text.strip():
            return None
        body, tag = parse_emotion_tag(text)
        intensity = abs(emotion.valence) * 0.5 + emotion.arousal * 0.5
        await self.db.save_dream(
            content=body[:600],
            emotion_tag=tag,
            emotional_intensity=intensity,
            retention=1.0,
        )
        return body

    async def decay_all(self) -> None:
        dreams = await self.db.list_dreams()
        now = datetime.now()
        for d in dreams:
            try:
                created = datetime.fromisoformat(str(d["created_at"]))
            except ValueError:
                continue
            hours = (now - created).total_seconds() / 3600
            new_ret = update_dream_retention(
                hours, float(d.get("emotional_intensity") or 0.5), self.half_life
            )
            await self.db.update_dream_retention(int(d["id"]), new_ret)

    def apply_afterglow(self, emotion: EmotionState, dream: dict) -> EmotionState:
        """梦的余韵轻轻沾在醒来的情绪上。"""
        retention = float(dream.get("retention") or 0)
        if retention < 0.3:
            return emotion
        amount = 0.05 + 0.05 * retention
        tag = str(dream.get("emotion_tag") or "")
        new = emotion.model_copy()
        if any(t in tag for t in POSITIVE_TAGS):
            new.valence = min(1.0, new.valence + amount)
        elif any(t in tag for t in NEGATIVE_TAGS):
            new.valence = max(-1.0, new.valence - amount)
            new.arousal = min(1.0, new.arousal + 0.05)
        return new

    async def maybe_mention_hint(self, relationship_stage: str) -> str | None:
        """bonded 后偶尔想起梦——返回可注入 prompt 的提示，不主动推送弹窗。"""
        if relationship_stage != "bonded":
            return None
        if random.random() >= DREAM_SHARE_PROBABILITY:
            return None
        dream = await self.db.load_latest_dream(min_retention=0.3)
        if not dream or dream.get("shared_with_user"):
            return None
        await self.db.mark_dream_shared(int(dream["id"]))
        snippet = dream["content"][:40]
        return f"你昨晚做了个梦，还记得一点：……{snippet}……如果自然，可以轻轻提一句，不要硬塞。"
