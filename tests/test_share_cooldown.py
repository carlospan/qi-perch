"""L7 share cooldown：递出节奏（对称 explore external）。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from qi.action.budget import ActionBudget
from qi.action.share import SHARE_LAST_KEY, ShareAction
from qi.core.emotion import EmotionState


@pytest.mark.asyncio
async def test_share_cooldown_no_record_first_time(db):
    share = ShareAction(db, narrative=None)
    now = datetime(2026, 8, 10, 1, 0, 0)
    assert await share._share_cooldown_ok(now) is True


@pytest.mark.asyncio
async def test_share_cooldown_blocks_within_window(db):
    share = ShareAction(db, narrative=None)
    t0 = datetime(2026, 8, 10, 1, 0, 0)
    await db.set_body_memory(SHARE_LAST_KEY, {"at": t0.isoformat(timespec="seconds")})
    assert await share._share_cooldown_ok(t0 + timedelta(hours=1)) is False


@pytest.mark.asyncio
async def test_share_cooldown_allows_after_window(db):
    share = ShareAction(db, narrative=None)
    t0 = datetime(2026, 8, 10, 1, 0, 0)
    await db.set_body_memory(SHARE_LAST_KEY, {"at": t0.isoformat(timespec="seconds")})
    assert await share._share_cooldown_ok(t0 + timedelta(hours=2)) is True


@pytest.mark.asyncio
async def test_share_cooldown_config_override(db):
    share = ShareAction(
        db,
        narrative=None,
        config={"action": {"share_cooldown_hours": 0.5}},
    )
    t0 = datetime(2026, 8, 10, 1, 0, 0)
    await db.set_body_memory(SHARE_LAST_KEY, {"at": t0.isoformat(timespec="seconds")})
    assert await share._share_cooldown_ok(t0 + timedelta(minutes=20)) is False
    assert await share._share_cooldown_ok(t0 + timedelta(minutes=30)) is True


@pytest.mark.asyncio
async def test_try_share_respects_cooldown(db):
    await db.save_creation("第一段", "note", None)
    await db.save_creation("第二段", "note", None)
    budget = ActionBudget({"action": {"autonomous_daily_limit": 20}})
    share = ShareAction(db, narrative=None)
    emotion = EmotionState()
    t0 = datetime(2026, 8, 10, 2, 0, 0)

    first = await share.try_share(emotion, "friend", budget, now=t0)
    assert first is not None
    assert first["content"] in ("第一段", "第二段")
    raw = await db.get_body_memory(SHARE_LAST_KEY)
    assert isinstance(raw, dict)
    assert raw.get("at") == t0.isoformat(timespec="seconds")

    second = await share.try_share(
        emotion, "friend", budget, now=t0 + timedelta(minutes=30)
    )
    assert second is None

    third = await share.try_share(
        emotion, "friend", budget, now=t0 + timedelta(hours=2)
    )
    assert third is not None
    assert third["creation_id"] != first["creation_id"]
    assert {first["content"], third["content"]} == {"第一段", "第二段"}
