"""阶段一·包 2：阶段锚、关系事件 nudge、大承诺日帽。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from qi.core.emotion import (
    BASELINES,
    MAJOR_COMMITMENT_DAILY_CAP,
    MAJOR_COMMITMENT_GATE_KEY,
    EmotionState,
    apply_coupling,
    apply_decay,
    apply_relationship_emotion_nudge,
    baseline_for,
    is_major_commitment_signal,
    step_emotion,
)
from qi.relationship.engine import STAGE_TEMPERATURE_COMFORT, RelationshipEngine
from qi.storage.database import Database


def test_stranger_baselines_match_global():
    assert baseline_for("attachment", "stranger") == BASELINES["attachment"]
    assert baseline_for("security", "stranger") == BASELINES["security"]


def test_bonded_attachment_baseline_significantly_higher():
    assert baseline_for("attachment", "bonded") == pytest.approx(0.62)
    assert baseline_for("security", "bonded") == pytest.approx(0.72)
    assert baseline_for("attachment", "bonded") - baseline_for(
        "attachment", "stranger"
    ) >= 0.25


def test_bonded_decay_targets_stage_anchor():
    e = EmotionState(attachment=0.2, security=0.3)
    after = e
    for _ in range(80):
        after = apply_decay(after, dt=1.0, relationship_stage="bonded")
    assert abs(after.attachment - 0.62) < abs(e.attachment - 0.62)
    assert abs(after.attachment - 0.62) < 0.05
    assert abs(after.security - 0.72) < 0.08


def test_stranger_decay_still_targets_03():
    e = EmotionState(attachment=0.9)
    after = e
    for _ in range(80):
        after = apply_decay(after, dt=1.0, relationship_stage="stranger")
    assert abs(after.attachment - 0.3) < 0.05


def test_coupling_unmet_uses_stage_anchor():
    """贴 bonded 锚时 unmet 偏离≈0，不应系统性抬 valence。"""
    e = EmotionState(attachment=0.62, security=0.72, valence=0.1)
    after = apply_coupling(e, relationship_stage="bonded")
    assert abs(after.valence - e.valence) < 0.02


def test_coupling_low_security_still_raises_attachment():
    e = EmotionState(security=0.2, attachment=0.3)
    after = apply_coupling(e, relationship_stage="stranger")
    assert after.attachment > e.attachment


def test_stage_changed_nudge():
    e = EmotionState(attachment=0.48, security=0.62)
    after = apply_relationship_emotion_nudge(
        e,
        {
            "stage_changed": True,
            "new_stage": "bonded",
            "scar_created": False,
            "signals": None,
        },
    )
    assert after.attachment == pytest.approx(0.58)
    assert after.security == pytest.approx(0.68)


def test_scar_nudge():
    e = EmotionState(attachment=0.5, security=0.6, valence=0.2)
    after = apply_relationship_emotion_nudge(
        e,
        {"stage_changed": False, "scar_created": True, "signals": None},
    )
    assert after.attachment < e.attachment
    assert after.security < e.security
    assert after.valence < e.valence


def test_commitment_nudge_and_skip_when_disallowed():
    signals = SimpleNamespace(
        creator_disclosure=0.7, is_deep=False, self_disclosure=0.0
    )
    assert is_major_commitment_signal(signals)
    e = EmotionState(attachment=0.4, security=0.5)
    yes = apply_relationship_emotion_nudge(
        e,
        {"stage_changed": False, "scar_created": False, "signals": signals},
        allow_commitment=True,
    )
    no = apply_relationship_emotion_nudge(
        e,
        {"stage_changed": False, "scar_created": False, "signals": signals},
        allow_commitment=False,
    )
    assert yes.attachment > e.attachment
    assert no.attachment == e.attachment


def test_commitment_skipped_on_stage_change():
    signals = SimpleNamespace(
        creator_disclosure=0.7, is_deep=False, self_disclosure=0.0
    )
    e = EmotionState(attachment=0.48, security=0.62)
    after = apply_relationship_emotion_nudge(
        e,
        {
            "stage_changed": True,
            "new_stage": "bonded",
            "scar_created": False,
            "signals": signals,
        },
        allow_commitment=True,
    )
    # 只有升档 nudge，无额外 +0.05
    assert after.attachment == pytest.approx(0.58)


@pytest.mark.asyncio
async def test_major_commitment_daily_cap_persists():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        now = datetime(2026, 8, 2, 3, 0, 0)

        class _LLM:
            async def call(self, purpose, messages, temperature=None):
                return ""

        from qi.core.brain import Brain

        brain = Brain({"tts": {"enabled": False}}, _LLM())  # type: ignore[arg-type]
        brain._db = db
        for _ in range(MAJOR_COMMITMENT_DAILY_CAP):
            assert await brain._consume_major_commitment_quota(now) is True
        assert await brain._consume_major_commitment_quota(now) is False
        gate = await db.get_body_memory(MAJOR_COMMITMENT_GATE_KEY)
        assert gate["day"] == "2026-08-02"
        assert gate["count"] == MAJOR_COMMITMENT_DAILY_CAP
        brain2 = Brain({"tts": {"enabled": False}}, _LLM())  # type: ignore[arg-type]
        brain2._db = db
        assert await brain2._consume_major_commitment_quota(now) is False
        await db.close()


@pytest.mark.asyncio
async def test_temperature_drifts_without_interaction():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        engine = RelationshipEngine(db, llm=None)
        await engine.restore()
        engine.state.stage = "bonded"
        engine.state.temperature = 1.0
        engine.state.trust = 1.0
        engine._interaction_day = "2026-08-01"
        engine._had_interaction_today = False
        engine._roll_day(datetime(2026, 8, 2, 10, 0, 0))
        assert engine.state.temperature < 1.0
        comfort = STAGE_TEMPERATURE_COMFORT["bonded"]
        assert engine.state.temperature > comfort
        assert engine.state.trust < 1.0
        await db.close()


def test_step_emotion_bonded_pulls_attachment_up():
    e = EmotionState(attachment=0.3, security=0.5)
    after = e
    for _ in range(30):
        after = step_emotion(
            after, datetime(2026, 8, 2, 12, 0, 0), relationship_stage="bonded"
        )
    assert after.attachment > 0.5
