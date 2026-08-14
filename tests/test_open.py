"""L7 open：意图、确认门、URL/白名单、教会。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.layer import ActionLayer
from qi.action.open import (
    OpenAction,
    OpenRequest,
    detect_open_intent,
    find_whitelist_entry,
    load_whitelist,
    looks_like_open_intent,
)
from qi.action.permission import can_open
from qi.core.emotion import ConsciousnessMode, EmotionState


def test_looks_like_open_url_and_look():
    assert looks_like_open_intent("打开 https://example.com/a")
    assert looks_like_open_intent("看看这个链接 https://example.com/b")
    assert not looks_like_open_intent("帮我看看这个文件 D:/a.txt")
    assert not looks_like_open_intent("你在干嘛")


@pytest.mark.asyncio
async def test_detect_open_and_look_strong():
    req = await detect_open_intent("帮我看看这个链接 https://example.com/x")
    assert req is not None
    assert req.intent == "open_and_look"
    assert req.target_type == "url"
    assert "example.com" in req.target


@pytest.mark.asyncio
async def test_detect_open_only():
    req = await detect_open_intent("帮我打开 https://example.com/y")
    assert req is not None
    assert req.intent == "open"
    assert req.target_type == "url"


def test_can_open_acquaintance():
    assert not can_open("stranger")
    assert can_open("acquaintance")
    assert can_open("friend")


@pytest.mark.asyncio
async def test_open_url_needs_confirm_then_opens(db):
    action = OpenAction(
        db, config={"action": {"open": {"look_after_delay_seconds": 0}}}
    )
    req = OpenRequest(
        intent="open", target_type="url", target="https://example.com/z"
    )
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("needs_confirmation")
    assert gate.get("kind") == "open"

    with patch("qi.action.open.webbrowser.open") as opener:
        done = await action.execute(
            req, relationship_stage="acquaintance", confirmed=True
        )
        opener.assert_called_once()
    assert done.get("outcome") == "success"
    assert "开了" in (done.get("qi_line") or "")


@pytest.mark.asyncio
async def test_open_url_rejects_file_scheme(db):
    action = OpenAction(db)
    req = OpenRequest(
        intent="open", target_type="url", target="file:///C:/secret.txt"
    )
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_open_app_not_in_whitelist(db):
    action = OpenAction(db)
    req = OpenRequest(intent="open", target_type="app", target="网易云")
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"
    assert "教" in (out.get("qi_line") or "")


@pytest.mark.asyncio
async def test_teach_then_open_app(db, tmp_path):
    fake = tmp_path / "cloudmusic.exe"
    fake.write_text("x")
    action = OpenAction(db)
    req = OpenRequest(
        intent="teach",
        target_type="app",
        target="网易云",
        candidates=[
            {"alias": "网易云", "path": str(fake), "label": "cloudmusic.exe"}
        ],
    )
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("needs_confirmation")

    taught = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert taught.get("outcome") == "success"
    entries = await load_whitelist(db)
    assert find_whitelist_entry(entries, "网易云")

    open_req = OpenRequest(intent="open", target_type="app", target="网易云")
    with patch.object(OpenAction, "_launch_path") as launch:
        done = await action.execute(
            open_req, relationship_stage="acquaintance", confirmed=True
        )
        launch.assert_called_once()
    assert done.get("outcome") == "success"


@pytest.mark.asyncio
async def test_open_and_look_calls_glance(db):
    look = MagicMock()
    look.glance = AsyncMock(
        return_value={
            "outcome": "success",
            "qi_line": "好像是个网页。",
        }
    )
    action = OpenAction(
        db,
        look=look,
        config={"action": {"open": {"look_after_delay_seconds": 0}}},
    )
    req = OpenRequest(
        intent="open_and_look",
        target_type="url",
        target="https://example.com/look",
    )
    with patch("qi.action.open.webbrowser.open"):
        with patch("qi.action.open.asyncio.sleep", new_callable=AsyncMock):
            done = await action.execute(
                req, relationship_stage="friend", confirmed=True
            )
    assert "网页" in (done.get("qi_line") or "")
    look.glance.assert_awaited()


@pytest.mark.asyncio
async def test_debounce(db):
    action = OpenAction(
        db, config={"action": {"open": {"debounce_seconds": 60}}}
    )
    req = OpenRequest(
        intent="open", target_type="url", target="https://example.com/d"
    )
    with patch("qi.action.open.webbrowser.open"):
        await action.execute(
            req, relationship_stage="acquaintance", confirmed=True
        )
        again = await action.execute(
            req, relationship_stage="acquaintance", confirmed=True
        )
    assert "刚开过" in (again.get("qi_line") or "")


@pytest.mark.asyncio
async def test_stranger_blocked(db):
    action = OpenAction(db)
    req = OpenRequest(
        intent="open", target_type="url", target="https://example.com/s"
    )
    out = await action.execute(
        req, relationship_stage="stranger", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_layer_execute_kind_open(db):
    layer = ActionLayer(db, config={})
    emotion = EmotionState()
    emotion.mode = ConsciousnessMode.AMBIENT
    req = OpenRequest(
        intent="open", target_type="url", target="https://example.com/L"
    )
    with patch("qi.action.open.webbrowser.open"):
        gate = await layer.execute_kind(
            "open",
            emotion,
            "acquaintance",
            "spring",
            datetime.now(),
            mode="ambient",
            payload=req,
            confirmed=False,
        )
    assert gate and gate.get("needs_confirmation")
