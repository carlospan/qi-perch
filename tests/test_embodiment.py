"""Avatar 状态映射测试。"""

from datetime import datetime

from core.emotion import EmotionState
from embodiment.avatar.controller import AvatarController
from embodiment.avatar.states import Effect, Expression, Posture
from embodiment.voice.tts import emotion_to_voice_params


def test_idle_default():
    ctrl = AvatarController()
    e = EmotionState(valence=0.0, arousal=0.3, energy=0.6)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 7, 21, 14, 0))
    assert state.posture == Posture.IDLE
    assert state.expression == Expression.NEUTRAL
    assert state.effect == Effect.NONE


def test_talking_overrides():
    ctrl = AvatarController()
    ctrl.set_talking(True)
    e = EmotionState(valence=0.8, arousal=0.7, energy=0.7)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 7, 21, 14, 0))
    assert state.posture == Posture.TALKING


def test_thinking_and_sparkles():
    ctrl = AvatarController()
    ctrl.set_thinking(True)
    e = EmotionState(curiosity=0.8, valence=0.1, arousal=0.4, energy=0.6)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 7, 21, 14, 0))
    assert state.posture == Posture.THINKING
    assert state.expression == Expression.CURIOUS
    assert state.effect == Effect.THINKING_SPARKLES


def test_dreaming_sleep_and_bubbles():
    ctrl = AvatarController()
    e = EmotionState(energy=0.2, valence=0.0, arousal=0.1)
    state = ctrl.map_state(e, "dreaming", "winter", datetime(2026, 7, 21, 2, 0))
    assert state.posture == Posture.SLEEPING
    assert state.expression == Expression.SLEEPY
    assert state.effect == Effect.DREAM_BUBBLES


def test_happy_posture():
    ctrl = AvatarController()
    e = EmotionState(valence=0.7, arousal=0.5, energy=0.7)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 7, 21, 12, 0))
    assert state.posture == Posture.HAPPY
    assert state.expression == Expression.HAPPY


def test_season_effects_when_idle():
    ctrl = AvatarController()
    e = EmotionState(valence=0.0, arousal=0.2, energy=0.6)
    autumn = ctrl.map_state(e, "awake", "autumn", datetime(2026, 10, 1, 12, 0))
    winter = ctrl.map_state(e, "awake", "winter", datetime(2026, 12, 1, 12, 0))
    assert autumn.effect == Effect.SEASON_LEAVES
    assert winter.effect == Effect.SNOW


def test_voice_params_happy_faster():
    e = EmotionState(valence=0.8, arousal=0.7, energy=0.7)
    speed, pitch = emotion_to_voice_params(e)
    assert speed > 1.0
    assert pitch > 1.0
