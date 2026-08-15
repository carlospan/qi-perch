"""L7 together：同看意图、对象池、确认后打开。"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from qi.action.permission import can_together
from qi.action.together import (
    TogetherAction,
    TogetherRequest,
    candidates_from_action_result,
    detect_together_intent,
    looks_like_pure_open,
    looks_like_together_intent,
    resolve_from_pool,
)
from qi.storage.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


def test_can_together():
    assert can_together("acquaintance") is True
    assert can_together("stranger") is False


def test_cues_vs_pure_open():
    assert looks_like_together_intent("一起看看刚才那个")
    assert looks_like_together_intent("一起看 https://example.com/a")
    assert looks_like_pure_open("打开 https://example.com/a")
    assert not looks_like_together_intent("打开 https://example.com/a")


@pytest.mark.asyncio
async def test_detect_url_together_not_pure_open():
    tog = await detect_together_intent("一起看 https://example.com/x")
    assert tog is not None
    assert tog.target.startswith("https://")

    assert await detect_together_intent("打开 https://example.com/x") is None


def test_resolve_pool_sticky():
    now = datetime.now()
    pool = [
        {
            "target_type": "url",
            "target": "https://a.example/1",
            "title": "甲",
            "source": "explore",
            "at": now - timedelta(minutes=20),
        },
        {
            "target_type": "url",
            "target": "https://b.example/2",
            "title": "乙",
            "source": "explore",
            "at": now,
        },
    ]
    got = resolve_from_pool("一起看刚才那个", pool)
    assert got is not None
    assert got.target == "https://b.example/2"

    stale_only = [pool[0]]
    assert resolve_from_pool("一起看", stale_only) is None


def test_candidates_from_explore():
    result = {
        "type": "explore_drift",
        "outcome": "success",
        "found": {
            "entries": [
                {"title": "T", "url": "https://ex.test/p"},
                {"title": "no", "url": ""},
            ]
        },
    }
    got = candidates_from_action_result(result)
    assert len(got) == 1
    assert got[0]["source"] == "explore"


@pytest.mark.asyncio
async def test_confirm_then_open(db):
    action = TogetherAction(db)
    req = TogetherRequest(
        target="https://example.com/t",
        title="例",
        source="explore",
    )
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("needs_confirmation") is True
    assert gate.get("kind") == "together"
    assert "一起看" in (gate.get("qi_line") or "")

    with patch("qi.action.together.webbrowser.open") as open_fn:
        done = await action.execute(
            req, relationship_stage="acquaintance", confirmed=True
        )
        open_fn.assert_called_once()
    assert done.get("outcome") == "success"
    assert "一起" in (done.get("qi_line") or "")


@pytest.mark.asyncio
async def test_need_target_when_empty(db):
    action = TogetherAction(db)
    out = await action.execute(
        TogetherRequest(),
        relationship_stage="friend",
        confirmed=False,
    )
    assert out.get("need_target") is True


@pytest.mark.asyncio
async def test_layer_together(db):
    from qi.action.layer import ActionLayer
    from qi.core.emotion import ConsciousnessMode, EmotionState

    layer = ActionLayer(db, {})
    emotion = EmotionState(
        mode=ConsciousnessMode.AWAKE,
        curiosity=0.5,
        energy=0.5,
        valence=0.1,
    )
    req = TogetherRequest(target="https://example.com/z", title="z")
    gate = await layer.execute_kind(
        "together",
        emotion,
        "acquaintance",
        "spring",
        datetime.now(),
        mode="awake",
        payload=req,
        confirmed=False,
    )
    assert gate and gate.get("needs_confirmation")
