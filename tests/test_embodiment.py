"""Avatar 状态映射 + 具身绑定安全测试。"""

from datetime import datetime

from qi.core.emotion import EmotionState
from qi.embodiment.avatar.controller import AvatarController
from qi.embodiment.avatar.states import Effect, Expression, Posture
from qi.embodiment.server import (
    WS_ALLOWED_ORIGINS,
    WS_HOST,
    WS_PORT,
    resolve_bind,
)
from qi.embodiment.voice.tts import emotion_to_voice_params


def test_resolve_bind_defaults_and_loopback():
    assert resolve_bind(None, None) == (WS_HOST, WS_PORT)
    assert resolve_bind("localhost", 9527) == ("localhost", 9527)
    assert resolve_bind("::1", "9528") == ("::1", 9528)


def test_resolve_bind_rejects_non_loopback():
    assert resolve_bind("0.0.0.0", 9527) == (WS_HOST, WS_PORT)
    assert resolve_bind("192.168.1.10", 80) == (WS_HOST, 80)


def test_ws_allowed_origins_cover_dev_and_tauri():
    assert "http://localhost:5173" in WS_ALLOWED_ORIGINS
    assert "https://tauri.localhost" in WS_ALLOWED_ORIGINS
    assert None in WS_ALLOWED_ORIGINS  # 本机非浏览器客户端


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
    assert state.expression == Expression.SOFT_SMILE
    assert state.effect == Effect.THINKING_SPARKLES


def test_curious_only_when_valence_negative():
    ctrl = AvatarController()
    e = EmotionState(valence=-0.15, curiosity=0.85, arousal=0.4, energy=0.6)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 8, 26, 0, 0))
    assert state.expression == Expression.CURIOUS


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


def test_positive_valence_prefers_smile_over_curious():
    """心情尚可时 curious 不应压过 soft_smile（相处页 VRM 观感）。"""
    ctrl = AvatarController()
    e = EmotionState(valence=0.45, curiosity=0.85, arousal=0.55, energy=0.6)
    state = ctrl.map_state(e, "awake", "spring", datetime(2026, 8, 25, 14, 0))
    assert state.expression == Expression.SOFT_SMILE

    e2 = EmotionState(valence=0.1, curiosity=0.85, arousal=0.4, energy=0.6)
    state2 = ctrl.map_state(e2, "awake", "spring", datetime(2026, 8, 26, 0, 0))
    assert state2.expression == Expression.SOFT_SMILE


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
