"""L7 open：意图、确认门、URL/白名单、授权 allow。"""

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
    is_plausible_app_alias,
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
    assert not looks_like_open_intent("对的，我还不睡，你现在改代码")


def test_plausible_app_alias_rejects_chat_fragments():
    assert is_plausible_app_alias("企微")
    assert is_plausible_app_alias("企业微信")
    assert is_plausible_app_alias("网易云")
    assert not is_plausible_app_alias("我还不睡，你现在")
    assert not is_plausible_app_alias("对的我还不睡")
    assert not is_plausible_app_alias("a")
    assert not is_plausible_app_alias("")


@pytest.mark.asyncio
async def test_detect_open_app_alias_short():
    req = await detect_open_intent("打开企微")
    assert req is not None
    assert req.intent == "open"
    assert req.target == "企微"


@pytest.mark.asyncio
async def test_detect_strips_一下_from_alias():
    req = await detect_open_intent("打开一下企业微信")
    assert req is not None
    assert req.intent == "open"
    assert req.target == "企业微信"
    req2 = await detect_open_intent("开一下企微")
    assert req2 is not None
    assert req2.target == "企微"


@pytest.mark.asyncio
async def test_detect_rejects_chatty_false_alias():
    # 无打开线索 → gate 挡；有「打开」但后接闲聊碎片 → 别名校验挡
    assert await detect_open_intent("对的，我还不睡，你现在改代码") is None
    assert await detect_open_intent("打开我还不睡你现在") is None


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


@pytest.mark.asyncio
async def test_detect_allow_from_以后帮开():
    req = await detect_open_intent("以后企微你可以帮我开")
    assert req is not None
    assert req.intent == "allow"
    assert "企微" in req.target


def test_can_open_acquaintance():
    assert not can_open("stranger")
    assert can_open("acquaintance")
    assert can_open("friend")


@pytest.mark.asyncio
async def test_open_url_needs_confirm_then_opens(db):
    action = OpenAction(db)
    req = OpenRequest(
        intent="open", target_type="url", target="https://example.com/z"
    )
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("needs_confirmation")
    with patch("qi.action.open.webbrowser.open") as opener:
        done = await action.execute(
            req, relationship_stage="acquaintance", confirmed=True
        )
        opener.assert_called_once()
    assert done.get("outcome") == "success"


@pytest.mark.asyncio
async def test_open_url_rejects_file_scheme(db):
    action = OpenAction(db)
    req = OpenRequest(
        intent="open", target_type="url", target="file:///C:/a.txt"
    )
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_open_app_not_in_whitelist_offers_allow(db):
    action = OpenAction(db)
    req = OpenRequest(intent="open", target_type="app", target="网易云")
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert out.get("outcome") == "confirm_required"
    assert out.get("needs_confirmation") is True
    assert out.get("promote_intent") == "allow"
    assert out.get("allow_alias") == "网易云"
    assert "以后" in (out.get("qi_line") or "") and "帮你开" in (
        out.get("qi_line") or ""
    )
    assert "教" not in (out.get("qi_line") or "")


@pytest.mark.asyncio
async def test_open_app_not_in_whitelist_confirmed_still_fails(db):
    action = OpenAction(db)
    req = OpenRequest(intent="open", target_type="app", target="网易云")
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_allow_then_open_app(db, tmp_path):
    fake = tmp_path / "cloudmusic.exe"
    fake.write_text("x")
    action = OpenAction(db)
    req = OpenRequest(
        intent="allow",
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

    allowed = await action.execute(
        req, relationship_stage="acquaintance", confirmed=True
    )
    assert allowed.get("outcome") == "success"
    assert allowed.get("offer_open_now") is True
    assert "没开" in (allowed.get("qi_line") or "")
    assert "现在开吗" in (allowed.get("qi_line") or "")
    assert "开前还是会问" not in (allowed.get("qi_line") or "")
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
            "qi_line": "网页上好像是排行榜。",
        }
    )
    action = OpenAction(db, look=look)
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


@pytest.mark.asyncio
async def test_brain_whitelist_miss_要_promotes_allow(tmp_path):
    """未在白名单 → 要约授权 pending；用户「要」→ allow 找候选再确认。"""
    import tempfile
    from pathlib import Path

    from qi.core.brain import Brain

    class _FakeLLM:
        async def call(self, purpose, messages, temperature=None):
            return ""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from qi.storage.database import Database

        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {
                "tts": {"enabled": False},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
            },
            _FakeLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = ActionLayer(db, {}, llm=_FakeLLM())
        brain.inner_life = None
        brain.first_times = None
        brain.memory = None
        brain.user_online = True
        brain.emotion = EmotionState(
            mode=ConsciousnessMode.AWAKE,
            curiosity=0.5,
            energy=0.7,
            valence=0.2,
        )
        rel = MagicMock()
        rel.state.stage = "friend"
        rel.state.trust = 0.7
        rel.state.season = "spring"
        brain.relationship = rel

        fake = tmp_path / "Weixin.exe"
        fake.write_text("x")

        with patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ), patch.object(
            brain, "_deliver_qi_message", new_callable=AsyncMock
        ), patch(
            "qi.action.open.find_app_candidates",
            return_value=[
                {
                    "alias": "企微",
                    "path": str(fake),
                    "label": "Weixin.exe",
                }
            ],
        ):
            line = await brain.receive_user_message("打开企微")
            assert line is not None
            assert "以后" in line or "帮你开" in line
            assert "教" not in line
            pending = brain.pending_assist_confirmation
            assert pending is not None
            assert getattr(pending, "intent", None) == "allow"
            assert getattr(pending, "target", None) == "企微"

            line2 = await brain.receive_user_message("要")
            assert line2 is not None
            assert "以后都可以帮你开" in line2 or "找到这些" in line2
            pending2 = brain.pending_assist_confirmation
            assert pending2 is not None
            assert getattr(pending2, "intent", None) == "allow"
            assert getattr(pending2, "candidates", None)

            line3 = await brain.receive_user_message("开吧")
            assert line3 is not None
            assert "记下了" in line3 and "没开" in line3
            assert "现在开吗" in line3
            pending3 = brain.pending_assist_confirmation
            assert pending3 is not None
            assert getattr(pending3, "intent", None) == "open"
            assert getattr(pending3, "target", None) == "企微"
            entries = await load_whitelist(db)
            assert find_whitelist_entry(entries, "企微")

            with patch.object(
                OpenAction, "_launch_path"
            ) as launch:
                line4 = await brain.receive_user_message("开吧")
                assert "开了" in (line4 or "")
                launch.assert_called_once()
            assert brain.pending_assist_confirmation is None

        await db.close()


def test_confirm_cue_要_is_exact_short():
    from qi.core.brain import Brain

    brain = Brain({}, MagicMock())
    assert brain._is_confirm_cue("要") is True
    assert brain._is_confirm_cue("要的") is True
    assert brain._is_confirm_cue("需要") is False
    assert brain._is_confirm_cue("重要") is False


def test_alias_needles_include_synonyms():
    from qi.action.open import _alias_needles

    needles = _alias_needles("企微")
    assert "企微" in needles
    assert "企业微信" in needles
    assert "wxwork" in needles


def test_find_app_candidates_start_menu(tmp_path, monkeypatch):
    from qi.action import open as open_mod

    monkeypatch.setattr(open_mod.sys, "platform", "win32")
    programs = tmp_path / "Programs"
    programs.mkdir()
    lnk = programs / "企业微信.lnk"
    lnk.write_bytes(b"fake")
    exe = tmp_path / "WXWork.exe"
    exe.write_text("x", encoding="utf-8")

    monkeypatch.setattr(open_mod, "_start_menu_roots", lambda: [programs])
    monkeypatch.setattr(open_mod, "_known_install_roots", lambda: [])
    monkeypatch.setattr(open_mod, "_resolve_shortcut", lambda p: exe)
    monkeypatch.setattr(
        open_mod.subprocess,
        "run",
        lambda *a, **k: MagicMock(stdout="", returncode=1),
    )

    found = open_mod.find_app_candidates("企微", limit=3)
    assert found
    assert any("WXWork.exe" in c["path"] for c in found)


def test_find_app_candidates_known_install_dir(tmp_path, monkeypatch):
    from qi.action import open as open_mod

    monkeypatch.setattr(open_mod.sys, "platform", "win32")
    pf = tmp_path / "Program Files"
    app = pf / "WXWork"
    app.mkdir(parents=True)
    exe = app / "WXWork.exe"
    exe.write_text("x", encoding="utf-8")

    monkeypatch.setattr(open_mod, "_start_menu_roots", lambda: [])
    monkeypatch.setattr(open_mod, "_known_install_roots", lambda: [pf])
    monkeypatch.setattr(
        open_mod.subprocess,
        "run",
        lambda *a, **k: MagicMock(stdout="", returncode=1),
    )

    found = open_mod.find_app_candidates("企业微信", limit=3)
    assert found
    assert any(c["path"].endswith("WXWork.exe") for c in found)


def test_find_app_candidates_direct_path(tmp_path):
    from qi.action.open import find_app_candidates

    exe = tmp_path / "foo.exe"
    exe.write_text("x", encoding="utf-8")
    found = find_app_candidates(str(exe), limit=1)
    assert len(found) == 1
    assert found[0]["path"].endswith("foo.exe")


def test_find_app_candidates_skips_uninstall(tmp_path, monkeypatch):
    from qi.action import open as open_mod

    monkeypatch.setattr(open_mod.sys, "platform", "win32")
    programs = tmp_path / "Programs"
    programs.mkdir()
    (programs / "卸载企业微信.lnk").write_bytes(b"x")
    (programs / "企业微信.lnk").write_bytes(b"x")
    good = tmp_path / "WXWork.exe"
    bad = tmp_path / "Uninstall.exe"
    good.write_text("x", encoding="utf-8")
    bad.write_text("x", encoding="utf-8")

    def _resolve(p):
        if "卸载" in p.stem:
            return bad
        if "企业微信" in p.stem:
            return good
        return None

    monkeypatch.setattr(open_mod, "_start_menu_roots", lambda: [programs])
    monkeypatch.setattr(open_mod, "_known_install_roots", lambda: [])
    monkeypatch.setattr(open_mod, "_resolve_shortcut", _resolve)
    monkeypatch.setattr(
        open_mod.subprocess,
        "run",
        lambda *a, **k: MagicMock(stdout="", returncode=1),
    )

    found = open_mod.find_app_candidates("企微", limit=3)
    assert found
    assert all("Uninstall" not in c["path"] for c in found)
    assert any("WXWork.exe" in c["path"] for c in found)


@pytest.mark.asyncio
async def test_open_confirm_speaks_without_assist_card():
    """open 确认：谈区开口，不广播 AssistConfirmCard（避免与 qi_line 重复）。"""
    from qi.core.brain import Brain

    brain = Brain({}, MagicMock())
    delivered: list[str] = []
    broadcasts: list[dict] = []

    async def fake_deliver(text, now, proactive=False):
        delivered.append(text)

    async def fake_broadcast(msg):
        broadcasts.append(msg)

    brain._deliver_qi_message = fake_deliver  # type: ignore[method-assign]
    brain.embodiment = MagicMock()
    brain.embodiment.broadcast = fake_broadcast

    msg = "以后都可以帮你开「qq」吗？我找到这些，回 1/2 或说开吧（默认 1）："
    await brain._deliver_action_result(
        {
            "type": "assist_confirm_request",
            "kind": "open",
            "target_path": "C:/QQ/QQ.exe",
            "summary": msg,
            "qi_line": msg,
            "speak": True,
            "outcome": "confirm_required",
            "needs_confirmation": True,
            "confirm_label": "好",
        },
        datetime(2026, 8, 15, 4, 55),
    )
    assert delivered == [msg]
    assert broadcasts == []

    # assist（非 open）仍广播确认卡
    delivered.clear()
    await brain._deliver_action_result(
        {
            "type": "assist_confirm_request",
            "target_path": "D:/a.txt",
            "summary": "要我看 a.txt 吗？",
            "qi_line": "要我看 a.txt 吗？",
            "speak": True,
            "outcome": "confirm_required",
            "needs_confirmation": True,
        },
        datetime(2026, 8, 15, 4, 56),
    )
    assert delivered == ["要我看 a.txt 吗？"]
    assert len(broadcasts) == 1
    assert broadcasts[0]["payload"]["type"] == "assist_confirm_request"
