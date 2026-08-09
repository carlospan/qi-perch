"""assist-4/5：对话拍触发 + 粘性补执行。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
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
    rel.state.season = "spring"
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


@pytest.mark.asyncio
async def test_confirm_after_pending_consumed_re_executes(tmp_path):
    """B1：夹杂追问后「好你读吧」仍用粘性 target 补执行。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("我爱栖", encoding="utf-8")
        path = str(f)

        with patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ):
            await brain.receive_user_message(f"帮我看一下 {path}")
        assert brain.pending_assist_confirmation is not None
        assert brain.last_assist_target is not None

        with patch.object(
            brain, "_deliver_action_result", new_callable=AsyncMock
        ):
            await brain.receive_user_message("看吧")
        assert brain.pending_assist_confirmation is None
        assert brain.last_assist_target is not None

        async def fake_heartbeat() -> None:
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("啊？你看到了什么")
        assert brain.last_user_message == "啊？你看到了什么"
        assert brain.last_assist_target is not None

        with (
            patch.object(
                brain,
                "_execute_assist_on_request",
                wraps=brain._execute_assist_on_request,
            ) as ex,
            patch.object(
                brain, "_deliver_action_result", new_callable=AsyncMock
            ),
        ):
            line = await brain.receive_user_message("好你读吧")

        ex.assert_awaited()
        assert ex.await_args.kwargs.get("confirmed_override") is True
        assert line is not None
        assert brain.last_assist_target is None
        await brain._db.close()


@pytest.mark.asyncio
async def test_confirm_after_pending_consumed_stale_target_guides(tmp_path):
    """B3：stale target → 引导；target=None 不进 3c。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.last_assist_target = str(tmp_path / "x.txt")
        brain.last_assist_target_at = datetime.now() - timedelta(minutes=6)

        with patch.object(
            brain, "_deliver_qi_message", new_callable=AsyncMock
        ) as deliver:
            line = await brain.receive_user_message("好你读吧")
        assert line == "嗯？你想让我看什么？"
        deliver.assert_awaited()
        assert "嗯？你想让我看什么？" in deliver.await_args.args[0]

        brain.last_assist_target = None
        brain.last_assist_target_at = None

        async def fake_heartbeat() -> None:
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with (
            patch.object(
                brain, "_deliver_qi_message", new_callable=AsyncMock
            ) as deliver2,
            patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock),
        ):
            await brain.receive_user_message("好你读吧")
        for c in deliver2.await_args_list:
            assert "嗯？你想让我看什么？" not in str(c.args[0])
        await brain._db.close()


@pytest.mark.asyncio
async def test_bare_confirm_cue_no_hijack():
    """B2：无 assist 上下文时裸「好」「嗯」走正常对话。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        seen: list[str] = []

        async def fake_heartbeat() -> None:
            if brain._pending_queue:
                seen.append(brain._pending_queue[0])
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("好")
            await brain.receive_user_message("嗯")
        assert seen == ["好", "嗯"]
        await brain._db.close()


@pytest.mark.asyncio
async def test_confirm_reexec_cue_phrase_only(tmp_path):
    """B2：裸「好」不补执行；「好你读吧」补执行。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        f = tmp_path / "note.txt"
        f.write_text("x", encoding="utf-8")
        brain.last_assist_target = str(f)
        brain.last_assist_target_at = datetime.now()

        async def fake_heartbeat() -> None:
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with (
            patch.object(
                brain, "_execute_assist_on_request", new_callable=AsyncMock
            ) as ex,
            patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock),
        ):
            await brain.receive_user_message("好")
        ex.assert_not_awaited()
        assert brain.last_assist_target is not None

        with (
            patch.object(
                brain,
                "_execute_assist_on_request",
                wraps=brain._execute_assist_on_request,
            ) as ex2,
            patch.object(
                brain, "_deliver_action_result", new_callable=AsyncMock
            ),
        ):
            await brain.receive_user_message("好你读吧")
        ex2.assert_awaited()
        assert ex2.await_args.kwargs.get("confirmed_override") is True
        await brain._db.close()


@pytest.mark.asyncio
async def test_non_reexec_with_target_not_shortcircuited():
    """B2/B3：有 target 但非窄词 → 不引导、不短路。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        brain.last_assist_target = "D:/x.txt"
        brain.last_assist_target_at = datetime.now()
        seen: list[str] = []

        async def fake_heartbeat() -> None:
            if brain._pending_queue:
                seen.append(brain._pending_queue[0])
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]
        with (
            patch.object(
                brain, "_deliver_qi_message", new_callable=AsyncMock
            ) as deliver,
            patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock),
        ):
            await brain.receive_user_message("嗯嗯")
        assert seen == ["嗯嗯"]
        for c in deliver.await_args_list:
            assert "嗯？你想让我看什么？" not in str(c.args[0])
        assert brain.last_assist_target == "D:/x.txt"
        await brain._db.close()


@pytest.mark.asyncio
async def test_assist_target_expires():
    brain = Brain({"tts": {"enabled": False}}, _FakeLLM())  # type: ignore[arg-type]
    brain.last_assist_target = "D:/x.txt"
    brain.last_assist_target_at = datetime.now() - timedelta(minutes=6)
    assert brain._assist_target_fresh(datetime.now()) is False
    brain.last_assist_target_at = datetime.now()
    assert brain._assist_target_fresh(datetime.now()) is True
