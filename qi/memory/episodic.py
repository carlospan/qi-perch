"""情景 episode——编织时落下的方向保真骨架，供梦巩固使用。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qi.storage.database import Database

# raw_events 无 role 列：用 type 映射说话人（user_message → 他；其余 → 我）
_USER_EVENT_TYPES = frozenset({"user_message", "user"})
# 归因比对需要足够长的原话；过短截断会漏掉后半句指纹
_ROLE_MAP_SNIPPET_LEN = 160
_KEY_FACT_LEN = 80


def event_speaker(event: dict) -> str:
    """从事件 type 推断说话人：user | qi。"""
    t = str(event.get("type") or "").strip().lower()
    if t in _USER_EVENT_TYPES or t.startswith("user"):
        return "user"
    return "qi"


def build_role_map(events: list[dict]) -> dict[str, Any]:
    """聚合「谁说了什么」——结构上堵住叙事织反进入巩固素材。"""
    turns: list[dict[str, Any]] = []
    user_said: list[str] = []
    qi_said: list[str] = []
    for e in events:
        text = str(e.get("content") or "").strip()
        if not text:
            continue
        speaker = event_speaker(e)
        snippet = text[:_ROLE_MAP_SNIPPET_LEN]
        turns.append(
            {
                "speaker": speaker,
                "text": snippet,
                "event_id": int(e["id"]) if e.get("id") is not None else None,
            }
        )
        if speaker == "user":
            user_said.append(snippet)
        else:
            qi_said.append(snippet)
    return {
        "turns": turns,
        "user_said": user_said,
        "qi_said": qi_said,
    }


def format_role_map_hint(role_map: dict | None) -> str:
    """梦 prompt / 模板用的硬约束文案。

    两侧都带「说」字，避免「我：「…」」被模型当成待换位的用户原话。
    """
    if not role_map:
        return "（无明确对话方向）"
    lines = ["事实方向（不可反）："]
    for t in role_map.get("turns") or []:
        who = "他说" if t.get("speaker") == "user" else "我说"
        text = str(t.get("text") or "").strip()
        if text:
            lines.append(f"{who}：「{text}」")
    if len(lines) == 1:
        return "（无明确对话方向）"
    return "\n".join(lines)


def _first_sentence(text: str, max_len: int = 40) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    parts = re.split(r"[。！？\n]", body, maxsplit=1)
    head = (parts[0] if parts else body).strip()
    if len(head) > max_len:
        return head[:max_len] + "…"
    return head or body[:max_len]


class EpisodicMemory:
    """编织成功后同步一条 closed episode。"""

    def __init__(self, db: Database):
        self.db = db

    async def create_from_weave(
        self,
        events: list[dict],
        *,
        narrative_id: int,
        woven: str,
        importance: float,
        emotional_intensity: float,
    ) -> int:
        role_map = build_role_map(events)
        # 带说话人前缀，避免梦/召回把无标签事实安到错误主语上
        key_facts: list[str] = []
        for e in events:
            text = str(e.get("content") or "").strip()
            if not text:
                continue
            who = "用户" if event_speaker(e) == "user" else "栖"
            key_facts.append(f"{who}：{text[:_KEY_FACT_LEN]}")
        topic = _first_sentence(woven, 40)
        summary = woven.strip()[:200]
        start_ts = str(events[0]["timestamp"]) if events else None
        end_ts = str(events[-1]["timestamp"]) if events else None
        event_ids = [int(e["id"]) for e in events]
        return await self.db.save_episode(
            start_ts=start_ts,
            end_ts=end_ts,
            topic=topic,
            summary=summary,
            key_facts=key_facts,
            role_map=role_map,
            status="closed",
            dreamed=0,
            importance=importance,
            emotional_intensity=emotional_intensity,
            narrative_id=narrative_id,
            source_event_ids=event_ids,
        )
