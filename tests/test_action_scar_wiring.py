"""Step 5 伤疤接线：失败行动形成伤疤。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from qi.action.layer import ActionLayer
from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_FAILED_JUDGMENT,
    OUTCOME_OVERSTEPPED,
    OUTCOME_SUCCESS,
    scar_blocks_kind,
)
from qi.core.emotion import EmotionState


@pytest.mark.asyncio
async def test_maybe_save_scar_failed_judgment(db):
    """outcome=failed_judgment → save_scar，severity=0.3，origin 含 [action:kind]。"""
    layer = ActionLayer(db, {})
    result = {
        "outcome": OUTCOME_FAILED_JUDGMENT,
        "summary": "不该这时候递给你看",
    }
    await layer._maybe_save_scar(
        result, "explore", datetime(2026, 8, 9, 12, 0), trust=0.62
    )
    assert result.get("created_scar") is not None
    scars = await db.list_scars()
    assert len(scars) == 1
    scar = scars[0]
    assert "[action:explore]" in scar["origin_event"]
    assert scar["severity"] == pytest.approx(0.3)
    assert scar["trust_before"] == pytest.approx(0.62)


@pytest.mark.asyncio
async def test_maybe_save_scar_overstepped_severity(db):
    """outcome=overstepped → severity=0.7。"""
    layer = ActionLayer(db, {})
    result = {"outcome": OUTCOME_OVERSTEPPED, "summary": "越界了"}
    await layer._maybe_save_scar(
        result, "assist", datetime(2026, 8, 9, 12, 0), trust=0.5
    )
    scars = await db.list_scars()
    assert scars[0]["severity"] == pytest.approx(0.7)
    assert "[action:assist]" in scars[0]["origin_event"]


@pytest.mark.asyncio
async def test_success_outcome_no_scar(db):
    """outcome=success → 不调 save_scar。"""
    layer = ActionLayer(db, {})
    layer.db.save_scar = AsyncMock(wraps=layer.db.save_scar)  # type: ignore[method-assign]
    result = {"outcome": OUTCOME_SUCCESS, "summary": "ok"}
    await layer._maybe_save_scar(
        result, "explore", datetime(2026, 8, 9, 12, 0)
    )
    layer.db.save_scar.assert_not_called()
    assert "created_scar" not in result
    assert await db.list_scars() == []


@pytest.mark.asyncio
async def test_failed_capability_no_scar(db):
    """outcome=failed_capability → 不调 save_scar。"""
    layer = ActionLayer(db, {})
    layer.db.save_scar = AsyncMock(wraps=layer.db.save_scar)  # type: ignore[method-assign]
    result = {"outcome": OUTCOME_FAILED_CAPABILITY, "summary": "搜不到"}
    await layer._maybe_save_scar(
        result, "explore", datetime(2026, 8, 9, 12, 0)
    )
    layer.db.save_scar.assert_not_called()
    assert await db.list_scars() == []


@pytest.mark.asyncio
async def test_scar_blocks_kind_after_save(db):
    """伤疤后 scar_blocks_kind(kind, scars) 返回 True。"""
    layer = ActionLayer(db, {})
    result = {"outcome": OUTCOME_FAILED_JUDGMENT, "summary": "手缩"}
    await layer._maybe_save_scar(
        result, "explore", datetime(2026, 8, 9, 12, 0)
    )
    scars = await db.list_scars(unhealed_only=True)
    assert scar_blocks_kind("explore", scars) is True
    assert scar_blocks_kind("share", scars) is False


@pytest.mark.asyncio
async def test_execute_kind_overstepped_creates_scar(db):
    """execute_kind 路径：result.outcome=overstepped → save_scar。"""
    layer = ActionLayer(db, {"action": {"autonomous_daily_limit": 20}})
    layer.explore.drift = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "type": "explore_drift",
            "found": None,
            "summary": "越界探索",
            "action_id": 1,
            "season": "spring",
            "curiosity": 0.9,
            "source": "journal",
            "sandbox": ".",
            "outcome": OUTCOME_OVERSTEPPED,
        }
    )
    emotion = EmotionState(curiosity=0.9, energy=0.8)
    result = await layer.execute_kind(
        "explore",
        emotion,
        "friend",
        "spring",
        datetime(2026, 8, 9, 12, 0),
        mode="solitary",
        trust=0.71,
    )
    assert result is not None
    assert result.get("created_scar") is not None
    scars = await db.list_scars()
    assert scars[0]["severity"] == pytest.approx(0.7)
    assert scars[0]["trust_before"] == pytest.approx(0.71)
    assert "[action:explore]" in scars[0]["origin_event"]


@pytest.mark.asyncio
async def test_return_dict_carries_outcome_success(db):
    """§0：现网成功路径 return 带 outcome=success（不建疤）。"""
    layer = ActionLayer(db, {"action": {"autonomous_daily_limit": 20}})
    layer.explore.drift = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "type": "explore_drift",
            "found": None,
            "summary": "飘了一下",
            "action_id": 1,
            "season": "spring",
            "curiosity": 0.9,
            "source": "journal",
            "sandbox": ".",
            "outcome": OUTCOME_SUCCESS,
        }
    )
    result = await layer.execute_kind(
        "explore",
        EmotionState(curiosity=0.9),
        "friend",
        "spring",
        datetime(2026, 8, 9, 12, 0),
        mode="solitary",
    )
    assert result is not None
    assert result.get("outcome") == OUTCOME_SUCCESS
    assert "created_scar" not in result
    assert await db.list_scars() == []
