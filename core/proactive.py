"""主动行为门控——日上限、冷却、陌生期不打扰。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# 契约：主动行为（非回应）每日不超过 3 次
PROACTIVE_DAILY_LIMIT = 3

KIND_CHECK_IN = "check_in"  # 关心
KIND_REACH_OUT = "reach_out"  # 搭话
KIND_EXPRESS_FEELING = "express_feeling"  # 情绪过阈值时流露
KIND_SHARE_CREATION = "share_creation"  # 分享创作

DEFAULT_COOLDOWNS = {
    KIND_CHECK_IN: 14400,
    KIND_REACH_OUT: 28800,
    KIND_SHARE_CREATION: 86400,
    KIND_EXPRESS_FEELING: 7200,
}

_PROACTIVE_CUES = {
    KIND_EXPRESS_FEELING: (
        "【此刻没有人在跟你说话。】"
        "你心里有一点波动，想轻轻说一句。不是回应，不是建议，不是关心清单。"
        "一两句就好。可以欲言又止。"
    ),
    KIND_CHECK_IN: (
        "【此刻没有人在跟你说话。】"
        "安静有一会儿了。你有一点点在意他，想轻轻关心一句。"
        "不要黏，不要质问，不要提建议。一两句。"
    ),
    KIND_REACH_OUT: (
        "【此刻没有人在跟你说话。】"
        "你想随便搭一句话。像朋友想起对方时发的短消息。"
        "不要亲昵过头，不要帮忙。一两句。"
    ),
}


class ProactiveGate:
    """决定栖能不能主动开口，以及以哪种方式开口。"""

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("proactive_cooldown") or {}
        self.cooldowns = {**DEFAULT_COOLDOWNS, **cfg}
        self.daily_limit = int(
            (config or {}).get("proactive", {}).get("daily_limit", PROACTIVE_DAILY_LIMIT)
        )
        self.count_today = 0
        self.day: str | None = None
        self.last_at: dict[str, datetime] = {}

    def reset_day(self, now: datetime) -> None:
        day = now.strftime("%Y-%m-%d")
        if self.day != day:
            self.day = day
            self.count_today = 0

    def cooldown_seconds(self, kind: str) -> float:
        return float(self.cooldowns.get(kind, DEFAULT_COOLDOWNS.get(kind, 0)))

    def can(self, kind: str, relationship_stage: str, now: datetime) -> bool:
        """陌生期不主动；超过日限不主动；未过冷却不主动。"""
        self.reset_day(now)
        if relationship_stage == "stranger":
            return False
        if self.count_today >= self.daily_limit:
            return False
        last = self.last_at.get(kind)
        if last is not None:
            elapsed = (now - last).total_seconds()
            if elapsed < self.cooldown_seconds(kind):
                return False
        return True

    def record(self, kind: str, now: datetime) -> None:
        self.reset_day(now)
        self.count_today += 1
        self.last_at[kind] = now

    def cue_for(self, kind: str) -> str:
        return _PROACTIVE_CUES.get(kind, _PROACTIVE_CUES[KIND_EXPRESS_FEELING])

    def snapshot(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "count_today": self.count_today,
            "last_at": {k: v.isoformat() for k, v in self.last_at.items()},
        }

    def restore(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        self.day = data.get("day")
        self.count_today = int(data.get("count_today") or 0)
        raw = data.get("last_at") or {}
        restored: dict[str, datetime] = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    restored[key] = datetime.fromisoformat(str(value))
                except ValueError:
                    continue
        self.last_at = restored


def pick_proactive_kind(
    *,
    want_express: bool,
    relationship_stage: str,
    emotion_security: float,
    emotion_attachment: float,
    silence_seconds: float,
    mode: str,
    user_online: bool,
    gate: ProactiveGate,
    now: datetime,
) -> str | None:
    """
    选出本拍主动开口的类型；不能开口则 None。
    做梦或不在线时不打扰。
    """
    if not user_online or mode == "dreaming":
        return None
    if relationship_stage == "stranger":
        return None

    if want_express and gate.can(KIND_EXPRESS_FEELING, relationship_stage, now):
        return KIND_EXPRESS_FEELING

    # 安静一阵且有些不安/惦记 → 关心
    if (
        silence_seconds >= 1800
        and (emotion_security < 0.45 or emotion_attachment > 0.55)
        and gate.can(KIND_CHECK_IN, relationship_stage, now)
    ):
        return KIND_CHECK_IN

    # 更久的安静 + 朋友以上 → 轻轻搭话
    if (
        silence_seconds >= 3600
        and relationship_stage in ("friend", "bonded")
        and gate.can(KIND_REACH_OUT, relationship_stage, now)
    ):
        return KIND_REACH_OUT

    return None
