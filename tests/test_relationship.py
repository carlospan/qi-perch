"""L5 关系系统测试。"""

from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from qi.core.emotion import EmotionState
from qi.memory.first_time import FirstTimeMemory, rule_match
from qi.relationship.culture import detect_shared_culture, format_culture_for_prompt
from qi.relationship.engine import RelationshipEngine, assess_interaction
from qi.relationship.season import determine_season
from qi.relationship.stages import check_stage_upgrade
from qi.relationship.trust import apply_negative_event, apply_positive_interaction
from qi.storage.database import Database


def test_stage_upgrade_only_up():
    assert check_stage_upgrade("stranger", 0.35, 0.45) == "acquaintance"
    assert check_stage_upgrade("acquaintance", 0.2, 0.2) == "acquaintance"  # 不降级
    assert check_stage_upgrade("friend", 0.9, 0.85) == "bonded"


def test_trust_grows_slow_damages_fast():
    t = 0.5
    grown = apply_positive_interaction(t, 1.0)
    assert grown - t == pytest.approx(0.05, abs=1e-9)
    damaged, scar = apply_negative_event(t, 1.0)
    assert t - damaged >= 0.1
    assert scar is True


def test_culture_detects_ritual():
    msgs = [{"role": "user", "content": "早呀", "timestamp": "2026-07-21T09:00:00"}] * 5
    msgs += [{"role": "user", "content": "在忙", "timestamp": "2026-07-21T10:00:00"}]
    culture = detect_shared_culture(msgs, [])
    rituals = [c for c in culture if c["type"] == "ritual"]
    assert rituals
    assert "早" in format_culture_for_prompt(rituals)


def test_season_from_emotions():
    springish = [
        {"energy": 0.8, "valence": 0.2, "curiosity": 0.85} for _ in range(10)
    ]
    assert determine_season(springish) == "spring"
    winterish = [
        {"energy": 0.25, "valence": 0.0, "curiosity": 0.4} for _ in range(10)
    ]
    assert determine_season(winterish) == "winter"


def test_rule_match_goodnight():
    assert rule_match("first_goodnight", "晚安啦")
    assert not rule_match("first_goodnight", "你好")


@pytest.mark.asyncio
async def test_relationship_engine_and_first_time():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        engine = RelationshipEngine(db, llm=None)
        await engine.restore()
        assert engine.state.stage == "stranger"

        # 跨多日以突破每日 depth 上限
        for i in range(50):
            engine._depth_day = None  # 强制换日重置
            engine._depth_gained_today = 0.0
            engine._interaction_day = f"2026-01-{(i % 28) + 1:02d}"
            await engine.on_user_message(
                "我最近在学吉他，今天有点难过但有你在真好"
            )
        assert engine.state.depth > 0.3
        assert engine.state.stage in ("acquaintance", "friend", "bonded")

        ft = FirstTimeMemory(db, llm=None)
        mult, event = await ft.check("晚安", EmotionState())
        assert mult == 3.0
        assert event == "first_goodnight"
        assert await db.has_first_time("first_goodnight")
        mult2, event2 = await ft.check("晚安呀", EmotionState())
        assert mult2 == 1.0
        assert event2 is None

        before = engine.state.trust
        await engine.on_user_message("你烦不烦，删掉算了")
        scars = await db.list_scars()
        assert engine.state.trust < before
        assert scars

        await db.close()


@pytest.mark.asyncio
async def test_assess_interaction_negative():
    s = assess_interaction("你烦，闭嘴")
    assert s.is_negative
    assert s.severity > 0
