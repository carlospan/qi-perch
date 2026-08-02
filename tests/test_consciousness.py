"""阶段二·补丁 D：意识流触发门槛（silence / 无积压底线）。"""

from __future__ import annotations

from datetime import timedelta

from qi.inner_life.consciousness import (
    SILENCE_TRIGGER_HOURS,
    should_trigger_consciousness,
)


def test_silence_trigger_hours_is_three():
    assert SILENCE_TRIGGER_HOURS == 3


def test_no_open_loop_no_signal_stays_false():
    ok, reason = should_trigger_consciousness(
        "awake",
        0.0,
        0.0,
        timedelta(0),
        open_loop_count=0,
    )
    assert ok is False
    assert reason == ""


def test_solitary_silence_over_three_hours():
    ok, reason = should_trigger_consciousness(
        "solitary",
        0.0,
        0.0,
        timedelta(hours=3, minutes=1),
        open_loop_count=0,
    )
    assert ok is True
    assert reason == "silence"


def test_solitary_silence_under_three_hours_no_trigger():
    ok, reason = should_trigger_consciousness(
        "solitary",
        0.0,
        0.0,
        timedelta(hours=2, minutes=59),
        open_loop_count=0,
    )
    assert ok is False
    assert reason == ""


def test_awake_long_silence_still_no_trigger():
    ok, _ = should_trigger_consciousness(
        "awake",
        0.0,
        0.0,
        timedelta(hours=5),
        open_loop_count=0,
    )
    assert ok is False
