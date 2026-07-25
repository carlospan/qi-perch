"""用户事实记忆：FactStore / FactNoticer（L2 fact）。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.core.emotion import EmotionState
from qi.memory.facts import CONFIDENCE_FLOOR, FactNoticer, FactStore
from qi.storage.database import Database


@pytest.fixture
async def db_store():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        database = Database(str(Path(tmp) / "qi.db"))
        await database.initialize()
        store = FactStore(database)
        try:
            yield database, store
        finally:
            await database.close()


class _CountingLLM:
    """记录是否被调用；默认返回空事实。"""

    def __init__(self, payload: str = "[]"):
        self.calls = 0
        self.payload = payload

    async def call(self, *args, **kwargs):
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_identity_wo_ming_stranger(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 12, 0)

    results = await noticer.notice(
        "我叫小明", EmotionState(), "stranger", now=now
    )
    assert len(results) == 1
    assert results[0]["action"] == "add"
    assert results[0]["fact_type"] == "identity"

    facts = await store.active_facts("identity")
    assert len(facts) == 1
    assert "小明" in facts[0]["content"]
    assert facts[0]["confidence"] == pytest.approx(0.95)
    assert facts[0]["stability"] == "stable"
    assert facts[0]["superseded_by"] is None


@pytest.mark.asyncio
async def test_other_facts_gated_by_stage(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 12, 0)

    r0 = await noticer.notice(
        "我喜欢咖啡", EmotionState(), "stranger", now=now
    )
    assert r0 == []
    assert await store.active_facts("preference") == []

    r1 = await noticer.notice(
        "我喜欢咖啡", EmotionState(), "acquaintance", now=now
    )
    assert len(r1) == 1
    facts = await store.active_facts("preference")
    assert len(facts) == 1
    assert "咖啡" in facts[0]["content"]


@pytest.mark.asyncio
async def test_chitchat_no_fact_no_llm(db_store):
    db, store = db_store
    llm = _CountingLLM()
    noticer = FactNoticer(store, llm=llm)  # type: ignore[arg-type]
    now = datetime(2026, 7, 23, 12, 0)

    results = await noticer.notice(
        "今天天气真好", EmotionState(), "acquaintance", now=now
    )
    assert results == []
    assert llm.calls == 0
    assert await store.active_facts() == []


@pytest.mark.asyncio
async def test_repeat_identity_only_confirms(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    t0 = datetime(2026, 7, 23, 12, 0)
    t1 = datetime(2026, 7, 24, 12, 0)

    await noticer.notice("我叫小明", EmotionState(), "stranger", now=t0)
    await noticer.notice("我叫小明", EmotionState(), "stranger", now=t1)

    facts = await store.active_facts("identity")
    assert len(facts) == 1
    assert facts[0]["last_confirmed"] == t1.isoformat(timespec="seconds")
    assert facts[0]["first_learned"] == t0.isoformat(timespec="seconds")


@pytest.mark.asyncio
async def test_occupation_supersede_keeps_trace(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    t0 = datetime(2026, 7, 23, 12, 0)
    t1 = datetime(2026, 7, 24, 12, 0)

    old_id = await store.add(
        "occupation",
        "他在甲公司工作",
        0.9,
        "state",
        "从前说过",
        0.6,
        t0,
    )
    results = await noticer.notice(
        "我换工作了", EmotionState(), "acquaintance", now=t1
    )
    assert any(r.get("action") == "supersede" for r in results)

    active = await store.active_facts("occupation")
    assert len(active) == 1
    assert "换了工作" in active[0]["content"]
    assert int(active[0]["id"]) != old_id

    old = await db.get_user_fact(old_id)
    assert old is not None
    assert old["superseded_by"] == active[0]["id"]


@pytest.mark.asyncio
async def test_low_confidence_not_stored(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 12, 0)

    landed = await noticer._land(
        {
            "fact_type": "other",
            "content": "他可能喜欢雨",
            "confidence": CONFIDENCE_FLOOR - 0.1,
            "stability": "stable",
            "emotional_weight": 0.4,
        },
        "大概吧",
        now,
    )
    assert landed is None
    assert await store.active_facts() == []


@pytest.mark.asyncio
async def test_facts_survive_reopen():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = str(Path(tmp) / "qi.db")
        db1 = Database(path)
        await db1.initialize()
        store1 = FactStore(db1)
        noticer = FactNoticer(store1, llm=None)
        now = datetime(2026, 7, 23, 12, 0)
        await noticer.notice("我叫小明", EmotionState(), "stranger", now=now)
        await db1.close()

        db2 = Database(path)
        await db2.initialize()
        store2 = FactStore(db2)
        facts = await store2.active_facts("identity")
        assert len(facts) == 1
        assert "小明" in facts[0]["content"]
        await db2.close()


@pytest.mark.asyncio
async def test_identity_correction_supersedes(db_store):
    db, store = db_store
    noticer = FactNoticer(store, llm=None)
    t0 = datetime(2026, 7, 23, 12, 0)
    t1 = datetime(2026, 7, 24, 12, 0)

    await noticer.notice("我叫小明", EmotionState(), "stranger", now=t0)
    old = (await store.active_facts("identity"))[0]

    results = await noticer.notice(
        "我不叫小明，我叫小红", EmotionState(), "stranger", now=t1
    )
    assert any(r.get("action") == "supersede" for r in results)

    active = await store.active_facts("identity")
    assert len(active) == 1
    assert "小红" in active[0]["content"]
    assert "小明" not in active[0]["content"]

    old_row = await db.get_user_fact(int(old["id"]))
    assert old_row is not None
    assert old_row["superseded_by"] == active[0]["id"]


@pytest.mark.asyncio
async def test_format_facts_for_prompt_restrained():
    from qi.memory.facts import format_facts_for_prompt

    empty = format_facts_for_prompt([], "stranger")
    assert "不太了解" in empty

    facts = [
        {
            "fact_type": "identity",
            "content": "他叫小明",
            "emotional_weight": 0.9,
        },
        {
            "fact_type": "occupation",
            "content": "他在甲公司工作",
            "emotional_weight": 0.5,
        },
        {
            "fact_type": "preference",
            "content": "他喜欢咖啡",
            "emotional_weight": 0.4,
        },
    ]
    stranger = format_facts_for_prompt(facts, "stranger")
    assert "小明" in stranger
    # 陌生期上限 2，且优先身份
    assert stranger.count("。") <= 2

    friend = format_facts_for_prompt(facts, "friend")
    assert "小明" in friend
    assert "甲公司" in friend or "咖啡" in friend


@pytest.mark.asyncio
async def test_prompt_contains_user_facts_after_reopen():
    """重启后从 DB 读 active，组装的 system prompt 仍含「你认识的他」。"""
    from qi.llm.prompt_builder import PromptBuilder
    from qi.memory.facts import format_facts_for_prompt
    from qi.memory.manager import MemoryManager

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = str(Path(tmp) / "qi.db")
        db1 = Database(path)
        await db1.initialize()
        mgr1 = MemoryManager(db1, {"memory": {"chroma_path": str(Path(tmp) / "chroma")}})
        await mgr1.notice_facts(
            "我叫小明", EmotionState(), "stranger", datetime(2026, 7, 23, 12, 0)
        )
        await db1.close()

        db2 = Database(path)
        await db2.initialize()
        mgr2 = MemoryManager(db2, {"memory": {"chroma_path": str(Path(tmp) / "chroma2")}})
        # restore 不装载事实；按需读
        await mgr2.restore()
        facts = await mgr2.active_facts()
        assert any("小明" in str(f.get("content")) for f in facts)

        block = format_facts_for_prompt(facts, "stranger")
        messages = PromptBuilder().build_conversation_prompt(
            user_message="嗨",
            emotion=EmotionState(),
            now=datetime(2026, 7, 23, 13, 0),
            inner_extras={"user_facts": block},
            relationship_stage="stranger",
        )
        system = messages[0]["content"]
        assert "【你认识的他】" in system
        assert "小明" in system
        assert "不要每句都喊" in system
        await db2.close()


@pytest.mark.asyncio
async def test_name_question_does_not_extract_ma(db_store):
    """「记得我的名字吗」不得抽出「他叫吗」。"""
    _, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 22, 21)

    results = await noticer.notice(
        "我已经重启了，你还记得我的名字吗？",
        EmotionState(),
        "stranger",
        now=now,
    )
    assert results == []
    assert await store.active_facts("identity") == []


@pytest.mark.asyncio
async def test_awaiting_name_bare_utterance_script(db_store):
    """实测剧本：我是说我的名字 →（栖邀名）→ 潘纪振。"""
    _, store = db_store
    noticer = FactNoticer(store, llm=None)
    t0 = datetime(2026, 7, 23, 22, 21, 0)
    t1 = datetime(2026, 7, 23, 22, 21, 30)

    r0 = await noticer.notice(
        "我是说我的名字", EmotionState(), "stranger", now=t0
    )
    assert r0 == []
    assert noticer._awaiting_name_active(t0)

    recent = [
        {"role": "user", "content": "我是说我的名字"},
        {"role": "qi", "content": "好啊，你告诉我。"},
    ]
    r1 = await noticer.notice(
        "潘纪振",
        EmotionState(),
        "stranger",
        now=t1,
        recent_messages=recent,
    )
    assert len(r1) == 1
    assert r1[0]["action"] in ("add", "supersede")
    facts = await store.active_facts("identity")
    assert len(facts) == 1
    assert "潘纪振" in facts[0]["content"]


@pytest.mark.asyncio
async def test_awaiting_name_after_qi_asks_your_name(db_store):
    """栖问「你叫什么名字」后，用户光给名字应落库。"""
    _, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 23, 22, 42)
    recent = [
        {"role": "user", "content": "你叫什么名字"},
        {
            "role": "qi",
            "content": "我叫栖。\n\n你呢？你叫什么名字？",
        },
    ]
    results = await noticer.notice(
        "潘纪振",
        EmotionState(),
        "stranger",
        now=now,
        recent_messages=recent,
    )
    assert len(results) == 1
    facts = await store.active_facts("identity")
    assert len(facts) == 1
    assert "潘纪振" in facts[0]["content"]


@pytest.mark.asyncio
async def test_bare_name_without_await_ignored(db_store):
    _, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 12, 0)
    results = await noticer.notice(
        "潘纪振", EmotionState(), "stranger", now=now
    )
    assert results == []
    assert await store.active_facts("identity") == []


@pytest.mark.asyncio
async def test_purge_bogus_identity_on_notice(db_store):
    _, store = db_store
    noticer = FactNoticer(store, llm=None)
    now = datetime(2026, 7, 23, 12, 0)
    await store.add(
        "identity",
        "他叫吗",
        0.95,
        "stable",
        "误抽",
        0.8,
        now,
    )
    assert len(await store.active_facts("identity")) == 1

    await noticer.notice("今天天气真好", EmotionState(), "acquaintance", now=now)
    assert await store.active_facts("identity") == []


@pytest.mark.asyncio
async def test_looks_like_person_name_gate():
    from qi.memory.facts import looks_like_person_name

    assert looks_like_person_name("潘纪振")
    assert looks_like_person_name("小明")
    assert not looks_like_person_name("吗")
    assert not looks_like_person_name("什么")
    assert not looks_like_person_name("好的")
    assert not looks_like_person_name("谢谢你")
    assert not looks_like_person_name("谢谢")
