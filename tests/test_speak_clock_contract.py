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
    # 日后 TTS 改接同一入口的契约说明
    assert "TTS" in text or "日后" in text
    assert "MOUTH_SHAPES" in text


def test_lock_mouth_deadlock_removed():
    text = VRM.read_text(encoding="utf-8")
    assert "lockMouth(" not in text
    assert "pulseSpeak" in text
    assert "clearSpeak" in text
    assert "applyMouthFromClock" in text
    assert "createSpeakClock" in text
