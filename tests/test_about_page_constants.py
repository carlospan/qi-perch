"""关于页版本解析（与前端 about.ts 同构口径，防漂移）。"""

from __future__ import annotations

import json
from pathlib import Path


def test_desktop_package_and_tauri_version_aligned():
    root = Path(__file__).resolve().parents[1]
    desktop = root / "qi" / "embodiment" / "desktop"
    pkg = json.loads((desktop / "package.json").read_text(encoding="utf-8"))
    tauri = json.loads(
        (desktop / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    assert pkg["version"] == tauri["version"]
    assert pkg["version"]  # 非空


def test_releases_url_constant_in_about_ts():
    about = (
        Path(__file__).resolve().parents[1]
        / "qi"
        / "embodiment"
        / "desktop"
        / "src"
        / "about.ts"
    ).read_text(encoding="utf-8")
    assert "https://github.com/carlospan/qi-perch/releases" in about
