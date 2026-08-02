"""阶段二·包 6：广播痕迹 + salience 地基。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.core.proactive import KIND_EXPRESS_FEELING, ProactiveGate
from qi.core.trace import (
    Contender,
    collect_contenders,
    outcome_from_legacy,
    salience_action,
    salience_close_loop,
    salience_respond,
    winner_from_legacy,
)
from qi.llm.gateway import LLMCallOutcome
from qi.storage.database import Database


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


def test_salience_boundaries():
    assert salience_respond(has_pending=True) == 1.0
    assert salience_respond(has_pending=False) == 0.0
    assert salience_action(priority=0.0) == 0.0
    assert salience_action(priority=1.0) == 1.0
    assert salience_close_loop(open_loop_count=0) == 0.0
    assert salience_close_loop(open_loop_count=1) >= 0.3
    assert salience_close_loop(open_loop_count=5) == 1.0


def test_salience_report_uptime_three_hours():
    from qi.core.trace import salience_report

    assert (
        salience_report(
            energy=0.6,
            security=0.5,
            uptime_seconds=3 * 3600 + 1,
        )
        > 0
    )
    assert (
        salience_report(
            energy=0.6,
            security=0.5,
            uptime_seconds=2 * 3600,
        )
        == 0.0
    )


def test_winner_from_legacy_pending_beats_higher_salience():
    cands = [
        Contender("respond", 1.0, "用户"),
        Contender("proactive:express_feeling", 0.99, "很响"),
    ]
    kind, sal = winner_from_legacy(
        pending="你好",
        kind="express_feeling",
        action_type=None,
        candidates=cands,
    )
    assert kind == "respond"
    assert sal == 1.0


def test_outcome_labels():
    assert (
        outcome_from_legacy(
            pending="x", kind=None, action_type=None, want_express=False
        )
        == "responded"
    )
    assert (
        outcome_from_legacy(
            pending=None, kind="check_in", action_type=None, want_express=True
        )
        == "proactive"
    )
    assert (
        outcome_from_legacy(
            pending=None, kind=None, action_type="explore", want_express=False
        )
        == "action"
    )
    assert (
        outcome_from_legacy(
            pending=None, kind=None, action_type=None, want_express=True
        )
        == "suppressed"
    )
    assert (
        outcome_from_legacy(
            pending=None, kind=None, action_type=None, want_express=False
        )
        == "idle"
    )


@pytest.mark.asyncio
async def test_broadcast_each_beat_and_idle_fields():
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

        for _ in range(3):
            await brain._heartbeat()

        rows = await db.list_recent_broadcast_traces(10)
        assert len(rows) == 3
        for r in rows:
            assert "beat" in r
            assert "winner_kind" in r
            assert "winner_salience" in r
            assert isinstance(r["candidates"], list)
            assert isinstance(r["motive"], dict)
            assert r["outcome"] in (
                "idle",
                "suppressed",
                "proactive",
                "action",
                "responded",
            )
        # 至少有一拍可无用户候选（空闲）
        idleish = [r for r in rows if r["winner_kind"] == "idle"]
        if idleish:
            assert isinstance(idleish[0]["candidates"], list)
        await db.close()


@pytest.mark.asyncio
async def test_pending_beat_respond_highest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _StubLLM("……在。"),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.user_online = True
        from qi.relationship.engine import RelationshipEngine

        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "friend"

        brain._pending_queue.append("你好呀")
        await brain._heartbeat()
        rows = await db.list_recent_broadcast_traces(1)
        assert len(rows) == 1
        row = rows[0]
        assert row["winner_kind"] == "respond"
        kinds = {c["kind"]: c["salience"] for c in row["candidates"]}
        assert "respond" in kinds
        assert kinds["respond"] == max(kinds.values())
        assert kinds["respond"] == 1.0
        await db.close()


@pytest.mark.asyncio
async def test_proactive_candidate_in_collect():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain({"tts": {"enabled": False}}, _StubLLM())  # type: ignore[arg-type]
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.user_online = True
        from qi.relationship.engine import RelationshipEngine

        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "friend"
        brain.proactive = ProactiveGate({})
        brain.emotion = EmotionState(valence=0.4, energy=0.6)
        brain.last_interaction = datetime.now() - timedelta(seconds=100)
        now = datetime.now()
        cands = await collect_contenders(
            brain,
            pending=None,
            want_express=True,
            kind=KIND_EXPRESS_FEELING,
            action_type=None,
            now=now,
        )
        kinds = [c.kind for c in cands]
        assert any(k == f"proactive:{KIND_EXPRESS_FEELING}" for k in kinds)
        await db.close()


@pytest.mark.asyncio
async def test_close_loop_contender_when_open_loops_present():
    """补丁 D：非空 open_loops → collect 注入 close_loop 且 sal>0。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        from qi.memory.open_loops import OpenLoopQueue

        q = OpenLoopQueue(db)
        await q.enqueue("silence", seed="")
        assert q.count() >= 1

        brain = Brain({"tts": {"enabled": False}}, _StubLLM())  # type: ignore[arg-type]
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.user_online = True
        brain.emotion = EmotionState(valence=0.2, energy=0.6)
        brain.last_interaction = datetime.now() - timedelta(seconds=60)
        now = datetime.now()
        cands = await collect_contenders(
            brain,
            pending=None,
            want_express=False,
            kind=None,
            action_type=None,
            now=now,
        )
        close = [c for c in cands if c.kind == "close_loop"]
        assert close
        assert close[0].salience > 0
        assert salience_close_loop(open_loop_count=1) > 0
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_still_writes_broadcast():
    """拔管：LLM 全失败时痕迹仍落盘。"""
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
        from qi.relationship.engine import RelationshipEngine

        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "friend"
        brain._pending_queue.append("还在吗")
        await brain._heartbeat()
        rows = await db.list_recent_broadcast_traces(1)
        assert len(rows) == 1
        assert rows[0]["winner_kind"] == "respond"
        await db.close()
