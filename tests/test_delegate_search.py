"""委托式联网检索。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.action.delegate_search import DelegateSearchAction, looks_like_delegate_search
from qi.action.explore_web import SearchHit


@pytest.mark.asyncio
async def test_delegate_search_success(db):
    web = MagicMock()
    web.search = AsyncMock(
        return_value=[
            SearchHit(title="A", snippet="snippet", url="https://example.com/a"),
        ]
    )
    llm = MagicMock()
    llm.call = AsyncMock(return_value="网上说大概是这么回事。")
    action = DelegateSearchAction(db, web=web, llm=llm)
    out = await action.execute(
        "量子纠缠",
        season="spring",
        now=datetime(2026, 8, 22, 12, 0),
        user_text="帮我查一下量子纠缠",
        motive={"reason": "willing"},
    )
    assert out.get("outcome") == "success"
    assert out.get("type") == "explore_drift"
    assert out["found"]["source"] == "web_delegate"
    assert out.get("delegate") is True
    web.search.assert_awaited_once()


def test_looks_like_delegate_search_phrases():
    assert looks_like_delegate_search("帮我查一下量子纠缠")
    assert not looks_like_delegate_search("你好")
