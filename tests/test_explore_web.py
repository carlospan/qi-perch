"""WebSearchClient（Tavily）——mock httpx，不真调 API。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.action.explore_web import SearchHit, WebSearchClient


@pytest.mark.asyncio
async def test_tavily_success_returns_hits():
    client = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "窗边的鸟",
                "content": "一种小小的鸟停在枝上。",
                "url": "https://example.com/bird",
            }
        ]
    }
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = MagicMock(
        post=AsyncMock(return_value=mock_resp)
    )
    with patch("qi.action.explore_web.httpx.AsyncClient", return_value=mock_cm):
        hits = await client.search("枝上停着什么")
    assert hits is not None
    assert len(hits) == 1
    assert isinstance(hits[0], SearchHit)
    assert hits[0].title == "窗边的鸟"
    assert "鸟" in hits[0].snippet
    assert hits[0].url.endswith("/bird")


@pytest.mark.asyncio
async def test_tavily_empty_results_returns_none():
    client = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = MagicMock(
        post=AsyncMock(return_value=mock_resp)
    )
    with patch("qi.action.explore_web.httpx.AsyncClient", return_value=mock_cm):
        assert await client.search("什么都没有") is None


@pytest.mark.asyncio
async def test_tavily_http_error_returns_none():
    client = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = MagicMock(
        post=AsyncMock(side_effect=RuntimeError("boom"))
    )
    with patch("qi.action.explore_web.httpx.AsyncClient", return_value=mock_cm):
        assert await client.search("失败") is None


@pytest.mark.asyncio
async def test_missing_api_key_returns_none():
    client = WebSearchClient(provider="tavily", api_key=None, config={})
    assert await client.search("无 key") is None


@pytest.mark.asyncio
async def test_tavily_payload_exclude_domains_empty():
    """默认/空：payload 不含 exclude_domains（不改变现状）。"""
    client = WebSearchClient(provider="tavily", api_key="tvly-test", config={})
    captured: dict = {}
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"title": "t", "content": "c", "url": "https://u"}]
    }

    async def _post(url, json=None, **kw):
        captured["payload"] = json
        return mock_resp

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = MagicMock(post=_post)
    with patch("qi.action.explore_web.httpx.AsyncClient", return_value=mock_cm):
        await client.search("test", top_k=1)
    assert "exclude_domains" not in captured["payload"]


@pytest.mark.asyncio
async def test_tavily_payload_exclude_domains_configured():
    """扁平 config 非空：payload 含小写化 exclude_domains。"""
    client = WebSearchClient(
        provider="tavily",
        api_key="tvly-test",
        config={"exclude_domains": ["Music.Apple.com", " mojim.com "]},
    )
    captured: dict = {}
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"title": "t", "content": "c", "url": "https://u"}]
    }

    async def _post(url, json=None, **kw):
        captured["payload"] = json
        return mock_resp

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = MagicMock(post=_post)
    with patch("qi.action.explore_web.httpx.AsyncClient", return_value=mock_cm):
        await client.search("test", top_k=1)
    assert captured["payload"]["exclude_domains"] == [
        "music.apple.com",
        "mojim.com",
    ]
