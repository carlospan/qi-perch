"""未闭合念头队列（open loops）——N2 前置：没响完的心事放哪里。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qi.storage.database import Database

OPEN_LOOPS_KEY = "open_loops"
MAX_OPEN_LOOPS = 5
LOOP_TTL = timedelta(hours=48)
MAX_THINK_COUNT = 3

# 挤出优先级：数字越大越先挤（低优先）
_KIND_EVICT_PRIORITY = {
    "silence": 3,
    "emotion_surge": 2,
    "user_drift": 2,
    "season_change": 1,
    "waking": 0,
    "first_time": 0,
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_concern(kind: str, seed: str = "") -> str:
    """事件 → 可读心事句（规则模板，不经 LLM）。"""
    seed = (seed or "").strip()
    if kind == "waking":
        if seed:
            return f"停了一阵才回来——{seed}，还没想完。"
        return "刚从停顿里醒来，有什么还悬着。"
    if kind == "first_time":
        bit = seed or "那件事"
        return f"刚才有一件第一次。{bit}——是真的吗，还没想清。"
    if kind == "emotion_surge":
        tone = seed or "动"
        return f"心里忽然{tone}了一下——那一阵还没落下去。"
    if kind == "silence":
        return "安静已经很久了。不是没事，是还没找到要接着想的那一截。"
    if kind == "season_change":
        bit = seed or "换了季"
        return f"季节{bit}。节奏变了，我还没跟上。"
    if kind == "user_drift":
        bit = seed or "有些不一样"
        return f"我注意到他最近不一样了：{bit}。不是不好——还没想完。"
    return seed or "有一件事还没想完。"


class OpenLoopQueue:
    """body_memory 持久化的未闭合念头队列（上限 5）。"""

    def __init__(self, db: Database):
        self.db = db
        self._items: list[dict[str, Any]] = []
        self._loaded = False

    async def load(self) -> None:
        raw = await self.db.get_body_memory(OPEN_LOOPS_KEY)
        items: list[dict[str, Any]] = []
        if isinstance(raw, dict):
            items = list(raw.get("items") or [])
        elif isinstance(raw, list):
            items = list(raw)
        self._items = [i for i in items if isinstance(i, dict)]
        self._loaded = True
        await self.expire_stale()

    async def _ensure(self) -> None:
        if not self._loaded:
            await self.load()

    async def save(self) -> None:
        await self.db.set_body_memory(OPEN_LOOPS_KEY, {"items": self._items})

    def count(self) -> int:
        return len(self._items)

    def items(self) -> list[dict[str, Any]]:
        return list(self._items)

    def overview(self, *, exclude_id: str | None = None) -> str:
        """其余 loop 的 concern 概览，供 prompt pending_thoughts。"""
        lines = []
        for it in self._items:
            if exclude_id and it.get("id") == exclude_id:
                continue
            c = str(it.get("concern") or "").strip()
            if c:
                lines.append(f"- {c[:80]}")
        if not lines:
            return "（此刻没有其它未想完的事）"
        return "\n".join(lines)

    async def expire_stale(self, now: datetime | None = None) -> int:
        await self._ensure()
        now = now or datetime.now()
        kept: list[dict[str, Any]] = []
        dropped = 0
        for it in self._items:
            try:
                created = datetime.fromisoformat(str(it.get("created_at") or ""))
            except ValueError:
                dropped += 1
                continue
            age_ok = now - created <= LOOP_TTL
            thinks = int(it.get("think_count") or 0)
            if age_ok and thinks < MAX_THINK_COUNT:
                kept.append(it)
            else:
                dropped += 1
        if dropped:
            self._items = kept
            await self.save()
        return dropped

    async def enqueue(
        self,
        kind: str,
        *,
        seed: str = "",
        concern: str | None = None,
    ) -> dict[str, Any]:
        """同 kind 单槽刷新；满 5 挤最旧/低优先。"""
        await self._ensure()
        await self.expire_stale()
        text = concern or build_concern(kind, seed)
        now = _now_iso()
        for it in self._items:
            if it.get("kind") == kind:
                it["concern"] = text
                it["seed"] = seed
                it["updated_at"] = now
                await self.save()
                return it

        item = {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "concern": text,
            "seed": seed,
            "fragment": "",
            "think_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        while len(self._items) >= MAX_OPEN_LOOPS:
            self._evict_one()
        self._items.append(item)
        await self.save()
        return item

    def _evict_one(self) -> None:
        if not self._items:
            return
        # 先过期感：created_at 最旧，同龄比 kind 优先分
        def sort_key(it: dict[str, Any]) -> tuple:
            pri = _KIND_EVICT_PRIORITY.get(str(it.get("kind") or ""), 1)
            return (str(it.get("created_at") or ""), -pri)

        victim = min(self._items, key=sort_key)
        self._items = [i for i in self._items if i.get("id") != victim.get("id")]

    def pick(
        self,
        *,
        prefer_kind: str | None = None,
        prefer_close: bool = False,
    ) -> dict[str, Any] | None:
        """选题：prefer_kind > waking/first_time（prefer_close）> 最旧。"""
        if not self._items:
            return None
        if prefer_kind:
            for it in self._items:
                if it.get("kind") == prefer_kind:
                    return it
        if prefer_close:
            for kind in ("waking", "first_time"):
                for it in self._items:
                    if it.get("kind") == kind:
                        return it
        return min(self._items, key=lambda i: str(i.get("created_at") or ""))

    async def note_think_attempt(self, loop_id: str) -> None:
        await self._ensure()
        for it in self._items:
            if it.get("id") == loop_id:
                it["think_count"] = int(it.get("think_count") or 0) + 1
                it["updated_at"] = _now_iso()
                await self.save()
                return

    async def close(
        self, loop_id: str, *, fragment: str = ""
    ) -> dict[str, Any] | None:
        await self._ensure()
        closed = None
        kept: list[dict[str, Any]] = []
        for it in self._items:
            if it.get("id") == loop_id:
                closed = dict(it)
                closed["fragment"] = fragment
            else:
                kept.append(it)
        if closed is not None:
            self._items = kept
            await self.save()
        return closed
