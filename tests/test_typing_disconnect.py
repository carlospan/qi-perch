"""慢回复等待感：超时不解灭等待点；retract 重亮 typing。"""

from __future__ import annotations

from pathlib import Path

USE_QI = (
    Path(__file__).resolve().parents[1]
    / "qi"
    / "embodiment"
    / "desktop"
    / "src"
    / "composables"
    / "useQi.ts"
)


def test_typing_timeout_keeps_waiting_ui():
    src = USE_QI.read_text(encoding="utf-8")
    assert "TYPING_TIMEOUT_MS = 60_000" in src
    assert "composerUnlockedEarly" in src
    assert "composerBusy" in src
    # 超时只解输入强调，不 setTyping(false)
    arm = src.index("function armTypingTimeout")
    chunk = src[arm : arm + 450]
    assert "composerUnlockedEarly.value = true" in chunk
    assert "typing.value = false" not in chunk
    assert "TIMEOUT_NOTICE" in chunk


def test_speech_retract_rearms_typing():
    src = USE_QI.read_text(encoding="utf-8")
    arm = src.index("function applySpeechRetract")
    end = src.index("function retractActiveStreamBubble", arm)
    chunk = src[arm:end]
    assert "setTyping(true)" in chunk


def test_ws_close_clears_typing():
    src = USE_QI.read_text(encoding="utf-8")
    assert 'qiWs.on("close"' in src
    close_idx = src.index('qiWs.on("close"')
    chunk = src[close_idx : close_idx + 200]
    assert "setTyping(false)" in chunk
