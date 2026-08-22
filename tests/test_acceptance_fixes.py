"""验收问题回归：用户落库、不可逆、disk 口语、列目录防抖。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.disk import detect_disk_intent, looks_like_disk_intent
from qi.action.irreversible import looks_like_irreversible_request
from qi.action.layer import ActionLayer
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database


class _FakeLLM:
    async def call(self, purpose, messages, temperature=None):
        return "嗯。"


def _brain(tmp: str, *, stage: str = "bonded") -> Brain:
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
    rel.state.stage = stage
    rel.state.trust = 1.0
    rel.state.season = "spring"
    brain.relationship = rel
    return brain


@pytest.mark.parametrize(
    "text",
    [
        "帮我看下 D 盘有啥",
        "看看 D 盘有什么",
    ],
)
def test_disk_colloquial_you_sha(text: str):
    assert looks_like_disk_intent(text)


@pytest.mark.asyncio
async def test_disk_detect_you_sha(tmp_path, monkeypatch):
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    req = await detect_disk_intent("帮我看下 D 盘有啥", llm=None)
    assert req is not None
    assert req.intent in ("list_dir", "offer_list")


@pytest.mark.parametrize(
    "text",
    [
        "帮我给某某发微信",
        "帮小明发一条短信",
        "转账 100 块",
    ],
)
def test_irreversible_detects(text: str):
    assert looks_like_irreversible_request(text)


@pytest.mark.asyncio
async def test_irreversible_honest_line():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        delivered: list[str] = []

        async def capture(line, now, proactive=False):
            delivered.append(line)

        brain._deliver_qi_message = capture  # type: ignore[method-assign]

        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            line = await brain.receive_user_message("帮我给某某发微信")

        assert line is not None
        assert "做不到" in line or "发微信" in line
        assert delivered
        msgs = await brain._db.load_messages(limit=5)
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        assert user_msgs and "发微信" in user_msgs[-1].get("content", "")
        actions = await brain._db.list_recent_actions(limit=5)
        assert any(a.get("kind") == "irreversible" for a in actions)
        await brain._db.close()


@pytest.mark.asyncio
async def test_l7_disk_saves_user_message(tmp_path, monkeypatch):
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()

        async def noop_deliver(result, now):
            pass

        brain._deliver_action_result = noop_deliver  # type: ignore[method-assign]

        with patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock):
            await brain.receive_user_message("列一下 D 盘有什么")

        msgs = await brain._db.load_messages(limit=10)
        assert any(
            m.get("role") == "user" and "D 盘" in m.get("content", "") for m in msgs
        )
        await brain._db.close()


@pytest.mark.asyncio
async def test_disk_list_debounce(tmp_path, monkeypatch):
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    from datetime import datetime

    from qi.action.disk import DiskAction, DiskRequest

    db = Database(str(tmp_path / "qi.db"))
    await db.initialize()
    action = DiskAction(db)
    req = DiskRequest(intent="list_dir", path=str(tmp_path))
    now = datetime.now()
    r1 = await action.execute(req, relationship_stage="bonded", confirmed=True, now=now)
    r2 = await action.execute(req, relationship_stage="bonded", confirmed=True, now=now)
    assert r1.get("intent") == "list_dir"
    assert r2.get("summary") == "list_debounce"
    await db.close()
