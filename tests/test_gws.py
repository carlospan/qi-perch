"""阶段二·包 7：GWS 仲裁与 shadow。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.core.gws import (
    GWS_SHADOW_KEY,
    arbitrate,
    executable_contenders,
    gws_config,
    load_shadow_stats,
    record_shadow_beat,
    shadow_match,
    shadow_rate,
)
from qi.core.trace import Contender
from qi.llm.gateway import LLMCallOutcome
from qi.storage.database import Database


def test_arbitrate_picks_highest_salience():
    winner = arbitrate(
        [
            Contender("proactive:check_in", 0.4, "a"),
            Contender("action:explore", 0.7, "b"),
            Contender("proactive:reach_out", 0.5, "c"),
        ]
    )
    assert winner is not None
    assert winner.kind == "action:explore"


def test_arbitrate_tie_break_by_family():
    winner = arbitrate(
        [
            Contender("action:explore", 0.9, "a"),
            Contender("close_loop", 0.9, "b"),
            Contender("proactive:check_in", 0.9, "c"),
        ]
    )
    assert winner is not None
    assert winner.kind == "close_loop"


def test_respond_never_overridden():
    winner = arbitrate(
        [
            Contender("proactive:express_feeling", 1.0, "拉满"),
            Contender("respond", 1.0, "用户"),
            Contender("close_loop", 1.0, "心事"),
        ]
    )
    assert winner is not None
    assert winner.kind == "respond"


def test_executable_filters_report_and_loop():
    raw = [
        Contender("respond", 1.0, ""),
        Contender("close_loop", 0.8, ""),
        Contender("report", 0.6, ""),
        Contender("proactive:check_in", 0.5, ""),
    ]
    exe = executable_contenders(raw)
    kinds = {c.kind for c in exe}
    assert "respond" in kinds
    assert "proactive:check_in" in kinds
    assert "close_loop" not in kinds
    assert "report" not in kinds


def test_shadow_match_and_rate():
    assert shadow_match("respond", "respond")
    assert shadow_match(None, "idle")
    assert not shadow_match("idle", "proactive:x")
    assert shadow_rate({"beats": 100, "matches": 99}) == 0.99
    assert shadow_rate({"beats": 0, "matches": 0}) == 0.0


@pytest.mark.asyncio
async def test_shadow_stats_ready_threshold():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        cfg = {"gws": {"shadow_beats": 5, "shadow_match_min": 0.8}}
        for i in range(5):
            await record_shadow_beat(db, matched=(i < 4), config=cfg)
        stats = await load_shadow_stats(db)
        assert stats["beats"] == 5
        assert stats["matches"] == 4
        assert stats["ready"] is True
        raw = await db.get_body_memory(GWS_SHADOW_KEY)
        assert raw["ready"] is True
        await db.close()


class _StubLLM:
    def __init__(self, text: str = "嗯。"):
        self.text = text
        self.last_outcome = LLMCallOutcome(text=text, failure=None)
        self.calls = 0

    async def call(self, purpose, messages, temperature=None):
        self.calls += 1
        return self.text


class _FailLLM:
    def __init__(self):
        self.last_outcome = LLMCallOutcome(text="", failure="unreachable")

    async def call(self, purpose, messages, temperature=None):
        return ""


@pytest.mark.asyncio
async def test_shadow_default_writes_arb_fields():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {
                "tts": {"enabled": False},
                "gws": {"enabled": False},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
            },
            _StubLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        from qi.relationship.engine import RelationshipEngine

        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "friend"
        brain._pending_queue.append("你好")
        await brain._heartbeat()
        rows = await db.list_recent_broadcast_traces(1)
        assert rows[0]["winner_kind"] == "respond"
        assert rows[0]["winner_arb"] == "respond"
        assert rows[0]["arb_matches_legacy"] == 1
        await db.close()


@pytest.mark.asyncio
async def test_gws_enabled_dispatches_proactive():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {
                "tts": {"enabled": False},
                "gws": {"enabled": True},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
            },
            _StubLLM("……有一点想说。"),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        from qi.relationship.engine import RelationshipEngine

        brain.relationship = RelationshipEngine(db, None, {})
        await brain.relationship.restore()
        brain.relationship.state.stage = "bonded"
        brain.user_online = True
        brain.last_interaction = datetime.now() - timedelta(seconds=100)
        # 抬高表达欲：上一拍 valence 低、本拍抬升
        brain._prev_valence = -0.2
        brain.emotion = EmotionState(valence=0.5, energy=0.7, attachment=0.5)
        # action=None：启用路径走 _heartbeat_gws_idle，不会调用 legacy action.tick
        await brain._heartbeat_gws_idle(want_express=True, now=datetime.now())
        assert brain._gws_broadcast_hint is not None
        assert "winner_arb_kind" in brain._gws_broadcast_hint
        arb = brain._gws_broadcast_hint["winner_arb_kind"]
        assert isinstance(arb, str) and arb  # 非平凡标签（idle/proactive/…）
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_gws_still_arbitrates():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {
                "tts": {"enabled": False},
                "gws": {"enabled": True},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
            },
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
        brain._pending_queue.append("在吗")
        await brain._heartbeat()
        rows = await db.list_recent_broadcast_traces(1)
        assert rows[0]["winner_kind"] == "respond"
        assert rows[0]["winner_arb"] == "respond"
        await db.close()


def test_gws_config_defaults():
    c = gws_config({})
    assert c["enabled"] is False
    assert c["shadow_beats"] == 50
    assert c["shadow_match_min"] == 0.99
