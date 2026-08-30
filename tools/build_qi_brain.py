#!/usr/bin/env python3
"""打 Windows 大脑 onedir（qi-brain），拷入 Tauri resources。

用法（仓库根、已装 qi 依赖的 Python）：
    python tools/build_qi_brain.py
    python tools/build_qi_brain.py --skip-install   # 已有 pyinstaller 时跳过 pip
    python tools/smoke_qi_brain.py                  # 证伪 WS 9527

产物：
    qi/embodiment/desktop/src-tauri/resources/qi-brain/qi-brain.exe
    （及同目录 _internal/ 等；勿提交，见 .gitignore）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "tools" / "qi_brain_entry.py"
DIST_NAME = "qi-brain"
PYI_DIST = ROOT / "dist" / DIST_NAME
TARGET = (
    ROOT
    / "qi"
    / "embodiment"
    / "desktop"
    / "src-tauri"
    / "resources"
    / "qi-brain"
)
_STRIP_DIR_NAMES = frozenset({"node_modules", "target", ".vite", "dist"})
# 大脑不需要前端树；若 collect-data 误带入则整棵丢掉
_STRIP_REL_TREES = (
    Path("qi") / "embodiment" / "desktop",
)


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def _strip_frontend_junk(root: Path) -> None:
    """qi/embodiment/desktop 在包树下，collect 时可能误带进前端垃圾。"""
    for rel in _STRIP_REL_TREES:
        for base in (root, root / "_internal"):
            victim = base / rel
            if victim.is_dir():
                print(f"剥离树：{victim}", flush=True)
                shutil.rmtree(victim, ignore_errors=True)
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and path.name in _STRIP_DIR_NAMES:
            print(f"剥离：{path}", flush=True)
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build qi-brain onedir for Tauri")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="不执行 pip install pyinstaller",
    )
    args = parser.parse_args()

    if not ENTRY.is_file():
        print(f"缺少入口：{ENTRY}", file=sys.stderr)
        return 1

    if not args.skip_install:
        _run([sys.executable, "-m", "pip", "install", "-q", "pyinstaller>=6.0"])

    # 清理旧产物，避免混进脏文件
    for stale in (ROOT / "build" / DIST_NAME, PYI_DIST, ROOT / f"{DIST_NAME}.spec"):
        if stale.is_dir():
            shutil.rmtree(stale)
        elif stale.is_file():
            stale.unlink()

    # 不用 --collect-all qi：会把 embodiment/desktop/node_modules 整棵拖进来
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            DIST_NAME,
            "--paths",
            str(ROOT),
            "--collect-submodules",
            "qi",
            "--collect-data",
            "qi",
            "--collect-all",
            "chromadb",
            "--collect-all",
            "onnxruntime",
            "--collect-all",
            "tokenizers",
            "--hidden-import",
            "aiosqlite",
            "--hidden-import",
            "websockets",
            "--hidden-import",
            "yaml",
            "--hidden-import",
            "rich",
            str(ENTRY),
        ]
    )

    exe = PYI_DIST / ("qi-brain.exe" if sys.platform == "win32" else "qi-brain")
    if not exe.is_file():
        print(f"PyInstaller 未产出：{exe}", file=sys.stderr)
        return 1

    _strip_frontend_junk(PYI_DIST)

    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PYI_DIST, TARGET)
    readme = TARGET / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# qi-brain\n\n由 `python tools/build_qi_brain.py` 生成；勿手改。\n",
            encoding="utf-8",
        )

    out_exe = TARGET / exe.name
    print(f"已写入：{out_exe}", flush=True)
    print("证伪：python tools/smoke_qi_brain.py", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
