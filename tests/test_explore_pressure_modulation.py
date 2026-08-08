"""N3：explore drift / volition 受内稳态压力软调制。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qi.action.budget import ActionBudget
from qi.action.explore import PRESSURE_REST_K, PRESSURE_THROTTLE_K, ExploreAction
from qi.action.volition import action_intentions
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.storage.database import Database


def _make_pressure(throttle: float = 0.0, rest: float = 0.0) -> MagicMock:
    p = MagicMock()
    p.throttle = throttle
    p.rest = rest
    return p


class _FailLLM:
    async def call(self, *args, **kwargs) -> str:
        raise RuntimeError("LLM 不应被调用")


async def _drift_once(
    db: Database,
    curiosity: float,
    *,
    force: bool = False,
    pressure=None,
    season_scale: float = 1.0,
) -> dict | None:
    explore = ExploreAction(db, base_probability=1.0)
    return await explore.drift(
        curiosity,
        EmotionState(curiosity=curiosity),
        "spring",
        season_scale=season_scale,
        now=datetime(2026, 8, 9, 12, 0),
        force=force,
        pressure=pressure,
    )


@pytest.mark.asyncio
async def test_drift_pressure_none_unchanged(db):
    """pressure=None 时 force=False 路径与 d-3-2 一致：p=1 必过。"""
    with patch("qi.action.explore.random.random", return_value=0.99):
        result = await _drift_once(db, 1.0, pressure=None)
    assert result is not None
    assert result["type"] == "explore_drift"


@pytest.mark.asyncio
async def test_drift_throttle_reduces_probability(db):
    """throttle=1.0 时 p 减半：random=0.6 在 None 过、在 throttle 不过。"""
    assert PRESSURE_THROTTLE_K == 0.5
    with patch("qi.action.explore.random.random", return_value=0.6):
        none_ok = await _drift_once(db, 1.0, pressure=None)
        throttled = await _drift_once(
            db, 1.0, pressure=_make_pressure(throttle=1.0)
        )
    assert none_ok is not None
    assert throttled is None


@pytest.mark.asyncio
async def test_drift_rest_reduces_probability(db):
    """rest=1.0 时 p*=0.4：random=0.5 在 None 过、在 rest 不过。"""
    assert PRESSURE_REST_K == 0.6
    with patch("qi.action.explore.random.random", return_value=0.5):
        none_ok = await _drift_once(db, 1.0, pressure=None)
        rested = await _drift_once(db, 1.0, pressure=_make_pressure(rest=1.0))
    assert none_ok is not None
    assert rested is None


@pytest.mark.asyncio
async def test_drift_curiosity_threshold_unchanged(db):
    """curiosity<0.65 仍硬阈值不飘（force=False）。"""
    result = await _drift_once(
        db, 0.5, pressure=_make_pressure(throttle=1.0, rest=1.0)
    )
    assert result is None


@pytest.mark.asyncio
async def test_drift_force_pressure_soft_gate_blocks(db):
    """force=True 仍过压力软门；p_force=0.2 时 random=0.21 拦下。"""
    with patch("qi.action.explore.random.random", return_value=0.21):
        result = await _drift_once(
            db,
            0.5,
            force=True,
            pressure=_make_pressure(throttle=1.0, rest=1.0),
        )
    assert result is None


@pytest.mark.asyncio
async def test_drift_force_pressure_soft_gate_allows(db):
    """force=True 压力极高时仍保留 20%：random=0.19 放行。"""
    with patch("qi.action.explore.random.random", return_value=0.19):
        result = await _drift_once(
            db,
            0.5,
            force=True,
            pressure=_make_pressure(throttle=1.0, rest=1.0),
        )
    assert result is not None
    assert result["type"] == "explore_drift"


@pytest.mark.asyncio
async def test_drift_force_pressure_none_skips_soft_gate(db):
    """force=True 且 pressure=None：不拦（原 GWS 行为）。"""
    with patch("qi.action.explore.random.random", return_value=0.99):
        result = await _drift_once(db, 0.5, force=True, pressure=None)
    assert result is not None


def test_volition_explore_priority_throttle():
    """action_intentions：throttle=1 时 explore priority *= 0.7。"""
    now = datetime(2026, 8, 9, 12, 0)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 20}})
    kwargs = dict(
        mode="solitary",
        relationship_stage="friend",
        curiosity=0.9,
        valence=0.2,
        has_undelivered_creation=False,
        tend_occasion=None,
        user_message=None,
        budget=budget,
        now=now,
        season_scale=1.0,
        energy=0.7,
    )
    base = next(i.priority for i in action_intentions(**kwargs) if i.kind == "explore")
    throttled = next(
        i.priority
        for i in action_intentions(
            **kwargs, pressure=_make_pressure(throttle=1.0)
        )
        if i.kind == "explore"
    )
    assert throttled == pytest.approx(base * (1.0 - 0.3 * 1.0))


@pytest.mark.asyncio
async def test_brain_last_pressure_response_updated():
    """brain 每拍 heartbeat 更新 last_pressure_response。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {
                "tts": {"enabled": False},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
            },
            _FailLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        assert brain.last_pressure_response is None
        await brain._heartbeat()
        assert brain.last_pressure_response is not None
        assert hasattr(brain.last_pressure_response, "throttle")
        assert hasattr(brain.last_pressure_response, "rest")
        await db.close()
