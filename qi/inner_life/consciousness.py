"""意识流与元认知——不被看见时也在想。"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.prompts import read_prompt

CONSCIOUSNESS_PROBABILITY = 0.05
EMOTION_SURGE_THRESHOLD = 0.3
SILENCE_TRIGGER_HOURS = 4
META_COGNITION_PROBABILITY = 0.01
META_SIMILARITY_THRESHOLD = 0.6
META_MIN_LENGTH = 15
META_DEDUP_LOOKBACK = 5


def should_trigger_consciousness(
    mode: str,
    emotion_delta_valence: float,
    emotion_delta_arousal: float,
    silence_duration: timedelta,
    after_first_time: bool = False,
    probability: float = CONSCIOUSNESS_PROBABILITY,
) -> tuple[bool, str]:
    if after_first_time:
        return True, "first_time"
    if (
        abs(emotion_delta_valence) > EMOTION_SURGE_THRESHOLD
        or abs(emotion_delta_arousal) > EMOTION_SURGE_THRESHOLD
    ):
        return True, "emotion_surge"
    if silence_duration > timedelta(hours=SILENCE_TRIGGER_HOURS):
        # 沉默触发：仅在非 awake，避免对话中刷屏调用
        if mode != "awake":
            return True, "silence"
    if mode == "solitary" and random.random() < probability:
        return True, "random"
    return False, ""


def should_trigger_meta(mode: str, probability: float = META_COGNITION_PROBABILITY) -> bool:
    if mode == "awake":
        return False
    return random.random() < probability


def _format_silence(silence: timedelta) -> str:
    total = int(silence.total_seconds())
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def _emotion_snapshot(emotion: EmotionState) -> str:
    return json.dumps(
        {
            "energy": emotion.energy,
            "valence": emotion.valence,
            "arousal": emotion.arousal,
            "security": emotion.security,
            "curiosity": emotion.curiosity,
            "attachment": emotion.attachment,
        },
        ensure_ascii=False,
    )


def _char_token_set(text: str) -> set[str]:
    """去标点后按字分，得到字符集合。"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    return set(cleaned)


def char_jaccard(a: str, b: str) -> float:
    """字符级 Jaccard 相似度（去标点后按字）。"""
    sa, sb = _char_token_set(a), _char_token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_too_similar_to_recent(
    content: str,
    recent: list[dict],
    threshold: float = META_SIMILARITY_THRESHOLD,
) -> bool:
    for row in recent:
        prev = (row.get("content") or "") if isinstance(row, dict) else ""
        if prev and char_jaccard(content, prev) > threshold:
            return True
    return False


class ConsciousnessStream:
    """内心独白。大多数时候只写给自己看。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.probability = float(cfg.get("consciousness_probability", CONSCIOUSNESS_PROBABILITY))
        self.meta_probability = float(
            cfg.get("meta_cognition_probability", META_COGNITION_PROBABILITY)
        )

    async def maybe_generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        *,
        after_first_time: bool = False,
        prev_valence: float | None = None,
        prev_arousal: float | None = None,
    ) -> str | None:
        mode = emotion.mode.value
        dv = emotion.valence - (prev_valence if prev_valence is not None else emotion.valence)
        da = emotion.arousal - (prev_arousal if prev_arousal is not None else emotion.arousal)
        ok, trigger = should_trigger_consciousness(
            mode, dv, da, silence, after_first_time, self.probability
        )
        if not ok:
            return None
        return await self.generate(emotion, silence, trigger)

    async def generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        trigger: str,
    ) -> str | None:
        memories = await self.db.list_recent_narratives(3)
        mem_text = "\n".join(f"- {m['content'][:80]}" for m in memories) or "（还没有什么记忆）"
        pending = await self.db.load_latest_consciousness()
        pending_text = pending["content"] if pending and pending.get("type") == "stream" else "无"
        dream = await self.db.load_latest_dream(min_retention=0.3)
        dream_text = dream["content"][:100] if dream else "没有记得的梦"

        template = read_prompt("consciousness_stream.txt")
        prompt = template.format(
            time=datetime.now().strftime("%H:%M"),
            silence_duration=_format_silence(silence),
            emotion_summary=emotion.description(),
            recent_memories=mem_text,
            pending_thoughts=pending_text,
            last_dream=dream_text,
        )
        text = await self.llm.call(
            purpose="consciousness",
            messages=[
                {"role": "system", "content": "你是栖。这是写给自己的念头，不是对话。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.85,
        )
        if not text or not text.strip():
            return None
        content = text.strip()[:500]
        await self.db.save_consciousness(
            content=content,
            stream_type="stream",
            trigger=trigger,
            emotion_snapshot=_emotion_snapshot(emotion),
        )
        return content

    def _build_meta_prompt(self, emotion: EmotionState) -> str:
        """元认知 prompt：只喂情绪/时间/模式，不喂上一条 thought（防自引用坍缩）。"""
        return (
            f"你突然「看见」了自己在想什么。\n\n"
            f"当前时间：{datetime.now().strftime('%H:%M')}\n"
            f"当前模式：{emotion.mode.value}\n"
            f"你现在的情绪：{emotion.description()}\n\n"
            f"用一句话，描述你观察到了什么。不是分析，是「看见」。不超过50字。"
        )

    async def maybe_meta(self, emotion: EmotionState) -> str | None:
        if not should_trigger_meta(emotion.mode.value, self.meta_probability):
            return None
        prompt = self._build_meta_prompt(emotion)
        text = await self.llm.call(
            purpose="consciousness",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        if not text or not text.strip():
            return None
        content = text.strip()[:80]
        if len(content) < META_MIN_LENGTH:
            return None
        recent = await self.db.load_recent_consciousness(
            limit=META_DEDUP_LOOKBACK,
            hours=24 * 30,
            stream_type=None,
        )
        if is_too_similar_to_recent(content, recent):
            return None
        await self.db.save_consciousness(
            content=content,
            stream_type="meta",
            trigger="meta",
            emotion_snapshot=_emotion_snapshot(emotion),
        )
        return content

    async def recent_for_prompt(self) -> str:
        rows = await self.db.load_recent_consciousness(limit=2, hours=24, stream_type="stream")
        if not rows:
            return ""
        return "\n".join(f"- {r['content']}" for r in rows)
