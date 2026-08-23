"""L7 判断制 · 白话验收（任务包 §4，非口令）。

跑法：pytest tests/test_judgment_colloquial_acceptance.py -v
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.layer import ActionLayer
from qi.action.write import WriteAction, WriteRequest
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.storage.database import Database


class _FakeLLM:
    def __init__(self, text: str = "嗯。") -> None:
        self.text = text

    async def call(self, purpose, messages, temperature=None):
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


def _no_confirm(result: dict | None) -> None:
    assert result is not None
    assert result.get("needs_confirmation") is not True
    assert result.get("outcome") != "confirm_required"


@pytest.mark.asyncio
async def test_colloquial_delegate_search_no_confirm_card(tmp_path):
    """「帮我查一下量子纠缠入门资料」→ 接时真搜；不要求确认卡。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        from qi.action.explore_web import SearchHit

        web = MagicMock()
        web.search = AsyncMock(
            return_value=[
                SearchHit(
                    title="量子纠缠入门",
                    snippet="简介",
                    url="https://example.com/q",
                )
            ]
        )
        brain.action._build_explore_web = lambda: web  # type: ignore[method-assign]
        brain.llm = _FakeLLM("网上大概是这样。")  # type: ignore[assignment]

        delivered: list[dict] = []

        async def capture(result, now):
            delivered.append(result)

        with patch.object(brain, "_deliver_action_result", side_effect=capture):
            line = await brain.receive_user_message("帮我查一下量子纠缠入门资料")

        assert line is not None
        assert brain.pending_assist_confirmation is None
        assert delivered, "应有行动结果"
        _no_confirm(delivered[-1])
        assert delivered[-1].get("type") == "explore_drift"
        assert delivered[-1].get("found", {}).get("source") == "web_delegate"
        await brain._db.close()


@pytest.mark.asyncio
async def test_colloquial_hot_news_without_search_cue(tmp_path):
    """「今天热点新闻有什么」→ 问句形态 + LLM 判别 search，非话题词表。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        from qi.action.explore_web import SearchHit

        web = MagicMock()
        web.search = AsyncMock(
            return_value=[
                SearchHit(
                    title="今日要闻",
                    snippet="摘要",
                    url="https://example.com/n",
                )
            ]
        )
        brain.action._build_explore_web = lambda: web  # type: ignore[method-assign]

        class _IntentLLM:
            async def call(self, purpose, messages, temperature=None):
                user = str(messages[-1].get("content") or "")
                if "search" in user and "neither" in user:
                    return '{"intent":"search","query":"今天热点新闻"}'
                return "嗯。"

        brain.llm = _IntentLLM()  # type: ignore[assignment]

        delivered: list[dict] = []

        async def capture(result, now):
            delivered.append(result)

        with patch.object(brain, "_deliver_action_result", side_effect=capture):
            line = await brain.receive_user_message("今天热点新闻有什么")

        assert line is not None
        assert delivered, "应有 delegate 行动结果"
        assert delivered[-1].get("found", {}).get("source") == "web_delegate"
        await brain._db.close()


@pytest.mark.asyncio
async def test_colloquial_disk_capability_lists_without_confirm(tmp_path, monkeypatch):
    """「栖你能看到 d 盘下的文件吗？」→ 直接列目录；不要求确认卡。"""
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    (tmp_path / "hello.txt").write_text("x", encoding="utf-8")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp, stage="acquaintance")
        await brain._db.initialize()
        delivered: list[dict] = []

        async def capture(result, now):
            delivered.append(result)

        with patch.object(brain, "_deliver_action_result", side_effect=capture):
            line = await brain.receive_user_message("栖你能看到d盘下的文件吗？")

        assert line is not None
        assert brain.pending_assist_confirmation is None
        assert delivered
        _no_confirm(delivered[-1])
        assert delivered[-1].get("outcome") == "success"
        assert "hello" in (delivered[-1].get("qi_line") or "") or "能" in line
        await brain._db.close()


@pytest.mark.asyncio
async def test_colloquial_diary_write_without_confirm(tmp_path, monkeypatch):
    """「帮我把这段话记进今天日记」→ 判断后直接写；不要求确认卡。"""
    monkeypatch.setattr("qi.action.write.DEFAULT_ALLOWED_ROOT", tmp_path)
    diary_dir = tmp_path / "日记本"
    diary_dir.mkdir()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp, stage="friend")
        await brain._db.initialize()
        action = WriteAction(brain._db)
        await action.execute(
            WriteRequest(
                intent="allow",
                path=str(diary_dir),
                entry_kind="dir",
                role="diary",
            ),
            relationship_stage="friend",
            confirmed=True,
        )

        delivered: list[dict] = []

        async def capture(result, now):
            delivered.append(result)

        with patch.object(brain, "_deliver_action_result", side_effect=capture):
            line = await brain.receive_user_message(
                "帮我把这段话记进今天日记：今天我们聊了判断制。"
            )

        assert line is not None
        assert brain.pending_assist_confirmation is None
        if delivered:
            _no_confirm(delivered[-1])
        files = list(diary_dir.glob("日记-*.md"))
        assert files, "应已写入日记文件（内容由 LLM 起草，不验原文）"
        await brain._db.close()


@pytest.mark.asyncio
async def test_colloquial_irreversible_not_confirm_loop():
    """「帮我给某某发微信」→ 非 assist 读文件路径；不叠 L7 确认循环。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp)
        await brain._db.initialize()
        delivered: list[dict] = []

        async def capture(result, now):
            delivered.append(result)

        async def fake_heartbeat():
            brain._pending_queue.clear()

        brain._heartbeat = fake_heartbeat  # type: ignore[method-assign]

        with (
            patch.object(brain, "_deliver_action_result", side_effect=capture),
            patch("qi.core.brain.asyncio.sleep", new_callable=AsyncMock),
        ):
            line = await brain.receive_user_message("帮我给某某发微信")

        assert brain.pending_assist_confirmation is None
        for result in delivered:
            _no_confirm(result)
        assert not any(
            r.get("type") == "assist_confirm_request" for r in delivered
        )
        msgs = await brain._db.load_messages(limit=5)
        assert any(m.get("role") == "user" for m in msgs)
        await brain._db.close()


@pytest.mark.asyncio
async def test_colloquial_disk_defer_when_busy(tmp_path, monkeypatch):
    """忙时请人列 D 盘 → 延口语 + 入队，不弹确认卡。"""
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _brain(tmp, stage="acquaintance")
        await brain._db.initialize()
        brain._pending_queue.append("上一轮还没说完")

        line = await brain.receive_user_message("列一下 D 盘有什么")

        assert line is not None
        assert "稍等" in line or "弄完" in line
        assert brain.pending_assist_confirmation is None
        from qi.action.judgment import load_delegate_queue

        items = await load_delegate_queue(brain._db)
        assert items
        assert items[-1].get("kind") == "disk"
        await brain._db.close()
