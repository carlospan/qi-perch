"""情绪动力学单元测试。"""

from core.emotion import (
    BASELINES,
    EmotionState,
    apply_decay,
    apply_event_impact,
    clamp_emotion,
)
from core.perception import Perception


def test_positive_impact_raises_valence():
    e = EmotionState(valence=0.0)
    new = apply_event_impact(e, 0.5)
    assert new.valence > e.valence
    assert new.arousal >= e.arousal


def test_negative_impact_lowers_valence():
    e = EmotionState(valence=0.2)
    new = apply_event_impact(e, -0.5)
    assert new.valence < e.valence


def test_decay_returns_toward_baseline():
    e = EmotionState(valence=0.9, energy=0.95)
    after = e
    for _ in range(30):
        after = apply_decay(after, dt=1.0)
    assert abs(after.valence - BASELINES["valence"]) < abs(e.valence - BASELINES["valence"])
    assert abs(after.energy - BASELINES["energy"]) < abs(e.energy - BASELINES["energy"])


def test_clamp_emotion_bounds():
    e = EmotionState(energy=2.0, valence=-2.0, arousal=-0.5)
    e = clamp_emotion(e)
    assert 0.05 <= e.energy <= 1.0
    assert -1.0 <= e.valence <= 1.0
    assert 0.0 <= e.arousal <= 1.0


def test_praise_raises_valence_via_perception():
    p = Perception({})
    e = EmotionState(valence=0.0, security=0.5)
    impact = p.assess_impact("你真棒，谢谢你", e)
    assert impact > 0
    new = apply_event_impact(e, impact)
    new = p.apply_security_hint(new, impact)
    assert new.valence > e.valence


def test_cold_lowers_security():
    p = Perception({})
    e = EmotionState(valence=0.1, security=0.5)
    impact = p.assess_impact("烦", e)
    assert impact < 0
    new = apply_event_impact(e, impact)
    new = p.apply_security_hint(new, impact)
    assert new.security < e.security
