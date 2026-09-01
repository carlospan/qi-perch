"""关于页 / 检查更新：常量与版本比对口径（与 about.ts 同构）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABOUT_TS = ROOT / "qi" / "embodiment" / "desktop" / "src" / "about.ts"
TAURI_CONF = ROOT / "qi" / "embodiment" / "desktop" / "src-tauri" / "tauri.conf.json"


def normalize_version(label: str) -> str:
    s = label.replace("（开发）", "")
    s = re.sub(r"\(dev(elopment)?\)", "", s, flags=re.I)
    s = re.sub(r"^v", "", s, flags=re.I)
    return s.strip()


def compare_versions(a: str, b: str) -> int:
    def parts(x: str) -> list[int]:
        out: list[int] = []
        for p in normalize_version(x).split("."):
            try:
                out.append(int(p))
            except ValueError:
                out.append(0)
        return out

    pa, pb = parts(a), parts(b)
    n = max(len(pa), len(pb))
    for i in range(n):
        da = pa[i] if i < len(pa) else 0
        db = pb[i] if i < len(pb) else 0
        if da != db:
            return da - db
    return 0


def test_desktop_package_and_tauri_version_aligned():
    desktop = ROOT / "qi" / "embodiment" / "desktop"
    pkg = json.loads((desktop / "package.json").read_text(encoding="utf-8"))
    tauri = json.loads((desktop / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    assert pkg["version"] == tauri["version"]
    assert pkg["version"]


def test_releases_and_latest_api_in_about_ts():
    about = ABOUT_TS.read_text(encoding="utf-8")
    assert "https://github.com/carlospan/qi-perch/releases" in about
    assert (
        "https://api.github.com/repos/carlospan/qi-perch/releases/latest" in about
    )
    assert "checkForUpdate" in about
    assert "normalizeVersion" in about


def test_csp_allows_github_api():
    conf = json.loads(TAURI_CONF.read_text(encoding="utf-8"))
    csp = conf["app"]["security"]["csp"]
    assert "https://api.github.com" in csp


def test_normalize_strips_dev_and_v():
    assert normalize_version("v0.1.1（开发）") == "0.1.1"
    assert normalize_version("0.1.1") == "0.1.1"


def test_compare_versions_ordering():
    assert compare_versions("0.1.2", "0.1.1") > 0
    assert compare_versions("0.1.1", "v0.1.1") == 0
    assert compare_versions("0.1.0", "0.1.1") < 0
    assert compare_versions("0.2", "0.1.9") > 0
