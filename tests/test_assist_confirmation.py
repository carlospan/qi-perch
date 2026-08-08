"""assist-3：跨轮确认状态机。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from qi.action.layer import ActionLayer
from qi.action.volition import AssistRequest, parse_assist_request
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.core.gws import Contender
from qi.storage.database import Database


class _FakeLLM:
    def __init__(self, text: str = "看到了笔记里的字。") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        self.calls.append({"purpose": purpose, "messages": messages})
        return self.text


def _brain(tmp: str) -> Brain:
    db = Database(str(Path(tmp) / "qi.db"))
    brain = Brain(
        {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
        _FakeLLM(),  # type: ignore[arg-type]
    )
    brain._db = db
    brain.action = ActionLayer(db, {}, llm=_FakeLLM())
    brain.inner_life = None
    brain.first_times = None
    brain.memory = None
    brain.user_online = True
    brain.emotion = EmotionState(
        mode=ConsciousnessMode.AWAKE, curiosity=0.5, energy=0.7, valence=0.2
    )
    rel = MagicMock()
    rel.state.stage = "friend"
    rel.state.trust = 0.7
    brain.relationship = rel
    return brain


@pytest.mark.asyncio
async def test_b1_pending_stored_from_op_path(tmp_path):
    """B1：confirm_gate 后 pending 用 op/target_path 存住。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("hello", encoding="utf-8")
        brain.last_assist_request = parse_assist_request(f"帮我看一下 {f}")
        assert brain.last_assist_request is not None

        winner = Contender(kind="action:assist", salience=0.9, reason="t")
        with patch("qi.core.gws.arbitrate", return_value=winner), patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ), patch.object(
            brain, "_persist_action_budget", new_callable=AsyncMock
        ):
            await brain._heartbeat_gws_idle(
                want_express=False, now=datetime(2026, 8, 9, 12, 0)
            )
        assert brain.pending_assist_confirmation is not None
        assert str(f) in brain.pending_assist_confirmation.target_path.replace(
            "\\", "/"
        ) or brain.pending_assist_confirmation.target_path.endswith("note.txt")
        assert brain.last_assist_request is None
        await brain._db.close()


@pytest.mark.asyncio
async def test_b2_confirm_triggers_execute(tmp_path):
    """B2：用户「看吧」→ 直接 execute_kind(confirmed=True) 真读。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("今天很开心", encoding="utf-8")
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path=str(f)
        )
        brain.pending_assist_confirmation_at = datetime.now()
        brain.pending_assist_heartbeats = 0

        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            line = await brain.receive_user_message("看吧")
        assert brain.pending_assist_confirmation is None
        assert line is not None
        assert "开心" in line or "看" in line
        await brain._db.close()


@pytest.mark.asyncio
async def test_b3_new_request_not_treated_as_confirm(tmp_path):
    """B3：pending 时「帮我看 Y」不当确认。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        x = tmp_path / "x.txt"
        x.write_text("x", encoding="utf-8")
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path=str(x)
        )
        brain.pending_assist_confirmation_at = datetime.now()

        async def fake_heartbeat() -> str | None:
            return None

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        # 用无空格绝对路径，避免 Windows temp 路径空格打断正则
        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("帮我看一下 D:/notes/y.txt")
        assert brain.pending_assist_confirmation is None
        assert brain.last_assist_request is not None
        assert brain.last_assist_request.target_path == "D:/notes/y.txt"
        await brain._db.close()


@pytest.mark.asyncio
async def test_user_reject_clears_pending(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path=str(tmp_path / "a.txt")
        )
        brain.pending_assist_confirmation_at = datetime.now()
        with patch.object(
            brain, "_deliver_qi_message", new_callable=AsyncMock
        ) as deliver:
            out = await brain.receive_user_message("不用")
        assert out == "好。"
        assert brain.pending_assist_confirmation is None
        deliver.assert_awaited()
        await brain._db.close()


@pytest.mark.asyncio
async def test_user_off_topic_clears_pending(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path=str(tmp_path / "a.txt")
        )
        brain.pending_assist_confirmation_at = datetime.now()

        async def fake_heartbeat() -> str | None:
            return None

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("今天天气真好")
        assert brain.pending_assist_confirmation is None
        await brain._db.close()


@pytest.mark.asyncio
async def test_pending_timeout_five_minutes(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.action = None
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path="D:/x.txt"
        )
        brain.pending_assist_confirmation_at = datetime.now() - timedelta(
            minutes=6
        )
        brain.pending_assist_heartbeats = 0
        await brain._heartbeat()
        assert brain.pending_assist_confirmation is None
        await brain._db.close()


@pytest.mark.asyncio
async def test_pending_timeout_three_heartbeats(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.action = None
        brain.pending_assist_confirmation = AssistRequest(
            op="read_file", target_path="D:/x.txt"
        )
        brain.pending_assist_confirmation_at = datetime.now()
        brain.pending_assist_heartbeats = 0
        await brain._heartbeat()
        assert brain.pending_assist_confirmation is not None
        await brain._heartbeat()
        assert brain.pending_assist_confirmation is not None
        await brain._heartbeat()
        assert brain.pending_assist_confirmation is None
        await brain._db.close()


def test_confirm_cue_excludes_bare_kan():
    brain = Brain({}, MagicMock())
    assert brain._is_confirm_cue("看吧") is True
    assert brain._is_confirm_cue("好") is True
    assert brain._is_confirm_cue("看") is False
    assert brain._is_confirm_cue("帮我看一下 D:/a.txt") is False


def test_reject_before_confirm_on_buyao_kan():
    """「不用看」先判拒绝；notes 路径不误伤。"""
    brain = Brain({}, MagicMock())
    assert brain._is_reject_cue("不用看") is True
    assert brain._is_reject_cue("no") is True
    assert brain._is_reject_cue("帮我看一下 D:/notes/y.txt") is False


@pytest.mark.asyncio
async def test_confirmed_assist_reads_file(tmp_path):
    """confirmed=True 真读 + digest。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "diary.md"
        f.write_text("一段心事", encoding="utf-8")
        result = await brain._execute_confirmed_assist(
            AssistRequest(op="read_file", target_path=str(f))
        )
        assert result is not None
        assert result.get("outcome") == "success"
        assert result.get("speak") is True
        await brain._db.close()
