"""L7 判断制：接 / 拒 / 延 + 委托队列。"""

from __future__ import annotations

import pytest

from qi.action.judgment import (
    OUTCOME_ACCEPT,
    OUTCOME_DECLINED,
    OUTCOME_DEFERRED,
    enqueue_delegate,
    judge_responsive_action,
    load_delegate_queue,
    pop_delegate_queue,
)


def test_judge_decline_stranger_open():
    j = judge_responsive_action(
        "open",
        relationship_stage="stranger",
        energy=0.6,
        mode="awake",
    )
    assert j.decision == OUTCOME_DECLINED


def test_judge_accept_friend_assist():
    j = judge_responsive_action(
        "assist",
        relationship_stage="friend",
        energy=0.6,
        mode="awake",
    )
    assert j.decision == OUTCOME_ACCEPT
    assert j.qi_line


def test_judge_defer_low_energy():
    j = judge_responsive_action(
        "delegate_search",
        relationship_stage="friend",
        energy=0.1,
        mode="awake",
    )
    assert j.decision == OUTCOME_DEFERRED


@pytest.mark.asyncio
async def test_delegate_queue_roundtrip(db):
    await enqueue_delegate(
        db,
        kind="delegate_search",
        summary="查量子",
        payload={"query": "量子纠缠"},
        user_text="帮我查一下量子纠缠",
    )
    items = await load_delegate_queue(db)
    assert len(items) == 1
    head = await pop_delegate_queue(db)
    assert head is not None
    assert head["kind"] == "delegate_search"
    assert await load_delegate_queue(db) == []


def test_delegate_search_looks_like():
    from qi.action.delegate_search import looks_like_delegate_search

    assert looks_like_delegate_search("帮我查一下量子纠缠")
    assert not looks_like_delegate_search("你在干嘛")
