"""assist-4：对话拍触发 execute_kind(assist)，不进 pending_queue。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.layer import ActionLayer
from qi.action.permission import OUTCOME_FAILED_CAPABILITY
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database


class _FakeLLM:
    def __init__(self, text: str = "嗯。") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        self.calls.append({"purpose": purpose, "messages": messages})
        return self.text


def _brain(tmp: str, *, stage: str = "friend") -> Brain:
    db = Database(str(Path(tmp) / "qi.db"))
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
        mode=ConsciousnessMode.AWAKE, curiosity=0.5, energy=0.7, valence=0.2
    )
    rel = MagicMock()
    rel.state.stage = stage
    rel.state.trust = 0.7
    brain.relationship = rel
    return brain


@pytest.mark.asyncio
async def test_receive_user_message_with_assist_request_triggers_execute_kind(
    tmp_path,
):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("hello", encoding="utf-8")

        with (
            patch.object(
                brain.action, "execute_kind", wraps=brain.action.execute_kind
            ) as ek,
            patch.object(
                brain, "_deliver_action_result", new_callable=AsyncMock
            ),
            patch.object(brain, "_heartbeat", new_callable=AsyncMock) as hb,
        ):
            line = await brain.receive_user_message(f"帮我看一下 {f}")

        ek.assert_awaited()
        assert ek.await_args.args[0] == "assist"
        assert ek.await_args.kwargs.get("confirmed") is False
        assert line is not None
        assert "看" in line
        assert len(brain._pending_queue) == 0
        hb.assert_not_awaited()
        await brain._db.close()


@pytest.mark.asyncio
async def test_receive_user_message_normal_message_unchanged():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        seen: list[str] = []

        async def fake_heartbeat() -> None:
            # 正常路径：入队后再心跳
            assert len(brain._pending_queue) == 1
            seen.append(brain._pending_queue[0])
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("你好")

        assert seen == ["你好"]
        assert brain.last_user_message == "你好"
        assert brain.last_assist_request is None
        assert brain.pending_assist_confirmation is None
        await brain._db.close()


@pytest.mark.asyncio
async def test_assist_request_stranger_fails(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp, stage="stranger")
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("secret", encoding="utf-8")

        with patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ) as deliver:
            line = await brain.receive_user_message(f"帮我看一下 {f}")

        assert line is not None
        assert "熟一点" in line
        deliver.assert_awaited()
        result = deliver.await_args.args[0]
        assert result.get("outcome") == OUTCOME_FAILED_CAPABILITY
        assert result.get("needs_confirmation") is not True
        assert brain.pending_assist_confirmation is None
        assert len(brain._pending_queue) == 0
        await brain._db.close()


@pytest.mark.asyncio
async def test_assist_request_friend_confirm_gate_stores_pending(tmp_path):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp, stage="friend")
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("hello", encoding="utf-8")

        with patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ):
            line = await brain.receive_user_message(f"帮我看一下 {f}")

        assert line is not None
        assert "说一声我就看" in line or "要我看" in line
        assert brain.pending_assist_confirmation is not None
        assert brain.pending_assist_confirmation.op == "read_file"
        path = brain.pending_assist_confirmation.target_path.replace("\\", "/")
        assert str(f).replace("\\", "/") in path or path.endswith("note.txt")
        assert brain.last_assist_request is None
        assert len(brain._pending_queue) == 0
        await brain._db.close()
