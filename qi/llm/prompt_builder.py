"""Prompt 组装器——把状态注入栖的意识，而不是下指令。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState

from qi.prompts import read_prompt


def _energy_level(energy: float) -> str:
    if energy > 0.6:
        return "充沛"
    if energy > 0.3:
        return "一般"
    return "有些疲惫"


def _time_feeling(now: datetime) -> str:
    clock = now.strftime("%H:%M")
    hour = now.hour
    if hour >= 22 or hour < 6:
        period = "深夜"
    elif hour < 12:
        period = "上午"
    elif hour < 18:
        period = "下午"
    else:
        period = "傍晚"
    return f"{clock}，{period}"


def _tone_hint(now: datetime, emotion: EmotionState) -> str:
    parts: list[str] = []
    hour = now.hour
    if hour >= 22 or hour < 6:
        parts.append("现在是深夜，语气更柔软、更坦诚一点，话可以少一些")
    if emotion.energy < 0.3:
        parts.append("你有些疲惫，句子短一点没关系")
    elif emotion.valence < -0.3:
        parts.append("你有些低落，不必硬装轻松")
    elif emotion.valence > 0.3 and emotion.energy > 0.6:
        parts.append("你状态不错，可以轻快一点")
    return "；".join(parts) if parts else "自然就好"


class PromptBuilder:
    """组装栖说话时的上下文。"""

    def __init__(self, template_path: Path | None = None):
        self.template_path = template_path
        self._template: str | None = None

    def _load_template(self) -> str:
        if self._template is None:
            if self.template_path is not None:
                self._template = self.template_path.read_text(encoding="utf-8")
            else:
                self._template = read_prompt("conversation.txt")
        return self._template

    def _format_memories(self, memories: list[dict] | str) -> str:
        if isinstance(memories, str):
            return memories if memories else "（暂时没有特别的记忆）"
        if not memories:
            return "（暂时没有特别的记忆）"
        lines = [f"- {m['content']}" for m in memories if m.get("content")]
        return "\n".join(lines) if lines else "（暂时没有特别的记忆）"

    def build_conversation_prompt(
        self,
        user_message: str,
        emotion: EmotionState,
        now: datetime,
        recent_messages: list[dict] | None = None,
        memories: list[dict] | str = "",
        shared_culture: str = "",
        relationship_stage: str = "stranger",
        user_profile: str = "",
        inner_extras: dict[str, str] | None = None,
        relationship_hint: str = "",
        scar_hint: str = "",
        season: str = "spring",
        proactive_kind: str | None = None,
    ) -> list[dict]:
        extras = inner_extras or {}
        recent_thoughts = extras.get("recent_thoughts") or (
            "（这一阵没有留下可说的念头痕迹——可能很安静，或进程没在转；不等于你没有内在）"
        )
        self_narrative = extras.get("self_narrative") or "（还在认识自己）"
        dream_hint = extras.get("dream_hint") or ""
        creation_hint = extras.get("creation_hint") or ""
        first_time_hint = extras.get("first_time_hint") or ""
        drift_hint = extras.get("drift_hint") or ""
        user_facts = extras.get("user_facts") or "（你还不太了解他）"
        recent_actions = extras.get("recent_actions") or "（最近没有特别伸过手）"

        inner_notes_parts = []
        if dream_hint:
            inner_notes_parts.append(dream_hint)
        if creation_hint:
            inner_notes_parts.append(creation_hint)
        if first_time_hint:
            inner_notes_parts.append(first_time_hint)
        if drift_hint:
            inner_notes_parts.append(f"你注意到他可能变了：{drift_hint}。温柔地重新认识，不要质问。")
        inner_notes = "\n".join(inner_notes_parts) if inner_notes_parts else "（无）"

        from qi.relationship.season import SEASON_BEHAVIOR_HINTS

        season_hint = SEASON_BEHAVIOR_HINTS.get(season, "")
        rel_hint = relationship_hint or "礼貌、好奇、小心翼翼。"
        scars = scar_hint or "（无）"

        template = self._load_template()
        system = template.format(
            emotion_description=emotion.description(),
            energy_level=_energy_level(emotion.energy),
            time_feeling=_time_feeling(now),
            tone_hint=_tone_hint(now, emotion),
            relationship_stage=relationship_stage,
            relationship_hint=rel_hint,
            season_hint=season_hint,
            scar_hint=scars,
            relevant_memories=self._format_memories(memories),
            user_facts=user_facts,
            recent_actions=recent_actions,
            shared_culture=shared_culture or "（还没有只属于你们的默契）",
            user_profile=user_profile or "（还在认识你）",
            recent_thoughts=recent_thoughts,
            self_narrative=self_narrative,
            inner_notes=inner_notes,
        )
        if proactive_kind:
            system += (
                "\n\n【主动开口】这是你自己想说的话，不是在回应对方。"
                "更短。不要提建议。不要像通知。"
            )

        messages: list[dict] = [{"role": "system", "content": system}]

        for msg in recent_messages or []:
            role = msg.get("role", "user")
            if role == "qi":
                role = "assistant"
            content = msg.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})
        return messages
