"""任务包 C：fake-provider 契约——拔管后四条线仍推进，主动开口有本地兜底。"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from qi.core.brain import Brain
from qi.core.proactive import KIND_EXPRESS_FEELING
from qi.llm.gateway import LLMCallOutcome, LLMGateway
from qi.memory.manager import MemoryManager
from qi.relationship.engine import RelationshipEngine
from qi.storage.database import Database

_USER_LINE = "我最近在学吉他，谢谢你陪我，我很开心"


class FakeLLM:
    """实现 call / call_detailed / last_outcome；不走真实重试与 sleep。"""

    def __init__(self, mode: str = "ok", fixed: str = "嗯。"):
        self.mode = mode  # ok | unreachable | empty
        self.fixed = fixed
        self.last_outcome = LLMCallOutcome(text="", failure=None)
        self.calls: list[str] = []

    async def call(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> str:
        outcome = await self.call_detailed(purpose, messages, temperature)
        return outcome.text

    async def call_detailed(
        self,
        purpose: str,
        messages: list[dict],
        temperature: float | None = None,
    ) -> LLMCallOutcome:
        self.calls.append(purpose)
        if self.mode == "ok":
            outcome = LLMCallOutcome(text=self.fixed, failure=None)
        elif self.mode == "unreachable":
            outcome = LLMCallOutcome(text="", failure="unreachable")
        else:
            outcome = LLMCallOutcome(text="", failure="empty")
        if purpose == "conversation":
            self.last_outcome = outcome
        return outcome


def _temp_config(tmp: str) -> dict:
    return {
        "memory": {
            "max_working_memory": 20,
            "chroma_path": str(Path(tmp) / "chroma"),
        },
        "emotion": {"expression_threshold": 0.3},
    }


async def _wire_brain(tmp: str, llm: FakeLLM) -> tuple[Brain, Database]:
    db = Database(str(Path(tmp) / "qi.db"))
    await db.initialize()
    config = _temp_config(tmp)
    brain = Brain(config, llm)  # type: ignore[arg-type]
    brain._db = db
    brain.memory = MemoryManager(db, config, llm=llm)  # type: ignore[arg-type]
    await brain.memory.restore()
    brain.relationship = RelationshipEngine(db, llm, config)  # type: ignore[arg-type]
    await brain.relationship.restore()
    brain.relationship.state.stage = "friend"
    brain.action = None
    brain.inner_life = None
    brain.first_times = None
    return brain, db


async def _cleanup(brain: Brain, db: Database) -> None:
    if brain.memory is not None:
        brain.memory.vector_store.close()
    await db.close()
    gc.collect()


@pytest.mark.asyncio
async def test_fixed_return_advances_four_lines():
    """LLM 正常：用户句后情绪/记忆/关系推进，并开口。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        llm = FakeLLM(mode="ok", fixed="……好。")
        brain, db = await _wire_brain(tmp, llm)
        before = brain.emotion.model_copy(deep=True)
        depth_before = brain.relationship.state.depth

        brain._pending_queue.append(_USER_LINE)
        await brain._heartbeat()

        assert brain._pending_speech is not None
        assert brain._pending_speech.text == "……好。"
        assert brain._pending_speech.proactive is False
        assert brain.emotion.valence != before.valence or brain.emotion.security != before.security
        recent = await db.load_recent_messages(limit=5)
        assert any(m.get("content") == _USER_LINE for m in recent)
        assert brain.relationship.state.depth >= depth_before
        assert llm.last_outcome.failure is None
        await _cleanup(brain, db)


@pytest.mark.asyncio
async def test_unreachable_dialogue_template_but_organs_advance():
    """对话 UNREACHABLE：模板开口（包 4 契约），情绪/记忆/关系仍推进。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        llm = FakeLLM(mode="unreachable")
        brain, db = await _wire_brain(tmp, llm)
        before = brain.emotion.model_copy(deep=True)
        depth_before = brain.relationship.state.depth

        brain._pending_queue.append(_USER_LINE)
        await brain._heartbeat()

        assert brain._pending_speech is not None
        assert brain._pending_speech.text
        assert llm.last_outcome.failure == "unreachable"
        intent = await db.get_body_memory("last_intention")
        assert intent and intent.get("outcome") == "template"
        assert brain.emotion.valence != before.valence or brain.emotion.security != before.security
        recent = await db.load_recent_messages(limit=5)
        assert any(m.get("content") == _USER_LINE for m in recent)
        assert brain.relationship.state.depth >= depth_before
        working = [m.content for m in brain.memory.working.get_messages()]  # type: ignore[union-attr]
        assert _USER_LINE in working
        await _cleanup(brain, db)


@pytest.mark.asyncio
async def test_unreachable_proactive_template_and_records():
    """主动 UNREACHABLE：意向卡模板开口，且计入日限。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        llm = FakeLLM(mode="unreachable")
        brain, db = await _wire_brain(tmp, llm)
        brain._accumulated_suppressed = 1.01
        brain._prev_valence = brain.emotion.valence
        brain.user_online = True
        assert brain.proactive.count_today == 0

        await brain._heartbeat()

        assert brain._pending_speech is not None
        assert brain._pending_speech.proactive is True
        assert brain._pending_speech.text
        intent = await db.get_body_memory("last_intention")
        assert intent and intent.get("outcome") == "template"
        assert brain.proactive.count_today == 1
        assert KIND_EXPRESS_FEELING in brain.proactive.last_at
        await _cleanup(brain, db)


@pytest.mark.asyncio
async def test_empty_proactive_template_and_records():
    """主动 EMPTY：同样模板开口并计入日限（废止 EMPTY 不 record）。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        llm = FakeLLM(mode="empty")
        brain, db = await _wire_brain(tmp, llm)
        brain._accumulated_suppressed = 1.01
        brain._prev_valence = brain.emotion.valence
        brain.user_online = True

        await brain._heartbeat()

        assert brain._pending_speech is not None
        assert brain._pending_speech.proactive is True
        assert llm.last_outcome.failure == "empty"
        intent = await db.get_body_memory("last_intention")
        assert intent and intent.get("outcome") == "template"
        assert brain.proactive.count_today == 1
        await _cleanup(brain, db)


@pytest.mark.asyncio
async def test_gateway_unreachable_mocked_without_retry_wait():
    """真 gateway + mock 抛异常：标 unreachable，不真等退避。"""
    gw = LLMGateway(
        {
            "llm": {
                "default_provider": "fake",
                "providers": {
                    "fake": {
                        "base_url": "http://127.0.0.1:9",
                        "api_key": "test-key",
                        "models": {"fast": "m"},
                    }
                },
                "model_routing": {"conversation": "fake:fast"},
            }
        }
    )

    async def boom(**_kwargs):
        raise TimeoutError("offline")

    gw.providers["fake"].chat = boom  # type: ignore[method-assign]
    with patch("qi.llm.gateway.asyncio.sleep", new_callable=AsyncMock) as sleep:
        text = await gw.call(
            "conversation", [{"role": "user", "content": "hi"}]
        )
    assert text == ""
    assert gw.last_outcome.failure == "unreachable"
    assert sleep.await_count == 2


@pytest.mark.asyncio
async def test_gateway_empty_and_last_outcome_conversation_only():
    """EMPTY 不重试；非 conversation 不覆盖 last_outcome。"""
    gw = LLMGateway(
        {
            "llm": {
                "default_provider": "fake",
                "providers": {
                    "fake": {
                        "base_url": "http://127.0.0.1:9",
                        "api_key": "test-key",
                        "models": {"fast": "m"},
                    }
                },
                "model_routing": {
                    "conversation": "fake:fast",
                    "narrative": "fake:fast",
                },
            }
        }
    )
    assert gw.last_outcome.failure is None

    async def say_ok(**_kwargs):
        return "好。"

    gw.providers["fake"].chat = say_ok  # type: ignore[method-assign]
    await gw.call("conversation", [{"role": "user", "content": "a"}])
    assert gw.last_outcome.failure is None
    assert gw.last_outcome.text == "好。"

    async def blank(**_kwargs):
        return "   "

    gw.providers["fake"].chat = blank  # type: ignore[method-assign]
    with patch("qi.llm.gateway.asyncio.sleep", new_callable=AsyncMock) as sleep:
        text = await gw.call("narrative", [{"role": "user", "content": "b"}])
    assert text == ""
    assert sleep.await_count == 0
    # narrative EMPTY 不得盖掉对话成功态
    assert gw.last_outcome.failure is None
    assert gw.last_outcome.text == "好。"

    text2 = await gw.call("conversation", [{"role": "user", "content": "c"}])
    assert text2 == ""
    assert gw.last_outcome.failure == "empty"


def test_gateway_last_outcome_starts_success():
    gw = LLMGateway({"llm": {"providers": {}}})
    assert gw.last_outcome.failure is None


def test_fallback_line_contract_smoke():
    from qi.core.proactive import ProactiveGate

    gate = ProactiveGate({})
    for kind in (KIND_EXPRESS_FEELING, "check_in", "reach_out"):
        line = gate.fallback_line(kind)
        assert line
        assert "您" not in line
        assert "AI" not in line.upper()
        assert "心跳" not in line and "呼吸" not in line
