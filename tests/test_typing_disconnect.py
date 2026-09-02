"""P0 §〇.38：断线清 typing 源码契约。"""

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


def test_ws_close_clears_typing():
    src = USE_QI.read_text(encoding="utf-8")
    # close 回调内须清 typing（与 armTypingTimeout 配套）
    assert 'qiWs.on("close"' in src
    close_idx = src.index('qiWs.on("close"')
    chunk = src[close_idx : close_idx + 200]
    assert "setTyping(false)" in chunk
    assert "TYPING_TIMEOUT_MS = 60_000" in src
