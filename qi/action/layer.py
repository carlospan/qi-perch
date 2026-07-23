"""行动层协调器——意志伸手的那一拍。"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.budget import BODY_MEMORY_KEY, ActionBudget
from qi.action.explore import ExploreAction
from qi.action.share import ShareAction
from qi.action.tend import TendAction
from qi.action.volition import action_intentions

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action")

# 与 L5 SEASON_BEHAVIOR_HINTS 并列；可通过 config.action.season_scale 覆盖
SEASON_ACTION_SCALE = {
    "spring": 1.0,
    "summer": 0.8,
    "autumn": 0.5,
    "winter": 0.2,
}


def resolve_season_scale(season: str, config: dict | None = None) -> float:
    scales = dict(SEASON_ACTION_SCALE)
    cfg = ((config or {}).get("action") or {}).get("season_scale") or {}
    if isinstance(cfg, dict):
        scales.update({k: float(v) for k, v in cfg.items()})
    return float(scales.get(season, 1.0))


class ActionLayer:
    """
    tick：形成意图 → 门控/预算/季节 → 至多一个自主行动 → 留痕。
    LLM 不直接调工具；结果经 prompt_extras 注入下一轮对话。
    """

    def __init__(
        self,
        db: Database,
        config: dict | None = None,
        narrative: NarrativeMemory | None = None,
    ):
        self.db = db
        self.config = config or {}
        self.budget = ActionBudget(self.config)
        self.share = ShareAction(db, narrative=narrative)
        self.tend = TendAction(db, narrative=narrative)
        self.explore = ExploreAction(db, narrative=narrative)
        self.last_result: dict | None = None

    def season_scale(self, season: str) -> float:
        return resolve_season_scale(season, self.config)

    async def detect_tend_occasion(
        self, season: str, now: datetime
    ) -> str | None:
        """相识纪念日或季节更替；由调用方/本层给出 occasion。"""
        last_season = await self.db.get_body_memory("tend_last_season")
        if last_season != season:
            return f"season:{season}"

        firsts = await self.db.list_first_times()
        if firsts:
            raw = firsts[0].get("timestamp")
            try:
                t0 = datetime.fromisoformat(str(raw))
            except ValueError:
                t0 = None
            if t0 is not None and t0.month == now.month and t0.day == now.day:
                # 同一天首次相遇的周年；同年只记一次
                marked = await self.db.get_body_memory("tend_last_anniversary_year")
                if marked != now.year:
                    return "anniversary"
        return None

    async def _mark_tend_done(
        self, occasion: str, season: str, now: datetime
    ) -> None:
        if occasion.startswith("season:"):
            await self.db.set_body_memory("tend_last_season", season)
        elif occasion == "anniversary":
            await self.db.set_body_memory("tend_last_anniversary_year", now.year)

    async def tick(
        self,
        emotion: EmotionState,
        relationship_stage: str,
        season: str,
        now: datetime,
        *,
        mode: str,
        user_online: bool = True,
        scars: list[dict] | None = None,
    ) -> dict | None:
        """
        独处一拍：至多做一个自主行动。
        dreaming / 离线 → None。assist 不在此执行。
        """
        self.last_result = None
        if not user_online or mode == "dreaming":
            return None
        if mode not in ("solitary", "ambient"):
            # awake 偏对话；自主伸手留给独处气质
            return None
        if not self.budget.can_autonomous(now):
            return None

        undelivered = await self.db.load_unshared_creation()
        tend_occasion = await self.detect_tend_occasion(season, now)
        scale = self.season_scale(season)

        intents = action_intentions(
            mode=mode,
            relationship_stage=relationship_stage,
            curiosity=float(emotion.curiosity),
            valence=float(emotion.valence),
            has_undelivered_creation=undelivered is not None,
            tend_occasion=tend_occasion,
            user_message=None,
            budget=self.budget,
            now=now,
            season_scale=scale,
            scars=scars,
            user_online=user_online,
        )
        autos = [i for i in intents if i.kind != "assist"]
        if not autos:
            return None

        chosen = autos[0]
        # 软门控：priority（已含季节缩放）作概率；冬天几乎不动手
        if random.random() > min(1.0, max(0.0, chosen.priority)):
            return None

        result: dict | None = None
        if chosen.kind == "share":
            result = await self.share.try_share(
                emotion,
                relationship_stage,
                self.budget,
                season=season,
                now=now,
            )
        elif chosen.kind == "tend" and tend_occasion:
            result = await self.tend.tend(
                tend_occasion, emotion, season, now=now, speak=False
            )
            if result is not None:
                self.budget.record("tend", now)
                await self._mark_tend_done(tend_occasion, season, now)
        elif chosen.kind == "explore":
            result = await self.explore.drift(
                float(emotion.curiosity),
                emotion,
                season,
                season_scale=scale,
                now=now,
            )
            if result is not None:
                self.budget.record("explore", now)

        self.last_result = result
        return result

    async def prompt_extras(self, limit: int = 3) -> dict[str, str]:
        """栖最近做过的事——经历背景，不报流水账。"""
        rows = await self.db.list_recent_actions(limit=limit)
        if not rows:
            return {"recent_actions": "（最近没有特别伸过手）"}
        # 时间倒序已由 list_recent_actions 保证；用叙事摘要
        lines = []
        for row in rows:
            summary = str(row.get("summary") or "").strip()
            if summary:
                lines.append(f"- {summary}")
        if not lines:
            return {"recent_actions": "（最近没有特别伸过手）"}
        body = "\n".join(lines)
        return {
            "recent_actions": (
                "这些是你近来做过的事。知道就好，不必挂在嘴上，"
                "更不要当成任务清单念出来。\n" + body
            )
        }

    async def persist_budget(self) -> None:
        try:
            await self.db.set_body_memory(BODY_MEMORY_KEY, self.budget.snapshot())
        except Exception:
            logger.exception("行动预算持久化失败")

    async def restore_budget(self) -> None:
        data = await self.db.get_body_memory(BODY_MEMORY_KEY)
        if isinstance(data, dict):
            self.budget.restore(data)
