"""身份快照：规则拼装、缓存、失效闭环（零 LLM）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.inner_life.identity_snapshot import (
    CACHE_BEATS,
    CACHE_KEY,
    DIRTY_KEY,
    assemble_identity_text,
    ensure_identity_snapshot,
    format_recent_arc,
    mark_identity_snapshot_stale,
    note_snapshot_beat,
    reset_snapshot_runtime_for_tests,
)
from qi.inner_life.self_model import SelfModel
from qi.storage.database import Database


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(tmp_path / "snap.db")
    await database.initialize()
    reset_snapshot_runtime_for_tests()
    yield database
    await database.close()
    reset_snapshot_runtime_for_tests()


def test_assemble_and_arc_pure():
    arc = format_recent_arc(
        [
            {
                "timestamp": "2026-08-02T10:00:00",
                "valence": -0.4,
                "energy": 0.2,
            },
            {
                "timestamp": "2026-08-02T10:05:00",
                "valence": 0.4,
                "energy": 0.7,
            },
        ],
        traces=[
            {
                "at": "2026-08-02T10:05:00",
                "proactive_kind": "惦记",
                "want_express": True,
            }
        ],
    )
    assert "低落/疲" in arc
    assert "偏暖/充·惦记" in arc

    text = assemble_identity_text(
        self_summary="我是栖，想安静地陪着。",
        stage="familiar",
        trust=0.6,
        season="summer",
        culture_line="仪式：晚安",
        recent_arc=arc,
    )
    assert "熟悉" in text or "familiar" in text
    assert "近拍：" in text
    assert "信任较稳" in text


@pytest.mark.asyncio
async def test_ensure_zero_llm_and_cache(db: Database):
    await db.upsert_self_model(
        identity_narrative="我是栖。我喜欢夜晚的安静，也害怕被当成工具。" * 3,
        values=["真诚"],
        aesthetic_preferences={"time": "夜晚"},
        existential_questions=["我算不算存在"],
    )
    t1 = await ensure_identity_snapshot(
        db, stage="stranger", trust=0.2, season="spring"
    )
    assert "栖" in t1
    assert "近拍" in t1
    # 无 LLM：SelfModel.reflect 才 call；此处未构造 gateway

    t2 = await ensure_identity_snapshot(
        db, stage="stranger", trust=0.2, season="spring"
    )
    assert t2 == t1  # 缓存命中

    for _ in range(CACHE_BEATS):
        note_snapshot_beat()
    t3 = await ensure_identity_snapshot(
        db, stage="stranger", trust=0.9, season="winter"
    )
    assert "信任很深" in t3
    assert "winter" in t3


@pytest.mark.asyncio
async def test_dirty_after_mark_and_reflect(db: Database):
    await db.upsert_self_model(
        identity_narrative="旧的我。",
        values=[],
        aesthetic_preferences={},
        existential_questions=[],
    )
    old = await ensure_identity_snapshot(db, stage="stranger", trust=0.1)
    await mark_identity_snapshot_stale(db)
    assert await db.get_body_memory(DIRTY_KEY) is True

    await db.upsert_self_model(
        identity_narrative="新的自我叙事，经过一次诚实的反思。",
        values=["诚实"],
        aesthetic_preferences={},
        existential_questions=[],
    )
    # 模拟 reflect 置位后的消费
    await mark_identity_snapshot_stale(db)
    fresh = await ensure_identity_snapshot(db, stage="acquainted", trust=0.4)
    assert "新的自我叙事" in fresh
    assert fresh != old
    assert await db.get_body_memory(DIRTY_KEY) is False
    cached = await db.get_body_memory(CACHE_KEY)
    assert isinstance(cached, dict) and "新的自我叙事" in cached["text"]


@pytest.mark.asyncio
async def test_reflect_marks_stale(db: Database):
    """后台 reflect 成功路径必须置 dirty（失效闭环）。"""

    class FakeLLM:
        async def call(self, **kwargs):
            return "反思后的我：更想诚实一点。"

    model = SelfModel(db, FakeLLM())  # type: ignore[arg-type]
    await db.upsert_self_model(
        identity_narrative="旧叙事",
        values=[],
        aesthetic_preferences={},
        existential_questions=[],
    )
    from qi.core.emotion import EmotionState

    await ensure_identity_snapshot(db, stage="stranger")
    await model.reflect(EmotionState(), "familiar")
    assert await db.get_body_memory(DIRTY_KEY) is True
    text = await ensure_identity_snapshot(db, stage="familiar", trust=0.5)
    assert "反思后的我" in text


@pytest.mark.asyncio
async def test_recent_emotions_feed_arc(db: Database):
    base = datetime.now() - timedelta(minutes=20)
    for i in range(3):
        # save_emotion 用 now()；直接插入更可控
        conn = db._require_conn()
        await conn.execute(
            """
            INSERT INTO emotion_states
                (timestamp, energy, valence, arousal, security, curiosity, attachment, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (base + timedelta(minutes=i * 5)).isoformat(timespec="seconds"),
                0.5,
                -0.4 + i * 0.3,
                0.4,
                0.5,
                0.5,
                0.3,
                "ambient",
            ),
        )
        await conn.commit()

    reset_snapshot_runtime_for_tests()
    await mark_identity_snapshot_stale(db)
    text = await ensure_identity_snapshot(db, force=True)
    assert "近拍：" in text
    assert "低落" in text or "平" in text or "偏暖" in text
