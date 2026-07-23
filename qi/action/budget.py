"""行动预算——自主行动比言语更稀有。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# 言语主动日限是 3（ProactiveGate / contract 第 28 条）。
# 自主行动应更紧：默认 1 次/天。share / tend / explore 共享这一预算。
AUTONOMOUS_ACTION_DAILY_LIMIT = 1

# 响应式协助（assist）是「回应」，不占自主预算，但仍受 permission 门控。

BODY_MEMORY_KEY = "action_budget"


class ActionBudget:
    """
    决定今天还能不能自主伸手。
    与 ProactiveGate 同构：跨天重置、can / record、snapshot / restore；
    持久化走 body_memory key「action_budget」（由 Brain / ActionLayer 写入）。
    """

    def __init__(self, config: dict | None = None):
        action_cfg = (config or {}).get("action") or {}
        self.daily_limit = int(
            action_cfg.get("autonomous_daily_limit", AUTONOMOUS_ACTION_DAILY_LIMIT)
        )
        self.count_today = 0
        self.day: str | None = None
        self.last_kind: str | None = None
        self.last_at: datetime | None = None

    def reset_day(self, now: datetime) -> None:
        day = now.strftime("%Y-%m-%d")
        if self.day != day:
            self.day = day
            self.count_today = 0

    def can_autonomous(self, now: datetime) -> bool:
        self.reset_day(now)
        return self.count_today < self.daily_limit

    def record(self, kind: str, now: datetime) -> None:
        """记录一次自主行动。assist 不应调用此方法（响应式不占预算）。"""
        self.reset_day(now)
        self.count_today += 1
        self.last_kind = kind
        self.last_at = now

    def snapshot(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "count_today": self.count_today,
            "last_kind": self.last_kind,
            "last_at": self.last_at.isoformat() if self.last_at else None,
        }

    def restore(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        self.day = data.get("day")
        self.count_today = int(data.get("count_today") or 0)
        self.last_kind = data.get("last_kind")
        raw = data.get("last_at")
        if raw:
            try:
                self.last_at = datetime.fromisoformat(str(raw))
            except ValueError:
                self.last_at = None
        else:
            self.last_at = None
