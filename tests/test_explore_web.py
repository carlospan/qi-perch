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
