"""P2 连接失败排错：文案契约落在前端同源模块。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "qi" / "embodiment" / "desktop" / "src" / "connectionStatus.ts"


def test_offline_copy_strings_in_source():
    text = SRC.read_text(encoding="utf-8")
    assert "通道还没接上" in text
    assert "请确认栖后端在跑" in text
    assert "断了一下" in text
    assert "正在重连" in text
    assert 'kind === "reconnecting"' in text


def test_offline_kind_helper_in_source():
    text = SRC.read_text(encoding="utf-8")
    assert "offlineKindFromFlags" in text
    assert "everConnected" in text
