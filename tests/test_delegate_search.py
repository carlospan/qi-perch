"""委托式联网检索。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
    web.config = {}
    llm = MagicMock()
    llm.call = AsyncMock(return_value="网上说大概是这么回事。")
    action = DelegateSearchAction(db, web=web, llm=llm)
    with patch(
        "qi.action.search_plan.fetch_page_text",
        new=AsyncMock(return_value="正文里写了更多细节。"),
    ):
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
    assert web.search.await_count >= 1
    assert isinstance(out["found"].get("deep_read"), list)


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


def test_looks_like_followup_search():
    from qi.action.delegate_search import looks_like_followup_search

    assert looks_like_followup_search("我在抖音刷到，最近有个世界机器人大会")
    assert looks_like_followup_search("你再查一下")
    assert not looks_like_followup_search("今天天气真好")


def test_anchor_search_query_keeps_topic_on_followup():
    from qi.action.delegate_search import anchor_search_query, query_shares_topic

    recent = "2026年世界机器人大会相关信息有哪些？"
    dropped = "最新的是今年的还是往届的？"
    user = "那是今年的还是往届的？你再查一下最新的。"
    assert not query_shares_topic(dropped, recent)
    out = anchor_search_query(dropped, recent, user)
    assert "世界机器人大会" in out
    assert "往届" in out or "今年" in out


def test_anchor_search_query_does_not_glue_topic_switch():
    from qi.action.delegate_search import anchor_search_query

    recent = "2026年世界机器人大会相关信息有哪些？"
    out = anchor_search_query(
        "量子纠缠入门资料",
        recent,
        "帮我查一下量子纠缠入门资料",
    )
    assert out == "量子纠缠入门资料"
    assert "世界机器人大会" not in out


@pytest.mark.asyncio
async def test_detect_followup_anchors_recent_when_llm_drops_topic():
    """强启发「再查」路径：LLM 丢主题时仍锚回 recent。"""
    llm = MagicMock()
    llm.call = AsyncMock(return_value="最新的是今年的还是往届的？")
    recent = "2026年世界机器人大会相关信息有哪些？"
    q = await detect_delegate_search_intent(
        "那是今年的还是往届的？你再查一下最新的。",
        llm=llm,
        recent_query=recent,
    )
    assert q is not None
    assert "世界机器人大会" in q


def test_build_query_variants_adds_year():
    from datetime import datetime

    from qi.action.delegate_search import build_query_variants

    vs = build_query_variants(
        "世界机器人大会", now=datetime(2026, 8, 25)
    )
    assert vs[0] == "世界机器人大会"
    assert any("2026" in v for v in vs)


def test_merge_search_hits_dedupes_url():
    from qi.action.delegate_search import merge_search_hits
    from qi.action.explore_web import SearchHit

    a = SearchHit("A", "s1", "https://ex.com/a")
    b = SearchHit("A2", "s2", "https://ex.com/a")
    c = SearchHit("C", "s3", "https://ex.com/c")
    merged = merge_search_hits([[a], [b, c]], limit=5)
    assert len(merged) == 2
    assert merged[0].url.endswith("/a")
    assert merged[1].url.endswith("/c")


@pytest.mark.asyncio
async def test_delegate_search_multi_query_calls_web():
    """P0：execute 会发多轮 search（通用变体 + news）。"""
    web = MagicMock()
    hit = SearchHit(title="2026大会", snippet="8月在北京举办", url="https://news.example/wrc")
    web.search = AsyncMock(return_value=[hit])
    web.config = {
        "delegate_top_k": 4,
        "delegate_search_depth": "basic",
        "delegate_time_range": "month",
    }
    llm = MagicMock()
    llm.call = AsyncMock(return_value="查到今年大会在北京办。")
    action = DelegateSearchAction(db=MagicMock(), web=web, llm=llm)
    action.db.insert_action = AsyncMock(return_value=1)
    with patch(
        "qi.action.search_plan.fetch_page_text",
        new=AsyncMock(return_value="2026年8月19日至23日在北京亦庄举办。"),
    ):
        out = await action.execute(
            "世界机器人大会",
            season="spring",
            now=datetime(2026, 8, 25, 12, 0),
            user_text="最近有个世界机器人大会了解吗",
        )
    assert out.get("outcome") == "success"
    assert web.search.await_count >= 3  # 变体 + news 至少三轮
    topics = [
        call.kwargs.get("topic")
        for call in web.search.await_args_list
        if call.kwargs
    ]
    assert "news" in topics
    assert out["found"]["deep_read"]


def test_pick_deep_read_prefers_non_encyclopedia():
    from qi.action.delegate_search import pick_deep_read_hits

    wiki = SearchHit("百科", "年表", "https://zh.wikipedia.org/wiki/wrc")
    news = SearchHit("新闻", "开幕", "https://www.beijing.gov.cn/wrc")
    picked = pick_deep_read_hits([wiki, news], max_n=1)
    assert len(picked) == 1
    assert "beijing.gov.cn" in picked[0].url


def test_html_to_text_strips_tags():
    from qi.action.explore_web import _html_to_text

    html = "<html><script>x</script><body><p>你好</p><p>世界</p></body></html>"
    assert "你好" in _html_to_text(html)
    assert "script" not in _html_to_text(html).lower()


@pytest.mark.asyncio
async def test_digest_includes_deep_read_material():
    llm = MagicMock()
    llm.call = AsyncMock(return_value="深读新闻后，大会在北京办。")
    action = DelegateSearchAction(db=MagicMock(), web=MagicMock(), llm=llm)
    hits = [SearchHit("大会", "摘要很短", "https://news.example.com/a")]
    deep = [
        {
            "url": "https://news.example.com/a",
            "title": "大会",
            "text": "2026年8月19日至23日在北京经济技术开发区举行。",
        }
    ]
    await action._digest_hits("世界机器人大会", hits, deep_pages=deep)
    msgs = llm.call.await_args.kwargs["messages"]
    blob = msgs[1]["content"]
    assert "深读" in blob
    assert "2026年8月19日" in blob
    assert "深读" in msgs[0]["content"] or "正文" in msgs[0]["content"]


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


@pytest.mark.asyncio
async def test_delegate_search_two_beat_no_concat():
    """接受句先开口；查完摘要不与接受句拼接。"""
    from datetime import datetime
    from unittest.mock import AsyncMock, MagicMock, patch

    from qi.action.judgment import JudgmentResult, OUTCOME_ACCEPT
    from qi.core import brain_judgment as bj

    brain = MagicMock()
    brain.llm = MagicMock()
    brain._db = MagicMock()
    brain.action = MagicMock()
    brain.action._build_explore_web = MagicMock(return_value=MagicMock())
    brain.action.assist.narrative = None
    brain._current_season = MagicMock(return_value="autumn")
    brain._deliver_qi_message = AsyncMock()
    brain._deliver_action_result = AsyncMock()
    brain.embodiment = MagicMock()
    brain.embodiment.send_typing = AsyncMock()

    digest = "大会每年办，偏工业与人形机器人展。"
    fake_result = {
        "type": "explore_drift",
        "qi_line": digest,
        "speak": True,
        "outcome": "success",
    }

    with (
        patch(
            "qi.action.delegate_search.detect_delegate_search_intent",
            new=AsyncMock(return_value="世界机器人大会"),
        ),
        patch(
            "qi.action.delegate_search.looks_like_delegate_search",
            return_value=True,
        ),
        patch(
            "qi.core.brain_judgment.judge_for_kind",
            new=AsyncMock(
                return_value=JudgmentResult(
                    OUTCOME_ACCEPT,
                    "这个我不太清楚，我去查一下。",
                    {"reason": "willing"},
                )
            ),
        ),
        patch(
            "qi.action.delegate_search.DelegateSearchAction.execute",
            new=AsyncMock(return_value=fake_result),
        ),
    ):
        out = await bj.try_delegate_search_message(
            brain, "最近有个世界机器人大会，你有所了解吗？", datetime.now()
        )

    assert out == digest
    brain._deliver_qi_message.assert_awaited()
    accept_call = brain._deliver_qi_message.await_args
    assert "不太清楚" in accept_call.args[0]
    assert "查" in accept_call.args[0]
    brain._deliver_action_result.assert_awaited_once()
    delivered = brain._deliver_action_result.await_args.args[0]
    assert delivered["qi_line"] == digest
    assert "帮你看看" not in delivered["qi_line"]
    assert not delivered["qi_line"].startswith("这个我不太清楚")


def test_delegate_digest_prompt_forbids_mixed_tense():
    import inspect

    from qi.action.search_plan import DelegateSearchPlanner

    src = inspect.getsource(DelegateSearchPlanner.digest)
    assert "我大概看懂了" in src
    assert "去查那一拍已经说过了" in src
    assert "对不上" in src or "不敢断定" in src
    assert "出处" in src


@pytest.mark.asyncio
async def test_search_planner_run_orchestrates():
    """P3：planner 独立跑通 搜→深读→摘要。"""
    from qi.action.search_plan import DelegateSearchPlanner

    web = MagicMock()
    hit = SearchHit("标题", "摘要", "https://news.example.com/x")
    web.search = AsyncMock(return_value=[hit])
    web.config = {"delegate_deep_read": True, "delegate_deep_read_max": 1}
    llm = MagicMock()
    llm.call = AsyncMock(return_value="新闻里说是这么回事。")
    planner = DelegateSearchPlanner(web, llm=llm, config=web.config)
    with patch(
        "qi.action.search_plan.fetch_page_text",
        new=AsyncMock(return_value="正文细节。"),
    ):
        plan = await planner.run("某事", now=datetime(2026, 8, 25, 12, 0))
    assert not plan.empty
    assert plan.hits
    assert plan.digest
    assert plan.variants
    assert web.search.await_count >= 3


def test_format_hits_for_digest_includes_domain():
    from qi.action.delegate_search import format_hits_for_digest
    from qi.action.explore_web import SearchHit

    text = format_hits_for_digest(
        [
            SearchHit(
                "世界机器人大会",
                "2017年主办信息",
                "https://zh.wikipedia.org/wiki/x",
            ),
            SearchHit(
                "大会开幕",
                "2026年8月在北京",
                "https://www.beijing.gov.cn/a",
            ),
        ]
    )
    assert "[1]" in text and "wikipedia.org" in text
    assert "[2]" in text and "beijing.gov.cn" in text
    assert "2017" in text and "2026" in text


@pytest.mark.asyncio
async def test_digest_hits_passes_formatted_sources():
    """P1：digest 收到带域名的对照材料。"""
    llm = MagicMock()
    llm.call = AsyncMock(return_value="新闻里说今年在北京办，百科年表偏旧，我不敢混在一起讲。")
    action = DelegateSearchAction(db=MagicMock(), web=MagicMock(), llm=llm)
    hits = [
        SearchHit("旧", "2017主题", "https://zh.wikipedia.org/wiki/wrc"),
        SearchHit("新", "2026开幕", "https://news.example.com/wrc2026"),
    ]
    out = await action._digest_hits("世界机器人大会", hits)
    assert "不敢" in out or "北京" in out
    msgs = llm.call.await_args.kwargs["messages"]
    blob = msgs[1]["content"]
    assert "wikipedia.org" in blob
    assert "news.example.com" in blob
    sys = msgs[0]["content"]
    assert "对照" in sys
    assert "出处" in sys
