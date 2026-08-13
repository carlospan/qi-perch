"""行动预算——自主行动比言语更稀有。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# 言语主动日限是 3（ProactiveGate / contract 第 28 条）。
# 自主行动日限：默认 20。真实频率由可归档记忆量 / 独处门槛 /
# 在线时长等闸门限定，日限仅作安全阀，不参与行为塑造。
AUTONOMOUS_ACTION_DAILY_LIMIT = 20

# 响应式协助（assist）是「回应」，不占自主预算，但仍受 permission 门控。

BODY_MEMORY_KEY = "action_budget"

DEFAULT_KIND_WEIGHTS: dict[str, float] = {
    "share": 1.0,
    "tend": 1.0,
    "explore": 1.0,
    "look": 1.0,
}

WEIGHT_MIN = 0.2
WEIGHT_MAX = 1.5


def _clamp_weight(value: float) -> float:
    return max(WEIGHT_MIN, min(WEIGHT_MAX, float(value)))


class ActionBudget:
    """
    决定今天还能不能自主伸手。
    与 ProactiveGate 同构：跨天重置、can / record、snapshot / restore；
    持久化走 body_memory key「action_budget」（由 Brain / ActionLayer 写入）。
    kind_weights：对 share/tend/explore 意图优先级的缩放（包 8）。
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
        self.kind_weights: dict[str, float] = dict(DEFAULT_KIND_WEIGHTS)
        raw_weights = action_cfg.get("kind_weights")
        if isinstance(raw_weights, dict):
            for k, v in raw_weights.items():
                try:
                    self.kind_weights[str(k)] = _clamp_weight(float(v))
                except (TypeError, ValueError):
                    continue

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

    def weight_for(self, kind: str) -> float:
        return float(self.kind_weights.get(kind, 1.0))

    def set_kind_weight(self, kind: str, value: float) -> None:
        self.kind_weights[kind] = _clamp_weight(value)

    def weights_neutral(self) -> bool:
        for k, default in DEFAULT_KIND_WEIGHTS.items():
            if abs(self.weight_for(k) - default) > 1e-6:
                return False
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "count_today": self.count_today,
            "last_kind": self.last_kind,
            "last_at": self.last_at.isoformat() if self.last_at else None,
            "kind_weights": dict(self.kind_weights),
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
        weights = data.get("kind_weights")
        if isinstance(weights, dict):
            merged = dict(DEFAULT_KIND_WEIGHTS)
            for k, v in weights.items():
                try:
                    merged[str(k)] = _clamp_weight(float(v))
                except (TypeError, ValueError):
                    continue
            self.kind_weights = merged
