"""assist-1：读用户文件 + 确认门 + LLM 复述。"""

from __future__ import annotations

from datetime import datetime

import pytest
from qi.action.assist import AssistAction
from qi.action.layer import ActionLayer
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS
from qi.core.emotion import EmotionState


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        self.calls.append(
            {
                "purpose": purpose,
                "messages": messages,
                "temperature": temperature,
            }
        )
        return self.text


@pytest.mark.asyncio
async def test_assist_read_file_success(db, tmp_path):
    """friend+ 已确认 → 读文件 → digest → success。"""
    f = tmp_path / "note.txt"
    f.write_text("今天天气不错", encoding="utf-8")
    assist = AssistAction(db, llm=_FakeLLM("看到了今天的天气记一笔。"))
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert result["outcome"] == OUTCOME_SUCCESS
    assert result["speak"] is True
    assert "天气" in result["qi_line"]


@pytest.mark.asyncio
async def test_assist_not_confirmed_returns_confirm_gate(db, tmp_path):
    """friend+ 未确认 → confirm_gate，不执行。"""
    f = tmp_path / "note.txt"
    f.write_text("secret", encoding="utf-8")
    assist = AssistAction(db, llm=_FakeLLM("不该走到这"))
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=False,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert result["outcome"] == "confirm_required"
    assert "说一声" in result["qi_line"]
    assert result.get("needs_confirmation") is True


@pytest.mark.asyncio
async def test_assist_stranger_not_allowed(db, tmp_path):
    """stranger → 不允许，failed_capability。"""
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    assist = AssistAction(db, llm=_FakeLLM("不该"))
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="stranger",
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert result["outcome"] == OUTCOME_FAILED_CAPABILITY
    assert "熟一点" in result["qi_line"]


@pytest.mark.asyncio
async def test_assist_file_not_found(db, tmp_path):
    """文件不存在 → failed_capability。"""
    assist = AssistAction(db, llm=_FakeLLM("不该"))
    result = await assist.execute(
        "read_file",
        str(tmp_path / "nope.txt"),
        relationship_stage="friend",
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert result["outcome"] == OUTCOME_FAILED_CAPABILITY
    assert "没找到" in result["qi_line"]


@pytest.mark.asyncio
async def test_assist_scar_blocks(db, tmp_path):
    """assist 伤疤 → 不允许。"""
    await db.save_scar(
        origin_event="[action:assist] 之前越界了",
        severity=0.7,
        trust_before=0.7,
    )
    scars = await db.list_scars()
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    assist = AssistAction(db, llm=_FakeLLM("不该"))
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        scars=scars,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert result["outcome"] == OUTCOME_FAILED_CAPABILITY


@pytest.mark.asyncio
async def test_assist_digest_uses_llm(db, tmp_path):
    """digest 走 LLM consciousness。"""
    f = tmp_path / "note.txt"
    f.write_text("今天很开心", encoding="utf-8")
    llm = _FakeLLM("看到了你今天的开心。")
    assist = AssistAction(db, llm=llm)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    # R5 / B1 定案 a：短文件仅 1 次块 digest（无合并 LLM）
    assert len(llm.calls) == 1
    assert llm.calls[0]["purpose"] == "consciousness"
    assert result["qi_line"] == "看到了你今天的开心。"


@pytest.mark.asyncio
async def test_assist_digest_no_llm_fallback(db, tmp_path):
    """无 llm → 降级只说文件名。"""
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    assist = AssistAction(db, llm=None)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9),
    )
    assert "note.txt" in result["qi_line"]


@pytest.mark.asyncio
async def test_execute_kind_assist_not_record_budget(db, tmp_path):
    """execute_kind 走 assist 不调 budget.record。"""
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    layer = ActionLayer(
        db,
        {"action": {"autonomous_daily_limit": 20}},
        llm=_FakeLLM("看了。"),
    )
    before = layer.budget.count_today
    await layer.execute_kind(
        "assist",
        EmotionState(curiosity=0.5),
        "friend",
        "spring",
        datetime(2026, 8, 9),
        mode="solitary",
        op="read_file",
        target_path=str(f),
        confirmed=True,
    )
    assert layer.budget.count_today == before


@pytest.mark.asyncio
async def test_execute_kind_assist_in_awake_mode(db, tmp_path):
    """B1：awake 对话期 assist 仍可执行（不被 awake 门控堵）。"""
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    layer = ActionLayer(
        db,
        {"action": {"autonomous_daily_limit": 20}},
        llm=_FakeLLM("看了。"),
    )
    result = await layer.execute_kind(
        "assist",
        EmotionState(curiosity=0.5),
        "friend",
        "spring",
        datetime(2026, 8, 9),
        mode="awake",
        op="read_file",
        target_path=str(f),
        confirmed=True,
    )
    assert result is not None
    assert result["outcome"] == OUTCOME_SUCCESS


@pytest.mark.asyncio
async def test_execute_kind_assist_skips_budget_limit(db, tmp_path):
    """B2：自主日限满时 assist 仍执行（不占预算，跳过总闸）。"""
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    layer = ActionLayer(
        db,
        {"action": {"autonomous_daily_limit": 1}},
        llm=_FakeLLM("看了。"),
    )
    layer.budget.record("share", datetime(2026, 8, 9))
    assert not layer.budget.can_autonomous(datetime(2026, 8, 9))
    result = await layer.execute_kind(
        "assist",
        EmotionState(curiosity=0.5),
        "friend",
        "spring",
        datetime(2026, 8, 9),
        mode="awake",
        op="read_file",
        target_path=str(f),
        confirmed=True,
    )
    assert result is not None
    assert result["outcome"] == OUTCOME_SUCCESS
