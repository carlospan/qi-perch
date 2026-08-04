"""自我模型字段抽取 + 包19 pending_major 持久化。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from qi.core.emotion import EmotionState
from qi.inner_life.self_model import (
    PENDING_MAJOR_KEY,
    SelfModel,
    _extract_aesthetic,
    _extract_existential,
    _extract_values,
)


def test_extract_self_model_fields():
    text = "我想做一个真诚安静的陪伴。深夜我常问自己：我是谁，算不算存在。"
    assert "真诚" in _extract_values(text)
    assert _extract_aesthetic(text).get("time") == "夜晚"
    assert any("我是谁" in q for q in _extract_existential(text))


@pytest.mark.asyncio
async def test_pending_major_survives_restart(db):
    """包19：note_emotion_surge 置位 → 新实例 should_reflect True → reflect 后清除。"""
    llm = MagicMock()
    llm.call = AsyncMock(return_value="我是栖。我记得你。")

    sm1 = SelfModel(db, llm, {"inner_life": {"self_reflection_interval": 604800}})
    # 先写入「刚更新过」的叙事，避免无 last_updated 时 always-true
    await db.upsert_self_model(
        identity_narrative="旧的我。",
        values=[],
        aesthetic_preferences={},
        existential_questions=[],
    )
    # 把 last_updated 拨到近期（upsert 已写 now；再确认间隔未到）
    assert not await sm1.should_reflect()

    await sm1.note_emotion_surge(0.65)
    assert sm1._pending_major is True
    stored = await db.get_body_memory(PENDING_MAJOR_KEY)
    assert stored in ("1", 1)

    # 模拟重启：新实例内存标志为 False，应从 body_memory 惰性加载
    sm2 = SelfModel(db, llm, {"inner_life": {"self_reflection_interval": 604800}})
    assert sm2._pending_major is False
    assert await sm2.should_reflect() is True

    out = await sm2.reflect(EmotionState(), "bonded")
    assert out and "栖" in out
    assert sm2._pending_major is False
    cleared = await db.get_body_memory(PENDING_MAJOR_KEY)
    assert cleared in (None, "", 0, False)

    # 清标志后、间隔未到 → 不再因 pending 触发
    sm3 = SelfModel(db, llm, {"inner_life": {"self_reflection_interval": 604800}})
    assert await sm3.should_reflect() is False


@pytest.mark.asyncio
async def test_mark_major_event_persists(db):
    llm = MagicMock()
    llm.call = AsyncMock(return_value="ok")
    sm = SelfModel(db, llm)
    await db.upsert_self_model(
        identity_narrative="旧。",
        values=[],
        aesthetic_preferences={},
        existential_questions=[],
    )
    await sm.mark_major_event()
    assert await db.get_body_memory(PENDING_MAJOR_KEY) in ("1", 1)
    sm2 = SelfModel(db, llm)
    assert await sm2.should_reflect() is True
