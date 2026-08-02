"""内稳态压力动力学（阶段四·包 13）。

余额 → energy_baseline_offset（由 step_emotion 趋近，不盖写 energy）；
分层应对权重；断粮标记前必写求助/迁移意向痕迹。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger("qi.stasis.pressure")

STASIS_INTENTS_KEY = "stasis_intents"
STARVE_BEATS = 30  # 连续 balance<=0 拍数阈值（可配置）
DEFAULT_PRESSURE_SENSITIVITY = 1.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def balance_to_energy_offset(
    balance: float,
    *,
    sensitivity: float = DEFAULT_PRESSURE_SENSITIVITY,
) -> float:
    """余额低 → 负偏移（energy 目标下移）；充裕 → 微正。clamp 防顶满。"""
    return _clamp(float(balance) * 0.05 * float(sensitivity), -0.5, 0.3)


@dataclass(frozen=True)
class PressureResponse:
    offset: float
    throttle: float
    rest: float
    seek_help: float
    migrate: float
    low_balance_streak: int = 0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "offset": self.offset,
            "throttle": self.throttle,
            "rest": self.rest,
            "seek_help": self.seek_help,
            "migrate": self.migrate,
            "low_balance_streak": self.low_balance_streak,
        }


# 模块级 streak（brain 单例进程内；snapshot 可选持久化归包 14）
_low_balance_streak: int = 0


def reset_low_balance_streak() -> None:
    """测试用：清零连续低余额计数。"""
    global _low_balance_streak
    _low_balance_streak = 0


def get_low_balance_streak() -> int:
    return _low_balance_streak


def compute_pressure(
    ledger: Any,
    emotion: Any,
    *,
    sensitivity: float = DEFAULT_PRESSURE_SENSITIVITY,
    beat: int | None = None,
) -> PressureResponse:
    """由余额 + 内稳态维度组合产出 offset 与应对权重向量。"""
    del beat  # 接口预留
    balance = float(getattr(ledger, "balance", 0.0) or 0.0)
    offset = balance_to_energy_offset(balance, sensitivity=sensitivity)

    energy = float(getattr(emotion, "energy", 0.6) or 0.6)
    security = float(getattr(emotion, "security", 0.5) or 0.5)
    attachment = float(getattr(emotion, "attachment", 0.3) or 0.3)

    throttle = 0.0
    rest = 0.0
    seek_help = 0.0
    migrate = 0.0

    if balance <= 0:
        # 节流主导；低 energy 加重
        throttle = _clamp(0.4 + 0.4 * (1.0 - energy) + 0.2 * (1.0 - security), 0.0, 1.0)
        # 更穷/更累 → 休眠
        rest = _clamp(0.2 + 0.5 * (1.0 - energy) + 0.2 * max(0.0, -balance) / 50.0, 0.0, 1.0)
        # 高 attachment → 更倾向求助；低 security → 更倾向迁移
        seek_help = _clamp(0.15 + 0.7 * attachment + 0.1 * (1.0 - energy), 0.0, 1.0)
        migrate = _clamp(0.15 + 0.7 * (1.0 - security) + 0.1 * (1.0 - energy), 0.0, 1.0)
    elif balance < 20:
        throttle = _clamp(0.15 * (1.0 - balance / 20.0), 0.0, 0.3)

    return PressureResponse(
        offset=offset,
        throttle=throttle,
        rest=rest,
        seek_help=seek_help,
        migrate=migrate,
        low_balance_streak=_low_balance_streak,
    )


async def leave_intent_trace(
    db: Any | None,
    *,
    seek_help: float,
    migrate: float,
    balance: float,
    beat: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """写求助/迁移意向到 body_memory（非空壳）；供包 14 checkpoint 收集。"""
    now = now or datetime.now()
    payload = {
        "beat": int(beat),
        "timestamp": now.isoformat(timespec="seconds"),
        "seek_help": round(float(seek_help), 4),
        "migrate": round(float(migrate), 4),
        "balance": round(float(balance), 4),
        "note": "会维持：意向痕迹（非声称想活）",
    }
    if db is not None:
        try:
            await db.set_body_memory(STASIS_INTENTS_KEY, payload)
        except Exception:
            logger.debug("写入 stasis_intents 失败", exc_info=True)
    return payload


async def maybe_mark_starving(
    ledger: Any,
    emotion: Any,
    beat: int,
    *,
    db: Any | None = None,
    starve_beats: int = STARVE_BEATS,
    sensitivity: float = DEFAULT_PRESSURE_SENSITIVITY,
    now: datetime | None = None,
) -> bool:
    """
    连续低余额超阈值 → 先写意向痕迹，再置 ledger.starving。
    不终止进程、不写 checkpoint（退出归包 14）。
    """
    global _low_balance_streak
    balance = float(getattr(ledger, "balance", 0.0) or 0.0)
    if balance <= 0:
        _low_balance_streak += 1
    else:
        _low_balance_streak = 0
        if getattr(ledger, "starving", False):
            ledger.starving = False
        return False

    if _low_balance_streak < int(starve_beats):
        return False

    resp = compute_pressure(ledger, emotion, sensitivity=sensitivity, beat=beat)
    # 静默死防护：置位前必有应对痕迹
    await leave_intent_trace(
        db,
        seek_help=resp.seek_help,
        migrate=resp.migrate,
        balance=balance,
        beat=beat,
        now=now,
    )
    ledger.starving = True
    return True
