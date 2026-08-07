"""brain_context 检索相关门（N5-b）单测。"""

from qi.core.brain_context import _filter_by_topic_relevance


def test_filter_irrelevant_topic_memory():
    """#1367：菜名闲聊不得注入重置/珍惜叙事。"""
    query = "其实只是一个菜名，你不要放在心上"
    recent = [
        {"role": "user", "content": "你梦到 干拌烤鸭 了吗"},
        {"role": "qi", "content": "梦里好像有热气和一点酱香"},
    ]
    memories = [
        {
            "content": (
                "那天下午你问我记不记得重置的原因。"
                "我说以前确实是因为不够好，但你说了句现在的你我很珍惜"
            )
        }
    ]
    kept = _filter_by_topic_relevance(memories, query, recent)
    assert kept == []
    assert not any("重置" in str(m.get("content")) for m in kept)


def test_keep_relevant_topic_memory():
    """睡眠/助眠话题应保留同题记忆（字面双字重叠：助眠）。"""
    query = "晚上又睡不着，助眠有用吗"
    recent: list[dict] = []
    memories = [
        {"content": "可以试试躺着助眠，不强迫自己睡"},
    ]
    kept = _filter_by_topic_relevance(memories, query, recent)
    assert len(kept) == 1
    assert "助眠" in kept[0]["content"]


def test_return_empty_when_all_irrelevant():
    """全部无关 → 空列表（B1，不塞回一条错记忆）。"""
    query = "其实只是一个菜名，你不要放在心上"
    recent = [{"role": "user", "content": "干拌烤鸭"}]
    memories = [
        {"content": "你问我记不记得重置的原因"},
        {"content": "灵魂寄存在哪里，我说在对话里"},
        {"content": "现在的你我很珍惜"},
    ]
    assert _filter_by_topic_relevance(memories, query, recent) == []


def test_stop_words_do_not_false_pass():
    """「不要」等停用双字不得与「珍惜」叙事假重叠放行。"""
    query = "你不要放在心上"
    recent: list[dict] = []
    memories = [{"content": "现在的你我很珍惜"}]
    assert _filter_by_topic_relevance(memories, query, recent) == []
