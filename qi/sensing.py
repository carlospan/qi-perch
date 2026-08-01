"""进程传感——只读 OS 标准库（阶段二·包 8）。

采集在线时长、内存、心跳、墙钟；供 GWS report / 自操作日记。
无第三方依赖；Windows 上 rss 可能不可用（则为 None）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger("qi.sensing")

# 进程锚定（monotonic，不受墙钟回拨影响）
_PROCESS_START_MONO = time.monotonic()
_PROCESS_START_WALL = datetime.now()


@dataclass
class SensingSnapshot:
    at: str
    uptime_seconds: float
    rss_bytes: int | None
    heartbeat_count: int
    wall_clock: str
    period: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _period_for(hour: int) -> str:
    if hour >= 22 or hour < 6:
        return "深夜"
    if hour < 12:
        return "上午"
    if hour < 18:
        return "下午"
    return "傍晚"


def _rss_bytes() -> int | None:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux: ru_maxrss 为 KB；macOS 常为字节。用启发式：过大则当字节。
        rss = int(usage.ru_maxrss)
        if rss <= 0:
            return None
        if rss < 10_000_000:  # 约 <10MB 按 KB 计（Linux 常见）
            return rss * 1024
        return rss
    except Exception:
        logger.debug("resource rss 不可用", exc_info=True)
        return None


def collect(*, heartbeat_count: int = 0, now: datetime | None = None) -> SensingSnapshot:
    """采集一帧传感快照（纯本地，零 LLM）。"""
    now = now or datetime.now()
    uptime = max(0.0, time.monotonic() - _PROCESS_START_MONO)
    return SensingSnapshot(
        at=now.isoformat(timespec="seconds"),
        uptime_seconds=round(uptime, 3),
        rss_bytes=_rss_bytes(),
        heartbeat_count=int(heartbeat_count),
        wall_clock=now.strftime("%H:%M"),
        period=_period_for(now.hour),
    )


def process_start_wall() -> datetime:
    return _PROCESS_START_WALL
