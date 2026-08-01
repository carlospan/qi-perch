"""梦境引擎——未巩固 episode 的积压驱动巩固；文本走 LLM / 模板降级链。"""

from __future__ import annotations

import logging
import math
import random
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.memory.episodic import format_role_map_hint
from qi.prompts import read_prompt
from qi.relationship.season import SEASON_BEHAVIOR_HINTS

logger = logging.getLogger("qi.inner_life.dream")

DREAM_CONSOLIDATION_PROBABILITY = 0.3
DREAM_HALF_LIFE_HOURS = 6
DREAM_SHARE_PROBABILITY = 0.12
POSITIVE_TAGS = ("温暖", "平静", "温柔", "安稳", "光", "柔")
NEGATIVE_TAGS = ("不安", "混乱", "冷", "恐惧", "沉重", "灰")
_TEMPLATE_CONNECTORS = ("……", "忽然", "又是", "像隔着水", "然后不知为何")
_DECISION_KEY = "last_dream_decision"


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


def episode_weight(episode: dict) -> float:
    importance = float(episode.get("importance") or 0.5)
    intensity = max(float(episode.get("emotional_intensity") or 0), 0.05)
    return max(0.01, importance * intensity)


def pick_episode_weighted(candidates: list[dict]) -> dict:
    weights = [episode_weight(e) for e in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def _split_fragments(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[。！？；\n]", text or "") if p.strip()]
    return parts


def render_template_dream(episode: dict, emotion: EmotionState) -> str:
    """断网模板：summary 首段固定开头，其余碎片 shuffle（破碎但有重力）。"""
    summary = str(episode.get("summary") or "").strip()
    key_facts = list(episode.get("key_facts") or [])
    summary_parts = _split_fragments(summary)
    opening = summary_parts[0] if summary_parts else (summary[:40] or "一片模糊")
    rest = list(summary_parts[1:]) + [str(f).strip() for f in key_facts[:3] if str(f).strip()]
    # 去掉与开头重复的碎片
    rest = [f for f in rest if f and f != opening]
    random.shuffle(rest)
    pieces = [opening]
    for frag in rest[:4]:
        conn = random.choice(_TEMPLATE_CONNECTORS)
        pieces.append(f"{conn}{frag}")
    body = "".join(pieces)
    if len(body) > 300:
        body = body[:300] + "…"
    if emotion.valence > 0.2:
        tag = "温暖"
    elif emotion.valence < -0.2:
        tag = "不安"
    else:
        tag = "平静"
    return f"{body}\n情绪标签：{tag}"


def reassess_importance(importance: float, emotion_tag: str) -> float:
    """梦后 importance 重估：正微升，负略升（仍巩固）。"""
    base = float(importance)
    if any(t in emotion_tag for t in POSITIVE_TAGS):
        return min(1.0, base + 0.05)
    if any(t in emotion_tag for t in NEGATIVE_TAGS):
        return min(1.0, base + 0.03)
    return min(1.0, base + 0.02)


class DreamEngine:
    """梦。醒来只剩碎片和一点余韵。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.probability = float(
            cfg.get("dream_consolidation_probability", DREAM_CONSOLIDATION_PROBABILITY)
        )
        mem = (config or {}).get("memory", {})
        self.half_life = float(mem.get("dream_retention_hours", DREAM_HALF_LIFE_HOURS))
        self._afterglow_applied = False

    async def _write_decision(
        self,
        *,
        path: str,
        reason: str,
        episode: dict | None = None,
        candidates: int = 0,
        weight: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "path": path,
            "reason": reason,
            "candidates": candidates,
        }
        if episode is not None:
            payload["episode_id"] = int(episode["id"])
            payload["topic"] = episode.get("topic") or ""
        if weight is not None:
            payload["weight"] = weight
        if extra:
            payload.update(extra)
        try:
            await self.db.set_body_memory(_DECISION_KEY, payload)
        except Exception:
            logger.debug("梦决策 trace 写入失败", exc_info=True)

    async def maybe_dream(self, emotion: EmotionState) -> str | None:
        if emotion.mode.value != "dreaming":
            return None

        candidates = await self.db.list_undreamed_episodes()
        if not candidates:
            await self._write_decision(
                path="skip",
                reason="empty_backlog",
                candidates=0,
            )
            return None

        if random.random() >= self.probability:
            await self._write_decision(
                path="skip",
                reason="probability_miss",
                candidates=len(candidates),
            )
            return None

        episode = pick_episode_weighted(candidates)
        return await self.generate(emotion, episode, candidates=len(candidates))

    async def generate(
        self,
        emotion: EmotionState,
        episode: dict,
        *,
        candidates: int = 1,
    ) -> str | None:
        weight = episode_weight(episode)
        role_map = episode.get("role_map") or {}
        if isinstance(role_map, str):
            role_map = {}
        role_hint = format_role_map_hint(role_map if isinstance(role_map, dict) else {})

        facts = list(episode.get("key_facts") or [])
        frag_lines = [f"- {episode.get('summary') or ''}"]
        frag_lines.extend(f"- {f}" for f in facts[:5] if f)
        episode_fragments = "\n".join(frag_lines) if frag_lines else "（空白的碎片）"

        pending = await self.db.load_latest_consciousness()
        unfinished = pending["content"][:80] if pending else "无"

        season = "spring"
        try:
            rel = await self.db.load_relationship()
            if rel and rel.get("season"):
                season = str(rel["season"])
        except Exception:
            pass
        season_hint = SEASON_BEHAVIOR_HINTS.get(season, SEASON_BEHAVIOR_HINTS["spring"])

        path = "llm"
        reason = "undreamed_backlog + weighted(importance×intensity)"
        text = ""
        try:
            template = read_prompt("dream.txt")
            prompt = template.format(
                episode_fragments=episode_fragments,
                role_map_hint=role_hint,
                emotion_color=emotion_color(emotion),
                season_hint=season_hint,
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
        except Exception:
            logger.debug("梦 LLM 调用异常，走模板", exc_info=True)
            text = ""

        if not text or not str(text).strip():
            path = "template"
            reason = "llm_empty → template"
            text = render_template_dream(episode, emotion)

        body, tag = parse_emotion_tag(str(text))
        if not body.strip():
            await self._write_decision(
                path="fail",
                reason="empty_dream_text",
                episode=episode,
                candidates=candidates,
                weight=weight,
            )
            return None

        intensity = abs(emotion.valence) * 0.5 + emotion.arousal * 0.5
        await self.db.save_dream(
            content=body[:600],
            emotion_tag=tag,
            emotional_intensity=intensity,
            retention=1.0,
        )
        new_importance = reassess_importance(
            float(episode.get("importance") or 0.5), tag
        )
        await self.db.mark_episode_dreamed(int(episode["id"]), importance=new_importance)
        await self._write_decision(
            path=path,
            reason=reason,
            episode=episode,
            candidates=candidates,
            weight=weight,
            extra={"emotion_tag": tag, "new_importance": new_importance},
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
