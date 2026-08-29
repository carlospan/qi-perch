"""P0 情绪事件推送：指纹变化与 debounce 调度。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.embodiment.emotion_push import (
    EMOTION_PUSH_DEBOUNCE_S,
    build_emotion_snapshot,
    emotion_snapshot_changed,
)
from qi.embodiment.server import EmbodimentServer


def test_emotion_snapshot_changed_rounding():
    a = {
        "energy": 0.501,
        "valence": 0.0,
        "arousal": 0.3,
        "security": 0.5,
        "curiosity": 0.4,
        "attachment": 0.5,
        "mode": "ambient",
        "stasis": False,
        "description": "平静",
        "stage": "friend",
    }
    b = dict(a)
    b["energy"] = 0.504  # 同两位小数
    assert not emotion_snapshot_changed(a, b)
    b["energy"] = 0.52
    assert emotion_snapshot_changed(a, b)
    b = dict(a)
    b["description"] = "有点软"
    assert emotion_snapshot_changed(a, b)


def test_build_emotion_snapshot_fields():
    brain = MagicMock()
    brain.emotion.energy = 0.5
    brain.emotion.valence = 0.1
    brain.emotion.arousal = 0.2
    brain.emotion.security = 0.6
    brain.emotion.curiosity = 0.4
    brain.emotion.attachment = 0.5
    brain.emotion.description.return_value = "安静"
    brain.public_mode.return_value = "ambient"
    brain.in_stasis = False
    brain.relationship_stage = "friend"
    snap = build_emotion_snapshot(brain)
    assert snap["description"] == "安静"
    assert snap["mode"] == "ambient"
    assert snap["stage"] == "friend"


@pytest.mark.asyncio
async def test_schedule_emotion_push_debounces_and_skips_same():
    assert EMOTION_PUSH_DEBOUNCE_S == 1.0
    brain = MagicMock()
    brain.emotion.energy = 0.5
    brain.emotion.valence = 0.0
    brain.emotion.arousal = 0.3
    brain.emotion.security = 0.5
    brain.emotion.curiosity = 0.4
    brain.emotion.attachment = 0.5
    brain.emotion.description.return_value = "平静"
    brain.public_mode.return_value = "ambient"
    brain.in_stasis = False
    brain.relationship_stage = "friend"

    server = EmbodimentServer(brain)
    server.running = True
    server.send_emotion_update = AsyncMock()
    server.schedule_emotion_push()
    server.schedule_emotion_push()  # 合并
    await asyncio.sleep(1.15)
    assert server.send_emotion_update.await_count == 1

    server.send_emotion_update.reset_mock()
    server.schedule_emotion_push()
    await asyncio.sleep(1.15)
    # 无变化不推
    server.send_emotion_update.assert_not_awaited()

    brain.emotion.energy = 0.8
    server.schedule_emotion_push()
    await asyncio.sleep(1.15)
    assert server.send_emotion_update.await_count == 1
