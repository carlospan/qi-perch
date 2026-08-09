"""explore d-3-2：内部 narratives 深读 / digest / drift。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qi.action.explore import (
    _QUERY_PRIVACY_LINE,
    ExploreAction,
    _clip_entry,
)
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
        raise RuntimeError("internal digest boom")


@pytest.fixture
async def db(tmp_path: Path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


def test_clip_entry():
    assert _clip_entry("短") == "短"
    long = "字" * 50
    assert _clip_entry(long).endswith("…")
    assert len(_clip_entry(long)) == 41


@pytest.mark.asyncio
async def test_digest_internal_success(db):
    llm = _SeqLLM("想起午后的光，心里安静了一点。")
    explore = ExploreAction(db, config={}, llm=llm, web=AsyncMock())
    digest = await explore._digest_internal(
        [{"content": "午后的光把影子拉长。"}]
    )
    assert digest == "想起午后的光，心里安静了一点。"
    assert llm.calls and llm.calls[0]["purpose"] == "consciousness"
    joined = " ".join(str(m.get("content") or "") for m in llm.calls[0]["messages"])
    assert _QUERY_PRIVACY_LINE in joined
    assert "不编造" in joined


@pytest.mark.asyncio
async def test_digest_internal_no_llm(db):
    explore = ExploreAction(db, config={}, llm=None, web=AsyncMock())
    digest = await explore._digest_internal([{"content": "x"}])
    assert digest == "我翻了翻自己记得的事。"


@pytest.mark.asyncio
async def test_digest_internal_exception(db):
    explore = ExploreAction(db, config={}, llm=_RaisingLLM(), web=AsyncMock())
    digest = await explore._digest_internal([{"content": "x"}])
    assert digest == "我翻了翻自己记得的事。"


@pytest.mark.asyncio
async def test_read_internal_with_narratives(db):
    await db.save_narrative_memory("纸页空白处，我写你的名字。", importance=0.7)
    llm = _SeqLLM("想起纸页上你的名字。")
    explore = ExploreAction(db, config={}, llm=llm, web=AsyncMock())
    found, summary, outcome = await explore._read_internal()
    assert outcome == OUTCOME_SUCCESS
    assert found is not None
    assert found["source"] == "journal"
    assert found["entries"]
    assert "名字" in found["entries"][0]["title"]
    assert summary == "想起纸页上你的名字。"


@pytest.mark.asyncio
async def test_read_internal_empty(db):
    explore = ExploreAction(db, config={}, llm=_SeqLLM("不应调用"), web=AsyncMock())
    found, summary, outcome = await explore._read_internal()
    assert found is None
    assert "没有" in summary
    assert outcome == OUTCOME_SUCCESS
    assert explore.llm.calls == []  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_drift_internal_with_llm_and_narratives(db):
    await db.save_narrative_memory("楼下传来收废品的铃声。", importance=0.5)
    digest = "铃声很远，像昨天。"
    llm = _SeqLLM(digest)
    explore = ExploreAction(db, config={}, llm=llm, base_probability=1.0)
    result = await explore.drift(
        0.9, EmotionState(curiosity=0.9), "autumn", force=True
    )
    assert result is not None
    assert result["source"] == "journal"
    assert result["speak"] is True
    assert result["qi_line"] == result["summary"] == digest
    assert result["found"]["source"] == "journal"


@pytest.mark.asyncio
async def test_drift_internal_no_llm_with_narratives(db):
    await db.save_narrative_memory("我想给你看一段很短的话。", importance=0.5)
    explore = ExploreAction(db, config={}, llm=None, base_probability=1.0)
    result = await explore.drift(
        0.9, EmotionState(curiosity=0.9), "autumn", force=True
    )
    assert result is not None
    assert result["source"] == "journal"
    assert result["speak"] is True
    assert result["qi_line"] == "我翻了翻自己记得的事。"
    assert result["found"] is not None
