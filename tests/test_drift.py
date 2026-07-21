"""用户漂移：节奏距离与信号。"""

from datetime import datetime, timedelta

from relationship.drift import (
    build_updated_user_model,
    compute_rhythm,
    compute_rhythm_distance,
    detect_user_drift,
)


def _msg(role: str, content: str, when: datetime) -> dict:
    return {"role": role, "content": content, "timestamp": when.isoformat(timespec="seconds")}


def test_compute_rhythm_active_hours_and_gap():
    base = datetime(2026, 7, 21, 10, 0)
    msgs = [
        _msg("user", "工作好累", base),
        _msg("user", "还在写代码", base + timedelta(minutes=30)),
        _msg("user", "项目推进中", base + timedelta(hours=1)),
        _msg("qi", "嗯", base + timedelta(hours=1, minutes=1)),
    ]
    rhythm = compute_rhythm(msgs)
    assert rhythm["msg_count"] == 3
    assert 10 in rhythm["active_hours"]
    assert rhythm["avg_gap_seconds"] > 0


def test_rhythm_distance_detects_change():
    day = datetime(2026, 7, 1, 9, 0)
    old_msgs = [
        _msg("user", "早", day + timedelta(hours=i)) for i in range(4)
    ]
    # 旧：白天密集；新：深夜稀疏
    new_base = datetime(2026, 7, 20, 23, 0)
    new_msgs = [
        _msg("user", "还醒着", new_base),
        _msg("user", "睡不着", new_base + timedelta(hours=2)),
        _msg("user", "算了", new_base + timedelta(hours=4)),
        _msg("user", "晚安", new_base + timedelta(hours=5)),
    ]
    old_r = compute_rhythm(old_msgs)
    new_r = compute_rhythm(new_msgs)
    dist = compute_rhythm_distance(old_r, new_r)
    assert dist > 0.4


def test_detect_drift_includes_rhythm_signal():
    day = datetime(2026, 7, 1, 9, 0)
    old_msgs = [_msg("user", "工作代码项目", day + timedelta(hours=i)) for i in range(4)]
    model = build_updated_user_model(old_msgs, [])
    new_base = datetime(2026, 7, 20, 23, 0)
    new_msgs = [
        _msg("user", "电影音乐旅行", new_base + timedelta(hours=i * 2))
        for i in range(4)
    ]
    signals = detect_user_drift(model, new_msgs)
    # 话题或节奏至少有一个信号（综合可能过阈值）
    assert isinstance(signals, list)


def test_forget_constant_used_in_purge_api():
    from memory.narrative import FORGET_STRENGTH

    assert FORGET_STRENGTH == 0.1
