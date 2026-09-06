# -*- coding: utf-8 -*-
"""口型输出时钟契约：前端 speakClock 模块面检查（无浏览器）。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEAK = ROOT / "qi" / "embodiment" / "desktop" / "src" / "pet" / "speakClock.ts"
VRM = ROOT / "qi" / "embodiment" / "desktop" / "src" / "pet" / "usePetVrm.ts"


def test_speak_clock_module_api_surface():
    text = SPEAK.read_text(encoding="utf-8")
    assert "createSpeakClock" in text
    assert "pulse(" in text or "pulse(opts" in text
    assert "clear()" in text
    assert "tick(" in text
    assert "TTS" in text or "日后" in text
    assert "MOUTH_SHAPES" in text
    assert "vowelVisemeFromChar" in text
    assert "ATTACK" in text and "RELEASE" in text
    assert "text?" in text or "text?:" in text


def test_lock_mouth_deadlock_removed():
    text = VRM.read_text(encoding="utf-8")
    assert "lockMouth(" not in text
    assert "pulseSpeak" in text
    assert "clearSpeak" in text
    assert "applyMouthFromClock" in text
    assert "exaggerateMouthVisibility" in text
    assert "MOUTH_VISUAL_AMP" in text
    assert "createSpeakClock" in text


def test_vowel_viseme_heuristic_table_present():
    text = SPEAK.read_text(encoding="utf-8")
    assert "啊" in text and "OPEN_CHARS" in text
    assert "SOFT_CYCLE" in text
    assert "vowelVisemeFromChar" in text
