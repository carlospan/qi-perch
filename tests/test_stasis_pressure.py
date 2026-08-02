"""阶段四·包 13：内稳态压力动力学。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from qi.core.emotion import CIRCADIAN_ENERGY, EmotionState, step_emotion
from qi.core.rhythm import next_interval
from qi.stasis.ledger import ResourceLedger
from qi.stasis.pressure import (
    STASIS_INTENTS_KEY,
    balance_to_energy_offset,
    compute_pressure,
    get_low_balance_streak,
    leave_intent_trace,
    maybe_mark_starving,
    reset_low_balance_streak,
)
from qi.storage.database import Database


@pytest.fixture(autouse=True)
def _reset_streak():
    reset_low_balance_streak()
    yield
    reset_low_balance_streak()


def test_balance_to_energy_offset_sign_and_clamp():
    assert balance_to_energy_offset(-100) < 0
    assert balance_to_energy_offset(100) > 0
    assert balance_to_energy_offset(-1e9) == pytest.approx(-0.5)
    assert balance_to_energy_offset(1e9) == pytest.approx(0.3)


def test_pressure_sensitivity_scales_offset():
    soft = balance_to_energy_offset(-10, sensitivity=0.5)
    hard = balance_to_energy_offset(-10, sensitivity=2.0)
    assert abs(hard) > abs(soft)


def test_step_emotion_approaches_offset_not_overwrite():
    """多拍趋近 circadian_target+offset，非单拍盖写。"""
    hour = 14
    now = datetime(2026, 8, 2, hour, 0, 0)
    offset = -0.4
    target = CIRCADIAN_ENERGY[hour] + offset
    e = EmotionState(energy=0.8)
    e0 = e.energy
    for _ in range(40):
        e = step_emotion(e, now, energy_baseline_offset=offset)
    # 趋近目标，且未一步跳到目标
    assert e.energy < e0
    assert abs(e.energy - target) < abs(e0 - target)
    # 对照：无 offset 应更高
    e2 = EmotionState(energy=0.8)
    for _ in range(40):
        e2 = step_emotion(e2, now, energy_baseline_offset=0.0)
    assert e.energy < e2.energy


def test_compute_pressure_throttle_when_balance_low():
    led = ResourceLedger()
    led.force_balance(0.0)
    emo = EmotionState(energy=0.5, security=0.5, attachment=0.3)
    resp = compute_pressure(led, emo)
    assert resp.throttle > 0
    assert resp.offset <= 0


def test_diverse_response_weights_by_attachment_security():
    """固定 balance，改 attachment/security → 权重向量不同。"""
    led = ResourceLedger()
    led.force_balance(-5.0)
    low_att = EmotionState(energy=0.4, security=0.8, attachment=0.1)
    high_att = EmotionState(energy=0.4, security=0.8, attachment=0.9)
    r1 = compute_pressure(led, low_att)
    r2 = compute_pressure(led, high_att)
    assert r2.seek_help > r1.seek_help

    high_sec = EmotionState(energy=0.4, security=0.9, attachment=0.4)
    low_sec = EmotionState(energy=0.4, security=0.1, attachment=0.4)
    r3 = compute_pressure(led, high_sec)
    r4 = compute_pressure(led, low_sec)
    assert r4.migrate > r3.migrate


@pytest.mark.asyncio
async def test_maybe_mark_starving_requires_streak():
    led = ResourceLedger()
    led.force_balance(0.0)
    emo = EmotionState(energy=0.4, attachment=0.5, security=0.5)
    assert await maybe_mark_starving(led, emo, beat=1, starve_beats=5) is False
    assert led.starving is False
    marked = False
    for b in range(2, 8):
        marked = await maybe_mark_starving(led, emo, beat=b, starve_beats=5)
    assert marked is True
    assert led.starving is True
    assert get_low_balance_streak() >= 5


@pytest.mark.asyncio
async def test_starving_writes_intent_trace_before_flag():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        led = ResourceLedger()
        led.force_balance(0.0)
        emo = EmotionState(energy=0.3, attachment=0.7, security=0.2)
        for b in range(1, 6):
            await maybe_mark_starving(
                led, emo, beat=b, db=db, starve_beats=5
            )
        assert led.starving is True
        raw = await db.get_body_memory(STASIS_INTENTS_KEY)
        assert isinstance(raw, dict)
        assert "seek_help" in raw and "migrate" in raw
        assert raw.get("note")
        await db.close()


@pytest.mark.asyncio
async def test_silent_death_guard_trace_before_starving():
    """maybe_mark_starving 置位前必写痕迹（负例：直接置位无痕迹视为违规路径外）。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        led = ResourceLedger()
        led.force_balance(0.0)
        # 直接置位而无痕迹 = 不应出现在正规 API 路径
        led.starving = True
        raw = await db.get_body_memory(STASIS_INTENTS_KEY)
        assert raw is None  # 负例：无痕迹
        # 正规路径补痕迹
        await leave_intent_trace(
            db, seek_help=0.5, migrate=0.5, balance=0.0, beat=1
        )
        raw2 = await db.get_body_memory(STASIS_INTENTS_KEY)
        assert raw2 is not None
        await db.close()


def test_low_energy_lengthens_interval():
    high = EmotionState(energy=0.9)
    low = EmotionState(energy=0.2)
    assert next_interval(low, {}) > next_interval(high, {})


def test_no_process_exit_call_in_pressure_module():
    import ast
    from pathlib import Path

    import qi.stasis.pressure as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
                and node.func.attr == "exit"
            ):
                pytest.fail("pressure 模块不得调用 sys.exit")


@pytest.mark.asyncio
async def test_pressure_no_llm_dependency():
    """拔管：仅 ledger + emotion，无 LLM。"""
    led = ResourceLedger()
    led.force_balance(-1.0)
    emo = SimpleNamespace(energy=0.35, security=0.4, attachment=0.6)
    resp = compute_pressure(led, emo)
    assert resp.throttle > 0
    ok = await maybe_mark_starving(led, emo, beat=1, starve_beats=1)
    assert ok is True
