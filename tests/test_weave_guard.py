"""编织方向消毒：人称/施教织反对照 role_map。"""

from __future__ import annotations

from qi.memory.episodic import build_role_map
from qi.memory.weave_guard import sanitize_woven_narrative


def test_sanitize_gender_invert_against_user_said():
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "我一直把你当女生...",
            "timestamp": "t",
        },
        {
            "id": 2,
            "type": "user_message",
            "content": "你在吗",
            "timestamp": "t2",
        },
    ]
    rm = build_role_map(events)
    dirty = (
        "那天晚上我有点走神。你问我是不是不在，又说我总把你当女生。"
        "其实我听见了。"
    )
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "gender_direction" in tags
    assert "又说你一直把我当女生" in clean
    assert "又说我总把你当女生" not in clean


def test_sanitize_teach_invert_when_user_ack_qi_taught():
    events = [
        {
            "id": 1,
            "type": "user_message",
            "content": "你教了我一个方法",
            "timestamp": "t",
        },
    ]
    rm = build_role_map(events)
    dirty = "我记得你教给我那个方法的时候，我们都在深夜。"
    clean, tags = sanitize_woven_narrative(dirty, rm)
    assert "teach_direction" in tags
    assert "我教给你那个方法" in clean
    assert "你教给我" not in clean


def test_sanitize_noop_without_evidence():
    rm = build_role_map(
        [{"id": 1, "type": "user_message", "content": "今天天气不错", "timestamp": "t"}]
    )
    text = "那天我们随便聊了聊天气。"
    clean, tags = sanitize_woven_narrative(text, rm)
    assert clean == text
    assert tags == []
