"""身体记忆：习惯与节奏，不是文字，是模式。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from storage.database import Database

_GREETING_HINTS = ("早", "你好", "嗨", "嘿", "晚安", "午安", "在吗", "hello", "hi")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


class BodyMemory:
    """身体记忆：检测并存储用户的交互模式。"""

    def __init__(self, db: Database):
        self.db = db
        self._last_interaction: datetime | None = None
        self._last_day: str | None = None
        self._day_first_seen: bool = False

    async def get_pattern(self, key: str) -> Any | None:
        return await self.db.get_body_memory(key)

    async def update_pattern(self, key: str, value: dict | str) -> None:
        await self.db.set_body_memory(key, value)

    async def record_interaction(self, timestamp: datetime, message: str) -> None:
        """每次用户说话后更新模式。"""
        await self._update_active_hours(timestamp)
        await self._update_greeting(timestamp, message)
        await self._update_typing_rhythm(timestamp, message)
        await self._update_silence(timestamp)
        self._last_interaction = timestamp

    async def _update_active_hours(self, timestamp: datetime) -> None:
        data = await self.get_pattern("usual_active_hours") or {
            "hours": [],
            "start": 9,
            "end": 23,
            "samples": 0,
        }
        hours: list[int] = list(data.get("hours") or [])
        hours.append(timestamp.hour)
        # 只保留最近 200 个样本
        hours = hours[-200:]
        sorted_h = sorted(hours)
        n = len(sorted_h)
        start = sorted_h[max(0, int(n * 0.1))]
        end = sorted_h[min(n - 1, int(n * 0.9))]
        await self.update_pattern(
            "usual_active_hours",
            {"hours": hours, "start": start, "end": end, "samples": n},
        )

    async def _update_greeting(self, timestamp: datetime, message: str) -> None:
        day = timestamp.strftime("%Y-%m-%d")
        is_first = self._last_day != day
        self._last_day = day
        if not is_first:
            return
        text = message.strip()
        if not text:
            return
        # 只把像打招呼的短句记作问候
        if len(text) > 20 and not any(h in text for h in _GREETING_HINTS):
            return
        data = await self.get_pattern("greeting_pattern") or {"recent": [], "pattern": ""}
        recent: list[str] = list(data.get("recent") or [])
        recent.append(text[:30])
        recent = recent[-5:]
        # 众数
        pattern = max(set(recent), key=recent.count) if recent else text[:30]
        await self.update_pattern(
            "greeting_pattern",
            {"recent": recent, "pattern": pattern, "samples": len(recent)},
        )

    async def _update_typing_rhythm(self, timestamp: datetime, message: str) -> None:
        data = await self.get_pattern("typing_rhythm") or {
            "chars": [],
            "intervals": [],
            "avg_chars": 15,
            "avg_interval_sec": 60,
            "samples": 0,
        }
        chars: list[int] = list(data.get("chars") or [])
        intervals: list[float] = list(data.get("intervals") or [])
        chars.append(len(message))
        if self._last_interaction is not None:
            gap = (timestamp - self._last_interaction).total_seconds()
            if 0 < gap < 3600:
                intervals.append(gap)
        chars = chars[-100:]
        intervals = intervals[-100:]
        avg_chars = sum(chars) / len(chars) if chars else 15
        avg_interval = sum(intervals) / len(intervals) if intervals else 60
        await self.update_pattern(
            "typing_rhythm",
            {
                "chars": chars,
                "intervals": intervals,
                "avg_chars": round(avg_chars, 1),
                "avg_interval_sec": round(avg_interval, 1),
                "samples": len(chars),
            },
        )

    async def _update_silence(self, timestamp: datetime) -> None:
        if self._last_interaction is None:
            return
        gap_hours = (timestamp - self._last_interaction).total_seconds() / 3600
        if gap_hours <= 0:
            return
        data = await self.get_pattern("silence_tolerance") or {
            "gaps": [],
            "hours": 4.0,
            "samples": 0,
        }
        gaps: list[float] = list(data.get("gaps") or [])
        gaps.append(gap_hours)
        gaps = gaps[-100:]
        sorted_g = sorted(gaps)
        median = sorted_g[len(sorted_g) // 2]
        await self.update_pattern(
            "silence_tolerance",
            {"gaps": gaps, "hours": round(median, 2), "samples": len(gaps)},
        )

    async def detect_anomaly(self, now: datetime) -> list[str]:
        """偏离已知节奏时，轻轻标出来。样本不足不报。"""
        anomalies: list[str] = []

        hours = await self.get_pattern("usual_active_hours")
        if hours and int(hours.get("samples") or 0) >= 5:
            start = int(hours.get("start", 9))
            end = int(hours.get("end", 23))
            h = now.hour
            if h < start - 2:
                anomalies.append(f"他通常{start}点左右才在，今天{h}点就来了")
            elif h > end + 2:
                anomalies.append(f"他通常{end}点前就安静了，今天{h}点还在")

        silence = await self.get_pattern("silence_tolerance")
        if silence and int(silence.get("samples") or 0) >= 5 and self._last_interaction:
            tol = float(silence.get("hours") or 4)
            gap = (now - self._last_interaction).total_seconds() / 3600
            if gap > tol * 1.5:
                anomalies.append("他比平时安静更久了")

        greeting = await self.get_pattern("greeting_pattern")
        # 问候异常在 record 时不好比「今天第一条」；留给调用方传入当日首条时判断
        # 这里若 pattern 存在且 samples>=5，由外部可再比；L2 简化：不在 detect 里强制

        return anomalies

    async def detect_greeting_anomaly(self, message: str) -> str | None:
        data = await self.get_pattern("greeting_pattern")
        if not data or int(data.get("samples") or 0) < 5:
            return None
        pattern = str(data.get("pattern") or "")
        if not pattern:
            return None
        text = message.strip()[:30]
        if any(h in text for h in _GREETING_HINTS) or len(text) <= 12:
            if _levenshtein(text, pattern) > 2:
                return "他今天换了个方式打招呼"
        return None
