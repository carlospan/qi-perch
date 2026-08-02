"""阶段三·包 9：用户在线节律世界模型。"""

from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.brain import Brain
from qi.llm.gateway import LLMCallOutcome
from qi.storage.database import Database
from qi.world.model import WorldModel
from qi.world.online_rhythm import OnlineRhythm


class _StubLLM:
    def __init__(self, text: str = "嗯。"):
        self.text = text
        self.last_outcome = LLMCallOutcome(text=text, failure=None)

    async def call(self, purpose, messages, temperature=None):
        return self.text


class _FailLLM:
    def __init__(self):
        self.last_outcome = LLMCallOutcome(text="", failure="unreachable")

    async def call(self, purpose, messages, temperature=None):
        return ""


def _noon_monday() -> datetime:
    # weekday=0, hour=12
    return datetime(2026, 8, 3, 12, 0, 0)


@pytest.mark.asyncio
async def test_bucket_counts_success_and_fail():
    rhythm = OnlineRhythm()
    now = _noon_monday()
    await rhythm.record(None, online=True, now=now)
    await rhythm.record(None, online=True, now=now)
    await rhythm.record(None, online=False, now=now)
    cell = rhythm._buckets["0_12"]
    assert cell["s"] == 2
    assert cell["f"] == 1


@pytest.mark.asyncio
async def test_predict_converges_to_empirical_frequency():
    rhythm = OnlineRhythm()
    now = _noon_monday()
    assert rhythm.predict(now) == 0.5
    for _ in range(20):
        await rhythm.record(None, online=True, now=now)
    # (1+20)/(1+1+20) = 21/22
    assert rhythm.predict(now) == pytest.approx(21 / 22)
    assert rhythm.predict(now) > 0.9


@pytest.mark.asyncio
async def test_absence_lowers_predict():
    rhythm = OnlineRhythm()
    now = _noon_monday()
    for _ in range(10):
        await rhythm.record(None, online=False, now=now)
    assert rhythm.predict(now) < 0.2


@pytest.mark.asyncio
async def test_surprise_low_predict_appear_gt_high_predict_appear():
    low = OnlineRhythm()
    high = OnlineRhythm()
    now = _noon_monday()
    for _ in range(15):
        await low.record(None, online=False, now=now)
        await high.record(None, online=True, now=now)
    # surprise 用更新前预测；再观测 online=True
    s_low = low.surprise(True, now)
    s_high = high.surprise(True, now)
    assert s_low > s_high
    assert s_low == pytest.approx(-math.log(max(1e-6, low.predict(now))))


@pytest.mark.asyncio
async def test_snapshot_structure_after_record():
    rhythm = OnlineRhythm()
    now = _noon_monday()
    await rhythm.record(None, online=True, now=now)
    snap = rhythm.snapshot(now)
    assert set(snap) >= {"predicted_online", "surprise", "bucket"}
    assert snap["bucket"] == "0_12"
    assert 0.0 <= snap["predicted_online"] <= 1.0
    assert snap["surprise"] >= 0.0


@pytest.mark.asyncio
async def test_persist_roundtrip():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        now = _noon_monday()
        a = OnlineRhythm()
        await a.record(db, online=True, now=now)
        await a.record(db, online=False, now=now)
        b = OnlineRhythm()
        await b.record(db, online=True, now=now)  # 触发 lazy load + 再记一次成功
        assert b._buckets["0_12"]["s"] == 2
        assert b._buckets["0_12"]["f"] == 1
        await db.close()


@pytest.mark.asyncio
async def test_world_model_domains_reserved():
    wm = WorldModel()
    assert "online_rhythm" in wm.domains
    assert wm.domains["online_rhythm"] is wm.online


@pytest.mark.asyncio
async def test_heartbeat_injects_world_surprise_in_motive():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _StubLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        brain.last_interaction = datetime.now() - timedelta(seconds=10)
        brain.user_online = True

        await brain._heartbeat()
        assert brain.last_world is not None
        assert "online_rhythm" in brain.last_world
        rows = await db.list_recent_broadcast_traces(1)
        assert len(rows) == 1
        motive = rows[0]["motive"]
        assert "world_surprise" in motive
        assert isinstance(motive["world_surprise"], (int, float))
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_world_update_still_runs():
    """拔管：LLM 全失败时 world.update 仍推进并落 body_memory。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _FailLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        brain.user_online = False

        await brain._heartbeat()
        assert brain.last_world is not None
        raw = await db.get_body_memory("world.online_rhythm")
        assert isinstance(raw, dict)
        assert "buckets" in raw
        assert raw["buckets"]
        await db.close()
