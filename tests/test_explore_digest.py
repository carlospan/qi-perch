"""explore d-2：_digest_hits 成功 / 降级 / 无 llm。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qi.action.explore import ExploreAction
from qi.action.explore_web import SearchHit
from qi.action.permission import OUTCOME_SUCCESS
from qi.core.emotion import EmotionState
from qi.storage.database import Database


class _SeqLLM:
    def __init__(self, texts: list[str] | str) -> None:
        self._texts = [texts] if isinstance(texts, str) else list(texts)
        self.calls: list[dict] = []

    async def call(self, purpose: str, messages: list[dict], temperature=None) -> str:
        self.calls.append(
            {"purpose": purpose, "messages": messages, "temperature": temperature}
        )
        if not self._texts:
            return ""
        if len(self._texts) > 1:
            return self._texts.pop(0)
        return self._texts[0]


class _RaisingLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def call(self, purpose: str, messages: list[dict], temperature=None) -> str:
        self.calls.append({"purpose": purpose, "messages": messages})
        raise RuntimeError("digest boom")


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


def _hits() -> list[SearchHit]:
    return [SearchHit(title="窗边的鸟", snippet="小小的", url="https://ex/bird")]


@pytest.mark.asyncio
async def test_digest_hits_success(db):
    llm = _SeqLLM("落叶好像停在没人看见的角落。")
    explore = ExploreAction(db, config={}, llm=llm, web=AsyncMock())
    digest = await explore._digest_hits("落叶停哪？", _hits())
    assert digest == "落叶好像停在没人看见的角落。"
    assert llm.calls and llm.calls[0]["purpose"] == "consciousness"
    joined = " ".join(str(m.get("content") or "") for m in llm.calls[0]["messages"])
    assert "不引用 user_facts、对话内容或用户文件内容原文" in joined
    assert "窗边的鸟" in joined
    assert "不编造" in joined


@pytest.mark.asyncio
async def test_digest_hits_empty_response_degrades(db):
    llm = _SeqLLM("")
    explore = ExploreAction(db, config={}, llm=llm, web=AsyncMock())
    digest = await explore._digest_hits("落叶停哪？", _hits())
    assert digest == "我刚才看了看 落叶停哪？。"


@pytest.mark.asyncio
async def test_digest_hits_exception_degrades(db):
    explore = ExploreAction(db, config={}, llm=_RaisingLLM(), web=AsyncMock())
    digest = await explore._digest_hits("落叶停哪？", _hits())
    assert digest == "我刚才看了看 落叶停哪？。"


@pytest.mark.asyncio
async def test_digest_hits_no_llm_degrades(db):
    explore = ExploreAction(db, config={}, llm=None, web=AsyncMock())
    digest = await explore._digest_hits("落叶停哪？", _hits())
    assert digest == "我刚才看了看 落叶停哪？。"


@pytest.mark.asyncio
async def test_fetch_external_digest_failure_still_success(db):
    """降级只念 query 时 outcome 仍为 success（搜到了）。"""
    web = AsyncMock()
    web.search = AsyncMock(return_value=_hits())
    llm = _SeqLLM(["窗外问句", ""])  # query ok；digest 空 → 降级
    explore = ExploreAction(
        db,
        config={
            "action": {
                "explore_external": {
                    "enabled": True,
                    "api_key": "k",
                    "probability": 1.0,
                    "cooldown_hours": 0,
                }
            }
        },
        llm=llm,
        web=web,
        base_probability=1.0,
    )
    result = await explore.drift(
        0.95, EmotionState(curiosity=0.95), "spring", force=True
    )
    assert result is not None
    assert result["source"] == "web"
    assert result["qi_line"] == result["summary"] == "我刚才看了看 窗外问句。"
    assert result["found"]["entries"][0]["title"] == "窗边的鸟"
    conn = db._require_conn()
    cur = await conn.execute(
        "SELECT outcome FROM actions WHERE id=?", (result["action_id"],)
    )
    assert (await cur.fetchone())[0] == OUTCOME_SUCCESS
