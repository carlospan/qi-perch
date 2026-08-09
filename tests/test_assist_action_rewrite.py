"""assist-5：assist.execute 留痕（成功 / failed_capability；confirm_gate 不写）。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from qi.action.assist import AssistAction
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS


class _FakeLLM:
    def __init__(self, text: str = "看到了笔记。") -> None:
        self.text = text

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        return self.text


@pytest.mark.asyncio
async def test_assist_success_inserts_action(db, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("今天天气不错", encoding="utf-8")
    assist = AssistAction(db, llm=_FakeLLM())
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 12, 0),
    )
    assert result["outcome"] == OUTCOME_SUCCESS
    assert result.get("action_id") is not None
    rows = await db.list_recent_actions(limit=5)
    assist_rows = [r for r in rows if r.get("kind") == "assist"]
    assert len(assist_rows) >= 1
    row = assist_rows[0]
    assert row["outcome"] == OUTCOME_SUCCESS
    detail = json.loads(row["detail_json"] or "{}")
    assert "note.txt" in detail.get("target_path", "").replace("\\", "/")


@pytest.mark.asyncio
async def test_assist_fail_inserts_action(db, tmp_path):
    assist = AssistAction(db, llm=_FakeLLM("不该"))
    result = await assist.execute(
        "read_file",
        str(tmp_path / "nope.txt"),
        relationship_stage="friend",
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 12, 0),
    )
    assert result["outcome"] == OUTCOME_FAILED_CAPABILITY
    rows = await db.list_recent_actions(limit=5)
    assist_rows = [r for r in rows if r.get("kind") == "assist"]
    assert len(assist_rows) >= 1
    assert assist_rows[0]["outcome"] == OUTCOME_FAILED_CAPABILITY


@pytest.mark.asyncio
async def test_assist_confirm_gate_no_action(db, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("secret", encoding="utf-8")
    before = await db.list_recent_actions(limit=20)
    before_n = sum(1 for r in before if r.get("kind") == "assist")
    assist = AssistAction(db, llm=_FakeLLM("不该走到这"))
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=False,
        season="spring",
        now=datetime(2026, 8, 9, 12, 0),
    )
    assert result["outcome"] == "confirm_required"
    after = await db.list_recent_actions(limit=20)
    after_n = sum(1 for r in after if r.get("kind") == "assist")
    assert after_n == before_n
