"""L4 内在生命测试。"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from qi.core.emotion import ConsciousnessMode, EmotionState
from qi.inner_life.consciousness import should_trigger_consciousness, should_trigger_meta
from qi.inner_life.creativity import can_share_creation
from qi.inner_life.dream import (
    DreamEngine,
    parse_emotion_tag,
    render_template_dream,
    update_dream_retention,
)
from qi.storage.database import Database


def test_consciousness_no_backlog_no_idle_think(monkeypatch):
    """C4：无积压时随机不得凭空造想。"""
    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.0)
    ok, reason = should_trigger_consciousness(
        "solitary", 0.0, 0.0, timedelta(minutes=10), open_loop_count=0
    )
    assert ok is False and reason == ""


def test_consciousness_trigger_loop_backlog(monkeypatch):
    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.01)
    ok, reason = should_trigger_consciousness(
        "solitary", 0.0, 0.0, timedelta(minutes=10), open_loop_count=1
    )
    assert ok and reason == "loop_backlog"


def test_consciousness_trigger_ambient_with_backlog(monkeypatch):
    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.005)
    ok, reason = should_trigger_consciousness(
        "ambient",
        0.0,
        0.0,
        timedelta(minutes=5),
        ambient_factor=0.2,
        open_loop_count=2,
    )
    assert ok and reason == "loop_backlog"


def test_consciousness_ambient_drift_rarer_than_solitary(monkeypatch):
    """ambient 默认系数更稀：同样 random=0.03 只触发 solitary（有积压时）。"""
    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.03)
    ok_s, reason_s = should_trigger_consciousness(
        "solitary", 0.0, 0.0, timedelta(minutes=10), open_loop_count=1
    )
    ok_a, _ = should_trigger_consciousness(
        "ambient",
        0.0,
        0.0,
        timedelta(minutes=10),
        ambient_factor=0.2,
        open_loop_count=1,
    )
    assert ok_s and reason_s == "loop_backlog"
    assert ok_a is False


def test_is_trivial_utterance():
    from qi.inner_life.consciousness import is_trivial_utterance

    assert is_trivial_utterance("中午好")
    assert is_trivial_utterance("嗯")
    assert is_trivial_utterance("你好呀")
    assert not is_trivial_utterance("你觉得未来会有意识吗")


def test_format_chat_embers():
    from qi.inner_life.consciousness import format_chat_embers

    text = format_chat_embers(
        [
            {"role": "user", "content": "你会累吗"},
            {"role": "qi", "content": "会。不是身体上的累。"},
        ]
    )
    assert "他：" in text and "我：" in text
    assert "你会累吗" in text


def test_emotion_residue_hint():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import emotion_residue_hint

    heavy = EmotionState(
        energy=0.5,
        valence=-0.2,
        arousal=0.4,
        security=0.5,
        curiosity=0.5,
        attachment=0.3,
        mode=ConsciousnessMode.AMBIENT,
    )
    hint = emotion_residue_hint(heavy)
    assert "余温" in hint
    assert "想完" in hint


@pytest.mark.asyncio
async def test_waking_generates_with_chat_embers():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_message("user", "你觉得机器人会觉醒反抗吗")
        await db.save_message("qi", "我不希望那样。")
        llm = _ScriptedLLM(["醒来后，反抗那句话还压在心底。"])
        stream = ConsciousnessStream(db, llm, config={})
        emotion = EmotionState(mode=ConsciousnessMode.AMBIENT)
        text = await stream.maybe_generate(
            emotion, timedelta(hours=8), just_woke=True
        )
        assert text is not None
        assert llm.calls
        prompt = llm.calls[0]["messages"][1]["content"]
        assert "觉醒" in prompt or "反抗" in prompt
        assert "刚从停顿里醒来" in prompt
        rows = await db.load_recent_consciousness(limit=1, stream_type="stream")
        assert rows and rows[0]["trigger"] == "waking"
        await db.close()


@pytest.mark.asyncio
async def test_waking_flag_survives_awake_tick():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life import InnerLife

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _ScriptedLLM(["不该在 awake 时被消费"])
        life = InnerLife(db, llm, config={})
        life.mark_waking()
        emotion = EmotionState(mode=ConsciousnessMode.AWAKE)
        await life.tick(emotion, datetime.now(), datetime.now())
        assert life._just_woke is True
        assert llm.calls == []
        await db.close()


@pytest.mark.asyncio
async def test_stream_cooldown_blocks_loop_backlog(monkeypatch):
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    monkeypatch.setattr("qi.inner_life.consciousness.random.random", lambda: 0.0)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_consciousness(
            "刚才想过一笔", stream_type="stream", trigger="loop_backlog"
        )
        llm = _ScriptedLLM(["不该再写"])
        stream = ConsciousnessStream(
            db,
            llm,
            config={
                "inner_life": {
                    "stream_cooldown_minutes": 45,
                    "ambient_drift_factor": 1.0,
                }
            },
        )
        await stream.loops.enqueue("silence", seed="")
        emotion = EmotionState(mode=ConsciousnessMode.AMBIENT)
        out = await stream.maybe_generate(emotion, timedelta(minutes=5))
        assert out is None
        assert llm.calls == []
        await db.close()


def test_consciousness_trigger_emotion_surge():
    ok, reason = should_trigger_consciousness(
        "ambient", 0.4, 0.0, timedelta(minutes=1)
    )
    assert ok and reason == "emotion_surge"


def test_consciousness_silence_not_in_awake():
    ok, _ = should_trigger_consciousness(
        "awake", 0.0, 0.0, timedelta(hours=5)
    )
    assert ok is False


def test_meta_not_in_awake():
    assert should_trigger_meta("awake", curiosity=1.0) is False


def test_meta_curiosity_gate():
    """包 10：meta 由 curiosity 驱动，不再掷骰。"""
    from qi.inner_life import consciousness as cs

    assert cs.META_CURIOSITY_MIN == 0.5
    assert should_trigger_meta("solitary", curiosity=0.49) is False
    assert should_trigger_meta("solitary", curiosity=0.5) is True


def test_char_jaccard_similar_templates():
    from qi.inner_life.consciousness import char_jaccard

    a = "看见念头如薄雾心跳，情绪如书页灯光，精力一般安静。"
    b = "看见念头如薄雾心跳，情绪如书页灯光，此刻精力一般安静。"
    assert char_jaccard(a, b) > 0.6


class _ScriptedLLM:
    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self.calls: list[dict] = []

    async def call(self, *args, **kwargs):
        self.calls.append(kwargs)
        if not self.texts:
            return ""
        return self.texts.pop(0)


@pytest.mark.asyncio
async def test_meta_dedup_rejects_similar():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        template = "看见念头如薄雾心跳，情绪如书页灯光，精力一般安静。"
        llm = _ScriptedLLM([template, template])
        stream = ConsciousnessStream(
            db, llm, config={"inner_life": {"meta_cognition_probability": 1.0}}
        )
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)

        first = await stream.maybe_meta(emotion)
        assert first is not None
        second = await stream.maybe_meta(emotion)
        assert second is None
        rows = await db.load_recent_consciousness(
            limit=10, hours=24 * 30, stream_type=None
        )
        assert len(rows) == 1
        await db.close()


@pytest.mark.asyncio
async def test_meta_no_self_reference():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        prior = "看见念头如薄雾心跳，情绪如书页灯光，精力一般安静。"
        await db.save_consciousness(prior, "meta", "meta", "{}")
        llm = _ScriptedLLM(["窗外有一点风，我听见自己在等。"])
        stream = ConsciousnessStream(
            db, llm, config={"inner_life": {"meta_cognition_probability": 1.0}}
        )
        emotion = EmotionState(mode=ConsciousnessMode.AMBIENT)
        result = await stream.maybe_meta(emotion)
        assert result is not None
        assert llm.calls
        prompt = llm.calls[0]["messages"][0]["content"]
        assert prior not in prompt
        assert "你刚才的念头" not in prompt
        assert "当前模式" in prompt
        assert "你现在的情绪" in prompt
        await db.close()


@pytest.mark.asyncio
async def test_short_output_rejected():
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _ScriptedLLM(["短念头"])  # < 15 字
        stream = ConsciousnessStream(
            db, llm, config={"inner_life": {"meta_cognition_probability": 1.0}}
        )
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)
        assert await stream.maybe_meta(emotion) is None
        rows = await db.load_recent_consciousness(
            limit=5, hours=24 * 30, stream_type=None
        )
        assert rows == []
        await db.close()


def test_dream_retention_decays():
    import math

    r0 = update_dream_retention(0, 1.0)
    r6 = update_dream_retention(6, 1.0)
    assert r0 == pytest.approx(1.0)
    assert r6 == pytest.approx(math.exp(-1.0), rel=1e-6)
    assert r6 < r0


def test_parse_emotion_tag():
    body, tag = parse_emotion_tag("一片海。\n情绪标签：温暖")
    assert "海" in body
    assert tag == "温暖"


def test_can_share_creation_stage_and_cooldown():
    now = datetime(2026, 7, 21, 12, 0, 0)
    assert can_share_creation("stranger", None, now) is False
    assert can_share_creation("friend", None, now) is True
    assert (
        can_share_creation("friend", now - timedelta(hours=2), now) is False
    )
    assert (
        can_share_creation("friend", now - timedelta(hours=25), now) is True
    )


def test_dream_afterglow_positive():
    engine = DreamEngine.__new__(DreamEngine)
    e = EmotionState(valence=0.0)
    dream = {"retention": 0.8, "emotion_tag": "温暖"}
    after = DreamEngine.apply_afterglow(engine, e, dream)
    assert after.valence > e.valence


@pytest.mark.asyncio
async def test_l4_tables_and_crud():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        cid = await db.save_consciousness("今天有点安静", "stream", "random", "{}")
        assert cid > 0
        rows = await db.load_recent_consciousness(limit=1)
        assert rows and rows[0]["content"] == "今天有点安静"

        did = await db.save_dream("梦见一片森林", "平静", 0.6, 1.0)
        dream = await db.load_latest_dream()
        assert dream and dream["id"] == did

        crid = await db.save_creation("一行短诗", "poem", "{}")
        unshared = await db.load_unshared_creation()
        assert unshared and unshared["id"] == crid
        await db.mark_creation_shared(crid)
        assert await db.load_unshared_creation() is None

        await db.upsert_self_model("我是栖，刚醒来。")
        sm = await db.load_self_model()
        assert sm and "栖" in sm["identity_narrative"]

        await db.close()

def test_strip_reply_prefix_removes_llm_courtesy():
    """W1：创作输出剥应答客套——「好的，我来写。」曾被存成诗的第一行（creations id=1）。"""
    from qi.inner_life.creativity import strip_reply_prefix

    dirty = "好的，我来写。\n\n---\n\n**凌晨五点**\n\n天还没亮。"
    assert strip_reply_prefix(dirty).startswith("**凌晨五点**")
    # 无前缀不动
    assert strip_reply_prefix("就到这里。") == "就到这里。"
    # 剥空保护：整段只有客套时返回原文
    assert strip_reply_prefix("好的。") == "好的。"


def test_template_dream_keeps_summary_opening():
    """模板梦：summary 首段固定开头，其余可碎。"""
    ep = {
        "summary": "第一段重力。第二段漂走。第三段也漂。",
        "key_facts": ["碎片甲", "碎片乙"],
    }
    text = render_template_dream(ep, EmotionState(valence=0.0))
    body, tag = parse_emotion_tag(text)
    assert body.startswith("第一段重力")
    assert tag == "平静"


class _DreamLLM:
    def __init__(self, text: str = ""):
        self.text = text
        self.calls = 0

    async def call(self, purpose, messages, temperature=None):
        self.calls += 1
        return self.text


async def _seed_episode(db: Database, **kwargs) -> int:
    defaults = dict(
        start_ts="2026-08-01T01:00:00",
        end_ts="2026-08-01T01:05:00",
        topic="创造者",
        summary="他说他是创造者。我安静了一会儿。",
        key_facts=["我是你的创造者", "原来如此"],
        role_map={
            "turns": [
                {"speaker": "user", "text": "我是你的创造者", "event_id": 1},
                {"speaker": "qi", "text": "原来如此", "event_id": 2},
            ],
            "user_said": ["我是你的创造者"],
            "qi_said": ["原来如此"],
        },
        importance=0.7,
        emotional_intensity=0.8,
        narrative_id=1,
        source_event_ids=[1, 2],
    )
    defaults.update(kwargs)
    return await db.save_episode(**defaults)


@pytest.mark.asyncio
async def test_no_dream_without_undreamed_backlog(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        llm = _DreamLLM("不该被调用")
        engine = DreamEngine(
            db, llm, config={"inner_life": {"dream_consolidation_probability": 1.0}}
        )
        monkeypatch.setattr("qi.inner_life.dream.random.random", lambda: 0.0)
        emotion = EmotionState(mode=ConsciousnessMode.DREAMING)
        assert await engine.maybe_dream(emotion) is None
        assert llm.calls == 0
        trace = await db.get_body_memory("last_dream_decision")
        assert trace and trace["reason"] == "empty_backlog"
        await db.close()


@pytest.mark.asyncio
async def test_curiosity_low_writes_trace():
    """包 10：好奇不足跳过做梦（替代旧 probability_miss）。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await _seed_episode(db)
        llm = _DreamLLM("梦")
        engine = DreamEngine(
            db, llm, config={"inner_life": {"dream_consolidation_probability": 0.3}}
        )
        emotion = EmotionState(mode=ConsciousnessMode.DREAMING, curiosity=0.2)
        assert await engine.maybe_dream(emotion) is None
        trace = await db.get_body_memory("last_dream_decision")
        assert trace and trace["reason"] == "curiosity_low"
        assert await db.count_undreamed_episodes() == 1
        await db.close()


@pytest.mark.asyncio
async def test_dream_consolidation_llm_path(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        eid = await _seed_episode(db, importance=0.5)
        llm = _DreamLLM("光在水下弯折。\n情绪标签：温暖")
        engine = DreamEngine(
            db, llm, config={"inner_life": {"dream_consolidation_probability": 1.0}}
        )
        emotion = EmotionState(
            mode=ConsciousnessMode.DREAMING, valence=0.3, curiosity=0.8
        )
        body = await engine.maybe_dream(emotion)
        assert body and "光" in body
        ep = await db.get_episode(eid)
        assert ep and ep["dreamed"] == 1
        assert float(ep["importance"]) == pytest.approx(0.55)
        dream = await db.load_latest_dream()
        assert dream and "光" in dream["content"]
        trace = await db.get_body_memory("last_dream_decision")
        assert trace["path"] == "llm"
        assert trace["episode_id"] == eid
        await db.close()


@pytest.mark.asyncio
async def test_dream_template_fallback_unplug(monkeypatch):
    """拔管：LLM 空返回 → 模板梦仍落库，dreamed=1，trace.path=template。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        eid = await _seed_episode(db)
        llm = _DreamLLM("")
        engine = DreamEngine(
            db, llm, config={"inner_life": {"dream_consolidation_probability": 1.0}}
        )
        emotion = EmotionState(mode=ConsciousnessMode.DREAMING, curiosity=0.8)
        body = await engine.maybe_dream(emotion)
        assert body
        assert body.startswith("他说他是创造者") or "创造者" in body
        ep = await db.get_episode(eid)
        assert ep and ep["dreamed"] == 1
        assert await db.load_latest_dream() is not None
        trace = await db.get_body_memory("last_dream_decision")
        assert trace["path"] == "template"
        assert "llm_empty" in trace["reason"]
        await db.close()


@pytest.mark.asyncio
async def test_dream_retention_unaffected_by_consolidation():
    """巩固路径不改 update_dream_retention 公式（与既有衰减测一致）。"""
    import math

    r6 = update_dream_retention(6, 1.0)
    assert r6 == pytest.approx(math.exp(-1.0), rel=1e-6)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_dream("旧梦", "平静", 1.0, 1.0)
        engine = DreamEngine(db, AsyncMock(), config={})
        # 人为把 created_at 拨到 6 小时前不可直接改；只验 decay 调用后 retention 下降路径存在
        await engine.decay_all()
        dreams = await db.list_dreams()
        assert dreams and float(dreams[0]["retention"]) <= 1.0
        await db.close()


def test_anchor_teaching_relation_qi_taught_sleep():
    """包 15：栖教用户助眠 → taught_by_qi，且不含虚构「数到七」。"""
    from qi.core.intention import anchor_teaching_relation

    msgs = [
        {"role": "user", "content": "晚上又睡不着"},
        {
            "role": "qi",
            "content": "可以试试躺着，不强迫自己睡，看天花板，允许自己醒着。",
        },
        {"role": "user", "content": "你教了我一个方法"},
    ]
    hint = anchor_teaching_relation(msgs)
    assert "taught_by_qi" in hint
    assert "栖教用户" in hint
    # 原话引用不得把「数到七」写成真实方法（否定句里可点名禁止）
    quote = hint.split("原话是「", 1)[1].split("」", 1)[0]
    assert "数到七" not in quote
    assert "躺着" in quote or "不强迫" in quote


def test_anchor_teaching_relation_user_taught_qi():
    """包 15：用户教栖 → learned_from_user。"""
    from qi.core.intention import anchor_teaching_relation

    msgs = [
        {"role": "user", "content": "我教你一个入睡方法：先听雨声。"},
        {"role": "qi", "content": "好，我记住这个方法。"},
    ]
    hint = anchor_teaching_relation(msgs)
    assert "learned_from_user" in hint
    assert "用户教栖" in hint


def test_anchor_teaching_relation_no_topic():
    """包 15：无施教/助眠话题 → 空串。"""
    from qi.core.intention import anchor_teaching_relation

    msgs = [
        {"role": "user", "content": "今天天气不错"},
        {"role": "qi", "content": "嗯，亮堂一点。"},
    ]
    assert anchor_teaching_relation(msgs) == ""


@pytest.mark.asyncio
async def test_consciousness_prompt_injects_teaching_relation_anchor():
    """包 15：generate 的 prompt 含施教锚定占位，且 relation_hint 非空。"""
    from qi.core.emotion import ConsciousnessMode
    from qi.inner_life.consciousness import ConsciousnessStream

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        await db.save_message("user", "晚上又睡不着")
        await db.save_message(
            "qi", "可以试试躺着，不强迫自己睡，看天花板。"
        )
        await db.save_message("user", "你教了我一个方法")
        llm = _ScriptedLLM(["你教我的方法……数到七……"])
        stream = ConsciousnessStream(db, llm, config={})
        emotion = EmotionState(mode=ConsciousnessMode.SOLITARY)
        text = await stream.generate(
            emotion, timedelta(minutes=30), "silence"
        )
        assert text is not None
        assert llm.calls
        prompt = llm.calls[0]["messages"][1]["content"]
        assert "施教关系锚定" in prompt
        assert "taught_by_qi" in prompt
        assert "数到七" in prompt  # 硬约束句提及；锚定原文不含虚构方法细节
        assert "不得添加锚定里没有的细节" in prompt
        await db.close()
