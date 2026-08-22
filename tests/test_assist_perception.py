"""assist-2：感知层路径提取 + 触发链。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.layer import ActionLayer
from qi.action.volition import parse_assist_request
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.core.gws import Contender
from qi.core.trace import collect_contenders
from qi.storage.database import Database


class _FakeLLM:
    def __init__(self, text: str = "看了。") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        self.calls.append({"purpose": purpose, "messages": messages})
        return self.text


class TestParseAssistRequest:
    def test_windows_absolute_path(self):
        r = parse_assist_request("帮我看一下 D:/notes/today.txt")
        assert r is not None
        assert r.op == "read_file"
        assert "notes/today.txt" in r.target_path

    def test_windows_backslash_path(self):
        r = parse_assist_request("读一下 D:\\diary\\today.md")
        assert r is not None
        assert r.target_path == "D:/diary/today.md"

    def test_posix_absolute_path(self):
        r = parse_assist_request("帮我看 /tmp/log.txt")
        assert r is not None
        assert r.target_path == "/tmp/log.txt"

    def test_home_path(self):
        r = parse_assist_request("帮我读 ~/diary.md")
        assert r is not None
        assert r.target_path == "~/diary.md"

    def test_relative_path_with_ext(self):
        r = parse_assist_request("看下 note.txt")
        assert r is not None
        assert r.target_path == "note.txt"

    def test_relative_md_not_bare_ext(self):
        """B2：note.md 整段捕获，不是裸 .md。"""
        r = parse_assist_request("看下 note.md")
        assert r is not None
        assert r.target_path == "note.md"

    def test_no_path_returns_none(self):
        r = parse_assist_request("帮我看看这段")
        assert r is None

    def test_no_op_cue_returns_none(self):
        r = parse_assist_request("D:/notes/today.txt 很有意思")
        assert r is None

    def test_empty_message(self):
        assert parse_assist_request("") is None
        assert parse_assist_request(None) is None

    def test_path_with_trailing_punctuation(self):
        r = parse_assist_request("帮我看一下 D:/notes/today.txt。")
        assert r is not None
        assert "。" not in r.target_path


def _brain_for_assist(tmp: str) -> Brain:
    from qi.core.emotion import ConsciousnessMode

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
    # relationship_stage 是只读属性，挂 stub
    rel = MagicMock()
    rel.state.stage = "friend"
    rel.state.trust = 0.7
    rel.state.season = "spring"
    brain.relationship = rel
    return brain


class TestBrainAssistRequestStorage:
    @pytest.mark.asyncio
    async def test_receive_user_message_stores_assist_request(self):
        """assist-4：判断制直触发后消费 last_assist_request；不挂 assist pending。"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            brain = _brain_for_assist(tmp)
            await brain._db.initialize()

            with (
                patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock),
                patch.object(
                    brain, "_deliver_action_result", new_callable=AsyncMock
                ),
            ):
                await brain.receive_user_message("帮我看一下 D:/test.txt")
            assert brain.last_user_message == "帮我看一下 D:/test.txt"
            assert brain.last_assist_request is None
            assert brain.pending_assist_confirmation is None
            assert brain.last_assist_target is not None
            assert "test.txt" in brain.last_assist_target
            await brain._db.close()

    @pytest.mark.asyncio
    async def test_receive_user_message_no_path_stores_none(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            brain = _brain_for_assist(tmp)
            await brain._db.initialize()

            async def fake_heartbeat() -> str | None:
                return None

            brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
            with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
                await brain.receive_user_message("今天天气真好")
            assert brain.last_user_message == "今天天气真好"
            assert brain.last_assist_request is None
            await brain._db.close()


class TestTracePassesUserMessage:
    @pytest.mark.asyncio
    async def test_collect_contenders_passes_user_message(self):
        """B1：trace 传真实 user_message → assist 进 GWS candidates。"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            brain = _brain_for_assist(tmp)
            await brain._db.initialize()
            brain.last_user_message = "帮我看一下 D:/test.txt"
            now = datetime(2026, 8, 9, 12, 0)
            contenders = await collect_contenders(
                brain,
                pending=None,
                want_express=False,
                kind=None,
                action_type=None,
                now=now,
            )
            kinds = [c.kind for c in contenders]
            assert "action:assist" in kinds
            await brain._db.close()


class TestAssistRequestConsumed:
    @pytest.mark.asyncio
    async def test_assist_request_consumed_after_gws_execute(self, tmp_path):
        """B3：GWS 分发 assist 后清空 last_assist_request。"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            brain = _brain_for_assist(tmp)
            await brain._db.initialize()
            f = tmp_path / "note.txt"
            f.write_text("x", encoding="utf-8")
            brain.last_user_message = f"帮我看一下 {f}"
            brain.last_assist_request = parse_assist_request(
                brain.last_user_message
            )
            assert brain.last_assist_request is not None

            winner = Contender(
                kind="action:assist",
                salience=0.9,
                reason="test",
            )
            with patch(
                "qi.core.gws.arbitrate", return_value=winner
            ), patch.object(
                brain, "_deliver_action_result", new_callable=AsyncMock
            ), patch.object(
                brain, "_persist_action_budget", new_callable=AsyncMock
            ):
                await brain._heartbeat_gws_idle(
                    want_express=False, now=datetime(2026, 8, 9, 12, 0)
                )
            assert brain.last_assist_request is None
            await brain._db.close()
