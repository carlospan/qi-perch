"""explore 外部分支：门控 / 红线 / speak / gateway 接线。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from qi.action.explore import (
    EXTERNAL_LAST_KEY,
    ExploreAction,
)
from qi.action.explore_web import SearchHit, WebSearchClient
from qi.action.layer import ActionLayer
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS
from qi.core.emotion import EmotionState
from qi.storage.database import Database


class _FakeLLM:
    def __init__(self, text: str = "枝上那只鸟在想什么") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def call(self, purpose: str, messages: list[dict], temperature=None) -> str:
        self.calls.append(
            {"purpose": purpose, "messages": messages, "temperature": temperature}
        )
        return self.text


def _cfg(*, enabled: bool = True, cooldown_hours: float = 6.0) -> dict:
    return {
        "action": {
            "explore_external": {
                "enabled": enabled,
                "provider": "tavily",
                "api_key": "tvly-test",
                "cooldown_hours": cooldown_hours,
                "probability": 1.0,  # 测试默认必过概率门；个别测再 patch random
            }
        }
    }


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


def _web_ok() -> WebSearchClient:
    web = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    web.search = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            SearchHit(title="窗边的鸟", snippet="小小的", url="https://ex/bird")
        ]
    )
    return web


def _web_empty() -> WebSearchClient:
    web = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    web.search = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return web


@pytest.mark.asyncio
async def test_curiosity_below_08_stays_internal(db, tmp_path: Path):
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    (sandbox / "a.txt").write_text("x", encoding="utf-8")
    llm = _FakeLLM()
    explore = ExploreAction(
        db,
        config={
            "action": {
                "sandbox": str(sandbox),
                "explore_external": {
                    "enabled": True,
                    "api_key": "k",
                    "probability": 1.0,
                    "cooldown_hours": 0,
                },
            }
        },
        llm=llm,
        web=_web_ok(),
        base_probability=1.0,
    )
    with patch("qi.action.explore.random.random", return_value=0.0):
        result = await explore.drift(
            0.79, EmotionState(curiosity=0.79), "spring", force=True
        )
    assert result is not None
    assert result.get("source") == "sandbox"
    assert "speak" not in result
    assert llm.calls == []
    assert result["found"] is not None


@pytest.mark.asyncio
async def test_external_when_gates_pass(db):
    llm = _FakeLLM()
    explore = ExploreAction(
        db, config=_cfg(cooldown_hours=0), llm=llm, web=_web_ok(), base_probability=1.0
    )
    with patch("qi.action.explore.random.random", return_value=0.0):
        result = await explore.drift(
            0.9, EmotionState(curiosity=0.9), "spring", force=True
        )
    assert result is not None
    assert result["source"] == "web"
    assert result["speak"] is True
    assert result["qi_line"]
    assert "窗边的鸟" in result["qi_line"] or "鸟" in result["summary"]
    assert result["found"] is not None
    assert llm.calls and llm.calls[0]["purpose"] == "consciousness"
    joined = " ".join(
        str(m.get("content") or "") for m in llm.calls[0]["messages"]
    )
    assert "不引用 user_facts / 对话内容" in joined


@pytest.mark.asyncio
async def test_cooldown_blocks_external(db):
    now = datetime(2026, 8, 8, 18, 0, 0)
    await db.set_body_memory(
        EXTERNAL_LAST_KEY,
        {"at": (now - timedelta(hours=1)).isoformat(timespec="seconds")},
    )
    llm = _FakeLLM()
    explore = ExploreAction(
        db, config=_cfg(cooldown_hours=6), llm=llm, web=_web_ok(), base_probability=1.0
    )
    with patch("qi.action.explore.random.random", return_value=0.0):
        result = await explore.drift(
            0.95, EmotionState(curiosity=0.95), "spring", force=True, now=now
        )
    assert result is not None
    assert result.get("source") == "sandbox"
    assert "speak" not in result
    assert llm.calls == []


@pytest.mark.asyncio
async def test_web_none_or_llm_none_internal(db, tmp_path: Path):
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    (sandbox / "n.txt").write_text("n", encoding="utf-8")
    cfg = {
        "action": {
            "sandbox": str(sandbox),
            "explore_external": {
                "enabled": True,
                "api_key": "k",
                "probability": 1.0,
                "cooldown_hours": 0,
            },
        }
    }
    a = ExploreAction(db, config=cfg, llm=_FakeLLM(), web=None, base_probability=1.0)
    b = ExploreAction(db, config=cfg, llm=None, web=_web_ok(), base_probability=1.0)
    with patch("qi.action.explore.random.random", return_value=0.0):
        ra = await a.drift(0.95, EmotionState(curiosity=0.95), "spring", force=True)
        rb = await b.drift(0.95, EmotionState(curiosity=0.95), "spring", force=True)
    assert ra is not None and rb is not None
    assert "speak" not in ra and "speak" not in rb
    assert ra.get("source") == "sandbox" and rb.get("source") == "sandbox"


@pytest.mark.asyncio
async def test_external_empty_failed_capability_still_speaks(db):
    llm = _FakeLLM()
    explore = ExploreAction(
        db,
        config=_cfg(cooldown_hours=0),
        llm=llm,
        web=_web_empty(),
        base_probability=1.0,
    )
    with patch("qi.action.explore.random.random", return_value=0.0):
        result = await explore.drift(
            0.95, EmotionState(curiosity=0.95), "spring", force=True
        )
    assert result is not None
    assert result["found"] is None
    assert result["speak"] is True
    assert "不假装" in result["qi_line"]
    assert "编造" not in result["summary"]
    conn = db._require_conn()
    cur = await conn.execute(
        "SELECT outcome FROM actions WHERE id=?", (result["action_id"],)
    )
    outcome = (await cur.fetchone())[0]
    assert outcome == OUTCOME_FAILED_CAPABILITY


@pytest.mark.asyncio
async def test_force_still_respects_external_probability(db):
    """force=True 跳过内部 0.12 门，仍吃外部概率门。"""
    llm = _FakeLLM()
    explore = ExploreAction(
        db, config=_cfg(cooldown_hours=0), llm=llm, web=_web_ok(), base_probability=1.0
    )
    # _should_external 里 random > 0.05 → False；probability 配成 0.05，random=0.5 → 不外部
    cfg = _cfg(cooldown_hours=0)
    cfg["action"]["explore_external"]["probability"] = 0.05
    explore.config = cfg
    with patch("qi.action.explore.random.random", return_value=0.5):
        result = await explore.drift(
            0.95, EmotionState(curiosity=0.95), "spring", force=True
        )
    assert result is not None
    assert result.get("source") == "sandbox"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_non_force_internal_gate_then_external(db):
    llm = _FakeLLM()
    explore = ExploreAction(
        db, config=_cfg(cooldown_hours=0), llm=llm, web=_web_ok(), base_probability=1.0
    )
    # 非 force：先过内部 random（需 ≤ p≈1），再过外部 random=0
    with patch("qi.action.explore.random.random", return_value=0.0):
        result = await explore.drift(
            0.95, EmotionState(curiosity=0.95), "spring", force=False
        )
    assert result is not None
    assert result["source"] == "web"
    assert result["speak"] is True


@pytest.mark.asyncio
async def test_action_layer_passes_llm_and_builds_web(db):
    llm = _FakeLLM()
    layer = ActionLayer(
        db,
        {
            "action": {
                "explore_external": {
                    "enabled": True,
                    "provider": "tavily",
                    "api_key": "tvly-x",
                    "cooldown_hours": 0,
                    "probability": 1.0,
                }
            }
        },
        llm=llm,
    )
    assert layer.explore.llm is llm
    assert layer.explore.web is not None
    assert layer.explore.web.api_key == "tvly-x"

    layer_off = ActionLayer(db, {"action": {"explore_external": {"enabled": False}}}, llm=llm)
    assert layer_off.explore.web is None


@pytest.mark.asyncio
async def test_internal_success_outcome_unchanged(db, tmp_path: Path):
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    (sandbox / "z.txt").write_text("z", encoding="utf-8")
    explore = ExploreAction(
        db,
        config={"action": {"sandbox": str(sandbox)}},
        base_probability=1.0,
    )
    result = await explore.drift(
        0.9, EmotionState(curiosity=0.9), "spring", force=True
    )
    assert result is not None
    assert "speak" not in result
    conn = db._require_conn()
    cur = await conn.execute(
        "SELECT outcome FROM actions WHERE id=?", (result["action_id"],)
    )
    assert (await cur.fetchone())[0] == OUTCOME_SUCCESS
