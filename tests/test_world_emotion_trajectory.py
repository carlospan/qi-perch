"""阶段三·包 9b：自身情绪轨迹世界模型（观察项）。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.llm.gateway import LLMCallOutcome
from qi.storage.database import Database
from qi.world.emotion_trajectory import EmotionTrajectory
from qi.world.model import WorldModel


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


def _brain_stub(emotion: EmotionState, db=None) -> SimpleNamespace:
    return SimpleNamespace(emotion=emotion, _db=db)


@pytest.mark.asyncio
async def test_first_record_baseline_zero_surprise():
    traj = EmotionTrajectory()
    brain = _brain_stub(EmotionState(valence=0.2, arousal=0.3, energy=0.5))
    surp = await traj.record(brain, now=datetime.now())
    assert surp == {"valence": 0.0, "arousal": 0.0, "energy": 0.0}
    snap = traj.snapshot()
    assert snap["tracked_dims"] == ["valence", "arousal", "energy"]
    assert "surprise" in snap and "predicted_delta" in snap


@pytest.mark.asyncio
async def test_surprise_grows_when_delta_deviates():
    traj = EmotionTrajectory()
    now = datetime.now()
    # 基线
    await traj.record(
        _brain_stub(EmotionState(valence=0.0, arousal=0.3, energy=0.5)),
        now=now,
    )
    # 稳定微降若干拍 → 预测继续微降
    v = 0.0
    for _ in range(8):
        v -= 0.02
        await traj.record(
            _brain_stub(EmotionState(valence=v, arousal=0.3, energy=0.5)),
            now=now,
        )
    # 突然大涨：偏离预测 → surprise 升高
    surp_jump = await traj.record(
        _brain_stub(EmotionState(valence=v + 0.5, arousal=0.3, energy=0.5)),
        now=now,
    )
    assert surp_jump["valence"] > 1.0


@pytest.mark.asyncio
async def test_persist_roundtrip():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        now = datetime.now()
        a = EmotionTrajectory()
        await a.record(
            _brain_stub(EmotionState(valence=0.1, arousal=0.2, energy=0.6), db),
            now=now,
        )
        await a.record(
            _brain_stub(EmotionState(valence=0.0, arousal=0.25, energy=0.55), db),
            now=now,
        )
        raw = await db.get_body_memory("world.emotion_trajectory")
        assert isinstance(raw, dict)
        assert "last" in raw and "deltas" in raw
        b = EmotionTrajectory()
        await b.record(
            _brain_stub(EmotionState(valence=-0.05, arousal=0.3, energy=0.5), db),
            now=now,
        )
        # lazy load 后应已有上拍 last + 至少一条历史 delta
        assert len(b._deltas["valence"]) >= 1
        await db.close()


@pytest.mark.asyncio
async def test_world_model_domains_and_snapshot():
    wm = WorldModel()
    assert "emotion_trajectory" in wm.domains
    assert wm.domains["emotion_trajectory"] is wm.emotion_trajectory
    now = datetime.now()
    brain = _brain_stub(EmotionState(valence=0.1, arousal=0.2, energy=0.5))
    await wm.update(brain, now=now)
    snap = wm.snapshot(now=now)
    assert "online_rhythm" in snap
    assert "emotion_trajectory" in snap
    assert set(snap["emotion_trajectory"]["surprise"]) >= {
        "valence",
        "arousal",
        "energy",
    }


@pytest.mark.asyncio
async def test_heartbeat_injects_emotion_trajectory_surprise():
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

        # 两拍：首拍基线，次拍应有 emotion_trajectory_surprise 字段
        await brain._heartbeat()
        await brain._heartbeat()
        rows = await db.list_recent_broadcast_traces(2)
        assert len(rows) >= 1
        # 至少一拍 motive 含 emotion_trajectory_surprise
        found = any(
            isinstance(r.get("motive"), dict)
            and "emotion_trajectory_surprise" in r["motive"]
            for r in rows
        )
        assert found
        # 不污染 world_surprise 类型
        for r in rows:
            m = r.get("motive") or {}
            if "world_surprise" in m:
                assert isinstance(m["world_surprise"], (int, float))
            if "emotion_trajectory_surprise" in m:
                assert isinstance(m["emotion_trajectory_surprise"], dict)
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_emotion_trajectory():
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
        assert "emotion_trajectory" in brain.last_world
        raw = await db.get_body_memory("world.emotion_trajectory")
        assert isinstance(raw, dict)
        await db.close()
