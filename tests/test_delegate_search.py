"""委托式联网检索。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from qi.action.delegate_search import (
    DelegateSearchAction,
    detect_delegate_search_intent,
    looks_like_delegate_search,
    _weak_delegate_candidate,
)
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


def test_delegate_explore_drift_skips_together_pool():
    from qi.action.together import candidates_from_action_result

    result = {
        "type": "explore_drift",
        "delegate": True,
        "source": "web_delegate",
        "outcome": "success",
        "found": {
            "entries": [
                {"title": "天气", "url": "https://weather.example.com", "snippet": "雨"},
            ],
            "source": "web_delegate",
        },
    }
    assert candidates_from_action_result(result) == []


def test_looks_like_delegate_search_phrases():
    assert looks_like_delegate_search("帮我查一下量子纠缠")
    assert not looks_like_delegate_search("你好")


def test_weak_gate_question_shape_not_topic_keywords():
    assert _weak_delegate_candidate("今天热点新闻有什么")
    assert not _weak_delegate_candidate("昨天晚上聊得挺开心的")
    assert not _weak_delegate_candidate("发生了什么")


@pytest.mark.asyncio
async def test_detect_colloquial_hot_news_via_llm():
    llm = MagicMock()
    llm.call = AsyncMock(
        return_value='{"intent":"search","query":"今天热点新闻"}'
    )
    q = await detect_delegate_search_intent("今天热点新闻有什么", llm=llm)
    assert q == "今天热点新闻"
    llm.call.assert_awaited()


@pytest.mark.asyncio
async def test_detect_meta_ask_skips_delegate():
    llm = MagicMock()
    llm.call = AsyncMock()
    assert await detect_delegate_search_intent("发生了什么", llm=llm) is None
    llm.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_detect_request_intent_without_question_shape():
    llm = MagicMock()
    llm.call = AsyncMock(
        return_value='{"intent":"search","query":"海口今天天气"}'
    )
    q = await detect_delegate_search_intent(
        "海口今天天气",
        llm=llm,
        perception_intent="request",
    )
    assert q == "海口今天天气"
