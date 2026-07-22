"""主动行为门控测试。"""

from datetime import datetime, timedelta

from qi.core.proactive import (
    KIND_CHECK_IN,
    KIND_EXPRESS_FEELING,
    KIND_REACH_OUT,
    PROACTIVE_DAILY_LIMIT,
    ProactiveGate,
    pick_proactive_kind,
)


def test_stranger_cannot_proactive():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    assert gate.can(KIND_EXPRESS_FEELING, "stranger", now) is False
    assert (
        pick_proactive_kind(
            want_express=True,
            relationship_stage="stranger",
            emotion_security=0.3,
            emotion_attachment=0.7,
            silence_seconds=7200,
            mode="ambient",
            user_online=True,
            gate=gate,
            now=now,
        )
        is None
    )


def test_daily_limit_and_cooldown():
    gate = ProactiveGate({"proactive_cooldown": {"express_feeling": 7200}})
    now = datetime(2026, 7, 21, 12, 0)
    for _ in range(PROACTIVE_DAILY_LIMIT):
        assert gate.can(KIND_EXPRESS_FEELING, "friend", now)
        gate.record(KIND_EXPRESS_FEELING, now)
        now += timedelta(hours=3)
    assert gate.can(KIND_EXPRESS_FEELING, "friend", now) is False


def test_cooldown_blocks_same_kind():
    gate = ProactiveGate({"proactive_cooldown": {"check_in": 14400}})
    now = datetime(2026, 7, 21, 10, 0)
    gate.record(KIND_CHECK_IN, now)
    assert gate.can(KIND_CHECK_IN, "friend", now + timedelta(hours=1)) is False
    assert gate.can(KIND_CHECK_IN, "friend", now + timedelta(hours=5)) is True


def test_pick_express_feeling_when_want():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    kind = pick_proactive_kind(
        want_express=True,
        relationship_stage="acquaintance",
        emotion_security=0.5,
        emotion_attachment=0.4,
        silence_seconds=100,
        mode="awake",
        user_online=True,
        gate=gate,
        now=now,
    )
    assert kind == KIND_EXPRESS_FEELING


def test_pick_check_in_on_long_silence():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    kind = pick_proactive_kind(
        want_express=False,
        relationship_stage="friend",
        emotion_security=0.3,
        emotion_attachment=0.6,
        silence_seconds=2000,
        mode="solitary",
        user_online=True,
        gate=gate,
        now=now,
    )
    assert kind == KIND_CHECK_IN


def test_pick_reach_out_friend_long_silence():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    kind = pick_proactive_kind(
        want_express=False,
        relationship_stage="friend",
        emotion_security=0.7,
        emotion_attachment=0.3,
        silence_seconds=4000,
        mode="ambient",
        user_online=True,
        gate=gate,
        now=now,
    )
    assert kind == KIND_REACH_OUT


def test_no_proactive_when_offline_or_dreaming():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    assert (
        pick_proactive_kind(
            want_express=True,
            relationship_stage="friend",
            emotion_security=0.3,
            emotion_attachment=0.7,
            silence_seconds=5000,
            mode="awake",
            user_online=False,
            gate=gate,
            now=now,
        )
        is None
    )
    assert (
        pick_proactive_kind(
            want_express=True,
            relationship_stage="friend",
            emotion_security=0.3,
            emotion_attachment=0.7,
            silence_seconds=5000,
            mode="dreaming",
            user_online=True,
            gate=gate,
            now=now,
        )
        is None
    )


def test_snapshot_restore():
    gate = ProactiveGate({})
    now = datetime(2026, 7, 21, 12, 0)
    gate.record(KIND_REACH_OUT, now)
    snap = gate.snapshot()
    other = ProactiveGate({})
    other.restore(snap)
    assert other.count_today == 1
    assert KIND_REACH_OUT in other.last_at
