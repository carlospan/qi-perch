"""阶段三·包 10：learning-progress 好奇替换随机动机源。"""

from __future__ import annotations

import inspect
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.core.brain import Brain
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.core.gws import arbitrate
from qi.core.trace import Contender, collect_contenders, salience
from qi.inner_life.consciousness import should_trigger_meta
from qi.inner_life.creativity import CREATION_CURIOSITY_MIN, Creativity
from qi.inner_life.dream import DREAM_CURIOSITY_MIN, DreamEngine
from qi.llm.gateway import LLMCallOutcome
from qi.motivation.curiosity import CuriositySignal
from qi.storage.database import Database


class _StubLLM:
    def __init__(self, text: str = "嗯。"):
        self.text = text
        self.last_outcome = LLMCallOutcome(text=text, failure=None)

    async def call(self, purpose, messages, temperature=None):
        return self.text


class _FailLLM:
    def __init__(self):
        self.last_outcome = LLMCallOutcome(text="", failure="unreachable")

    async def call(self, purpose, messages, temperature=None):
        return ""


def _minimal_brain(tmp: str, llm=None) -> Brain:
    brain = Brain(
        {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
        llm or _StubLLM(),  # type: ignore[arg-type]
    )
    brain.action = None
    brain.inner_life = None
    brain.first_times = None
    brain.relationship = None
    brain.memory = None
    return brain


@pytest.mark.asyncio
async def test_curiosity_rises_with_world_surprise():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _minimal_brain(tmp)
        brain.emotion = EmotionState(curiosity=0.4)
        brain.last_world = {
            "online_rhythm": {"surprise": 3.0, "predicted_online": 0.1, "bucket": "0_12"}
        }
        sig = CuriositySignal()
        v = await sig.update(brain, now=datetime.now())
        assert v > 0.4
        assert brain.emotion.curiosity == v


@pytest.mark.asyncio
async def test_curiosity_rises_with_open_loops():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain._db = db
        brain.emotion = EmotionState(curiosity=0.4)
        brain.last_world = None
        from qi.memory.open_loops import OpenLoopQueue

        q = OpenLoopQueue(db)
        for i in range(4):
            await q.enqueue("silence", seed=f"n{i}")
        v = await CuriositySignal().update(brain, now=datetime.now())
        assert v > 0.4
        await db.close()


@pytest.mark.asyncio
async def test_curiosity_update_no_world_no_loop_stable():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _minimal_brain(tmp)
        brain.emotion = EmotionState(curiosity=0.55)
        brain.last_world = None

        async def _empty():
            return []

        brain._load_open_loops = _empty  # type: ignore[method-assign]
        v1 = await CuriositySignal().update(brain, now=datetime.now())
        v2 = await CuriositySignal().update(brain, now=datetime.now())
        assert v1 == pytest.approx(0.55)
        assert v2 == pytest.approx(0.55)


def test_salience_curiosity_branch():
    assert salience(kind="curiosity", curiosity=0.8) == pytest.approx(0.8)
    assert salience(kind="curiosity", curiosity=0.0) == 0.0


@pytest.mark.asyncio
async def test_collect_contenders_curiosity_gate():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain._db = db
        brain.user_online = True
        brain.last_interaction = datetime.now() - timedelta(seconds=30)
        now = datetime.now()
        with_c = await collect_contenders(
            brain,
            pending=None,
            want_express=False,
            kind=None,
            action_type=None,
            now=now,
            curiosity=0.8,
        )
        assert any(c.kind == "curiosity" for c in with_c)
        without = await collect_contenders(
            brain,
            pending=None,
            want_express=False,
            kind=None,
            action_type=None,
            now=now,
            curiosity=0.0,
        )
        assert not any(c.kind == "curiosity" for c in without)
        # pending 时不入场
        pending = await collect_contenders(
            brain,
            pending="你好",
            want_express=False,
            kind=None,
            action_type=None,
            now=now,
            curiosity=0.9,
        )
        assert any(c.kind == "respond" for c in pending)
        assert not any(c.kind == "curiosity" for c in pending)
        await db.close()


def test_arbitrate_curiosity_vs_respond():
    cands = [
        Contender("curiosity", 0.99, "很好奇"),
        Contender("respond", 1.0, "用户"),
        Contender("proactive:check_in", 0.5, "问候"),
    ]
    w = arbitrate(cands)
    assert w is not None and w.kind == "respond"


def test_arbitrate_curiosity_can_beat_proactive():
    cands = [
        Contender("curiosity", 0.9, "好奇"),
        Contender("proactive:check_in", 0.4, "问候"),
    ]
    w = arbitrate(cands)
    assert w is not None and w.kind == "curiosity"


def test_meta_and_dream_curiosity_gates():
    assert should_trigger_meta("solitary", curiosity=0.1) is False
    assert should_trigger_meta("dreaming", curiosity=0.6) is True
    assert DREAM_CURIOSITY_MIN == 0.55
    assert CREATION_CURIOSITY_MIN == 0.55


@pytest.mark.asyncio
async def test_maybe_create_curiosity_or_emotion():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _StubLLM("一行诗")
        eng = Creativity(db, llm, config={})
        low = EmotionState(
            mode=ConsciousnessMode.SOLITARY,
            curiosity=0.2,
            valence=0.1,
            arousal=0.1,
        )
        assert await eng.maybe_create(low) is None
        high_c = EmotionState(
            mode=ConsciousnessMode.SOLITARY,
            curiosity=0.7,
            valence=0.0,
            arousal=0.0,
        )
        assert await eng.maybe_create(high_c) is not None
        await db.close()


@pytest.mark.asyncio
async def test_maybe_dream_skips_when_curiosity_low():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_episode(
            start_ts="2026-08-01T10:00:00",
            end_ts="2026-08-01T10:05:00",
            topic="t",
            summary="一段未梦见的事",
            key_facts=["a"],
            role_map={},
            emotional_intensity=0.5,
            importance=0.5,
            narrative_id=1,
            source_event_ids=[1],
        )
        eng = DreamEngine(db, _StubLLM("梦"), config={})
        emotion = EmotionState(mode=ConsciousnessMode.DREAMING, curiosity=0.2)
        assert await eng.maybe_dream(emotion) is None
        await db.close()


@pytest.mark.asyncio
async def test_fake_provider_curiosity_update():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp, llm=_FailLLM())
        brain._db = db
        brain.user_online = True
        brain.last_interaction = datetime.now() - timedelta(seconds=5)
        brain.last_world = {"online_rhythm": {"surprise": 1.5}}
        await brain._heartbeat()
        assert 0.0 <= brain.emotion.curiosity <= 1.0
        rows = await db.list_recent_broadcast_traces(1)
        assert rows
        assert "curiosity" in rows[0]["motive"]
        await db.close()


def test_random_not_motive_source_in_dream_create_meta():
    """关键 WHETHER 路径源码中不再用 random 作纯动机门。"""
    import qi.inner_life.consciousness as consciousness
    import qi.inner_life.creativity as creativity
    import qi.inner_life.dream as dream

    dream_src = inspect.getsource(dream.DreamEngine.maybe_dream)
    assert "random.random()" not in dream_src
    assert "curiosity" in dream_src.lower() or "DREAM_CURIOSITY" in dream_src

    create_src = inspect.getsource(creativity.Creativity.maybe_create)
    assert "random.random()" not in create_src

    meta_src = inspect.getsource(consciousness.should_trigger_meta)
    assert "random.random()" not in meta_src
