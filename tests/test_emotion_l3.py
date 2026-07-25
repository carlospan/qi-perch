"""L3 情绪完善测试。"""

from datetime import datetime, timedelta

from qi.core.emotion import (
    ConsciousnessMode,
    EmotionState,
    apply_circadian,
    apply_coupling,
    apply_mood_cycle,
    modulate_impact,
    mood_cycle_offset,
    should_express,
    step_emotion,
)
from qi.core.rhythm import determine_mode, next_interval


def test_coupling_low_security_raises_attachment_need():
    """security 低于基线 → 依恋需求（attachment）上升。"""
    e = EmotionState(security=0.2, attachment=0.3)
    after = apply_coupling(e)
    assert after.attachment > e.attachment


def test_coupling_low_energy_pulls_valence_down():
    e = EmotionState(energy=0.2, valence=0.3)
    after = apply_coupling(e)
    assert after.valence < e.valence


def test_coupling_stage_scale_stranger_weaker_than_bonded():
    e = EmotionState(security=0.2, attachment=0.3)
    stranger = apply_coupling(e, relationship_stage="stranger")
    bonded = apply_coupling(e, relationship_stage="bonded")
    baseline = apply_coupling(e)
    assert stranger.attachment - e.attachment < bonded.attachment - e.attachment
    assert abs(baseline.attachment - apply_coupling(e, relationship_stage=None).attachment) < 1e-9


def test_mood_cycle_has_periodicity_over_7_days():
    base = datetime(2026, 7, 1, 12, 0, 0)
    offsets = [mood_cycle_offset(base + timedelta(hours=h)) for h in range(0, 7 * 24, 6)]
    assert max(offsets) - min(offsets) > 0.05
    # 同日噪声应稳定（hashlib/toordinal，不依赖 PYTHONHASHSEED）
    t = datetime(2026, 7, 2, 15, 0, 0)
    assert mood_cycle_offset(t) == mood_cycle_offset(t)
    # 同日不同小时：正弦项变，但日噪声分量相同 → 差值应主要来自周期项
    morning = mood_cycle_offset(datetime(2026, 7, 2, 3, 0, 0))
    evening = mood_cycle_offset(datetime(2026, 7, 2, 21, 0, 0))
    assert morning != evening
    # 跨日噪声一般不同
    assert mood_cycle_offset(datetime(2026, 7, 2, 12, 0, 0)) != mood_cycle_offset(
        datetime(2026, 7, 3, 12, 0, 0)
    )


def test_mood_cycle_approach_stays_bounded():
    e = EmotionState(valence=0.1)
    now = datetime(2026, 7, 1, 12, 0, 0)
    for _ in range(50):
        e = apply_mood_cycle(e, now)
    assert -1.0 <= e.valence <= 1.0


def test_circadian_morning_higher_than_night():
    night = EmotionState(energy=0.5)
    morning = EmotionState(energy=0.5)
    for _ in range(40):
        night = apply_circadian(night, 2)
        morning = apply_circadian(morning, 10)
    assert morning.energy > night.energy


def test_should_express_ignores_tiny_delta():
    assert should_express(0.05, "stranger") is False
    assert should_express(0.35, "stranger") is True
    # 关系越深阈值越低
    assert should_express(0.20, "bonded") is True


def test_should_express_accumulation():
    assert should_express(0.01, "stranger", accumulated_suppressed=1.1) is True


def test_modulate_impact_low_security_hurts_more():
    cold = EmotionState(security=0.3, energy=0.6)
    safe = EmotionState(security=0.8, energy=0.6)
    base = -0.2
    assert abs(modulate_impact(base, cold, "stranger")) > abs(
        modulate_impact(base, safe, "stranger")
    )


def test_modulate_impact_tired_more_fragile():
    tired = EmotionState(security=0.5, energy=0.2)
    fresh = EmotionState(security=0.5, energy=0.7)
    base = -0.2
    assert abs(modulate_impact(base, tired, "friend")) > abs(
        modulate_impact(base, fresh, "friend")
    )


def test_mode_silence_30min_to_solitary():
    now = datetime(2026, 7, 21, 15, 0, 0)
    last = now - timedelta(minutes=35)
    mode = determine_mode(last, user_online=True, now=now)
    assert mode == ConsciousnessMode.SOLITARY


def test_mode_long_silence_night_to_dreaming():
    now = datetime(2026, 7, 21, 2, 0, 0)
    last = now - timedelta(hours=5)
    mode = determine_mode(last, user_online=True, now=now)
    assert mode == ConsciousnessMode.DREAMING


def test_mode_interacting_is_awake():
    now = datetime(2026, 7, 21, 15, 0, 0)
    last = now - timedelta(hours=2)
    mode = determine_mode(last, user_online=True, now=now, interacting=True)
    assert mode == ConsciousnessMode.AWAKE


def test_next_interval_arousal_speeds_up():
    calm = EmotionState(mode=ConsciousnessMode.AWAKE, arousal=0.2, energy=0.8)
    excited = EmotionState(mode=ConsciousnessMode.AWAKE, arousal=0.9, energy=0.8)
    assert next_interval(excited) < next_interval(calm)


def test_step_emotion_runs():
    e = EmotionState()
    after = step_emotion(e, datetime(2026, 7, 21, 10, 0, 0))
    assert after.energy != 0  # still alive
    assert 0.05 <= after.energy <= 1.0
