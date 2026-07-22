"""L4 内在生命测试。"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.inner_life.consciousness import should_trigger_consciousness, should_trigger_meta
from qi.inner_life.creativity import can_share_creation
from qi.inner_life.dream import DreamEngine, parse_emotion_tag, update_dream_retention
from qi.storage.database import Database


def test_consciousness_trigger_solitary_random(monkeypatch):
    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.01)
    ok, reason = should_trigger_consciousness(
        "solitary", 0.0, 0.0, timedelta(minutes=10)
    )
    assert ok and reason == "random"


def test_consciousness_trigger_emotion_surge():
    ok, reason = should_trigger_consciousness(
        "ambient", 0.4, 0.0, timedelta(minutes=1)
    )
    assert ok and reason == "emotion_surge"


def test_consciousness_silence_not_in_awake():
    ok, _ = should_trigger_consciousness(
        "awake", 0.0, 0.0, timedelta(hours=5)
    )
    assert ok is False


def test_meta_not_in_awake():
    assert should_trigger_meta("awake", probability=1.0) is False


def test_dream_retention_decays():
    import math

    r0 = update_dream_retention(0, 1.0)
    r6 = update_dream_retention(6, 1.0)
    assert r0 == pytest.approx(1.0)
    assert r6 == pytest.approx(math.exp(-1.0), rel=1e-6)
    assert r6 < r0


def test_parse_emotion_tag():
    body, tag = parse_emotion_tag("一片海。\n情绪标签：温暖")
    assert "海" in body
    assert tag == "温暖"


def test_can_share_creation_stage_and_cooldown():
    now = datetime(2026, 7, 21, 12, 0, 0)
    assert can_share_creation("stranger", None, now) is False
    assert can_share_creation("friend", None, now) is True
    assert (
        can_share_creation("friend", now - timedelta(hours=2), now) is False
    )
    assert (
        can_share_creation("friend", now - timedelta(hours=25), now) is True
    )


def test_dream_afterglow_positive():
    engine = DreamEngine.__new__(DreamEngine)
    e = EmotionState(valence=0.0)
    dream = {"retention": 0.8, "emotion_tag": "温暖"}
    after = DreamEngine.apply_afterglow(engine, e, dream)
    assert after.valence > e.valence


@pytest.mark.asyncio
async def test_l4_tables_and_crud():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        cid = await db.save_consciousness("今天有点安静", "stream", "random", "{}")
        assert cid > 0
        rows = await db.load_recent_consciousness(limit=1)
        assert rows and rows[0]["content"] == "今天有点安静"

        did = await db.save_dream("梦见一片森林", "平静", 0.6, 1.0)
        dream = await db.load_latest_dream()
        assert dream and dream["id"] == did

        crid = await db.save_creation("一行短诗", "poem", "{}")
        unshared = await db.load_unshared_creation()
        assert unshared and unshared["id"] == crid
        await db.mark_creation_shared(crid)
        assert await db.load_unshared_creation() is None

        await db.upsert_self_model("我是栖，刚醒来。")
        sm = await db.load_self_model()
        assert sm and "栖" in sm["identity_narrative"]

        await db.close()
