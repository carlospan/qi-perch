"""阶段二·包 8：进程传感。"""

from __future__ import annotations

from datetime import datetime

from qi.sensing import SensingSnapshot, collect


def test_sensing_collect_fields():
    snap = collect(heartbeat_count=7)
    assert isinstance(snap, SensingSnapshot)
    assert snap.heartbeat_count == 7
    assert snap.uptime_seconds >= 0
    assert snap.at
    datetime.fromisoformat(snap.at)
    assert snap.wall_clock
    assert snap.period in ("深夜", "上午", "下午", "傍晚")
    if snap.rss_bytes is not None:
        assert isinstance(snap.rss_bytes, int)
        assert snap.rss_bytes >= 0


def test_sensing_to_dict():
    d = collect(heartbeat_count=1).to_dict()
    assert "uptime_seconds" in d
    assert d["heartbeat_count"] == 1
