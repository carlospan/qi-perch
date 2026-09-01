#!/usr/bin/env python3
"""打 Windows 大脑 onedir + 安装用 zip，写入 Tauri resources。

用法（仓库根、已装 qi 依赖的 Python）：
    python tools/build_qi_brain.py
    python tools/build_qi_brain.py --skip-install   # 已有 pyinstaller 时跳过 pip
    python tools/smoke_qi_brain.py                  # 证伪 WS 9527（用 onedir）

产物：
    …/resources/qi-brain/          onedir（本机 smoke / tauri:dev）
    …/resources/qi-brain.zip       安装包资源（单文件，壳首次解压）
    （勿提交，见 .gitignore）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "tools" / "qi_brain_entry.py"
DIST_NAME = "qi-brain"
PYI_DIST = ROOT / "dist" / DIST_NAME
RESOURCES = (
    ROOT
    / "qi"
    / "embodiment"
    / "desktop"
    / "src-tauri"
    / "resources"
)
TARGET = RESOURCES / "qi-brain"
ZIP_TARGET = RESOURCES / "qi-brain.zip"
# 安装包只打 zip（避免 NSIS 逐文件拷贝数千路径落半套）；onedir 留给本机 smoke / tauri:dev
_STRIP_DIR_NAMES = frozenset({"node_modules", "target", ".vite", "dist"})
# 大脑不需要前端树；若 collect-data 误带入则整棵丢掉
_STRIP_REL_TREES = (
    Path("qi") / "embodiment" / "desktop",
)
_NUMPY_PYD_PREFIX = "_multiarray_umath"
_NUMPY_PYD_SUFFIX = ".pyd"


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


def _numpy_core_dir(root: Path) -> Path | None:
    for candidate in (
        root / "_internal" / "numpy" / "_core",
        root / "numpy" / "_core",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _numpy_umath_pyd(root: Path) -> Path | None:
    core = _numpy_core_dir(root)
    if core is None:
        return None
    for path in core.iterdir():
        name = path.name
        if (
            path.is_file()
            and name.startswith(_NUMPY_PYD_PREFIX)
            and name.endswith(_NUMPY_PYD_SUFFIX)
        ):
            return path
    return None


def _write_zip(src_dir: Path, zip_path: Path) -> None:
    """把 onedir 打成单文件，供 NSIS 可靠落盘。"""
    if zip_path.is_file():
        zip_path.unlink()
    print(f"压缩：{src_dir} → {zip_path}", flush=True)
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir).as_posix())
    mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"zip 完成：{zip_path}（{mb:.1f} MB）", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build qi-brain onedir for Tauri")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="不执行 pip install pyinstaller",
    )
    parser.add_argument(
        "--zip-only",
        action="store_true",
        help="仅把已有 onedir 打成 qi-brain.zip（不跑 PyInstaller）",
    )
    args = parser.parse_args()

    if args.zip_only:
        if not (TARGET / ("qi-brain.exe" if sys.platform == "win32" else "qi-brain")).is_file():
            print(f"缺少 onedir：{TARGET}，不能 --zip-only", file=sys.stderr)
            return 1
        if _numpy_umath_pyd(TARGET) is None:
            print("onedir 缺 numpy 扩展，请完整重打脑", file=sys.stderr)
            return 1
        _write_zip(TARGET, ZIP_TARGET)
        print(f"已写入：{ZIP_TARGET}", flush=True)
        return 0

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
            "--noconsole",
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
            "numpy",
            "--collect-all",
            "onnxruntime",
            "--collect-all",
            "tokenizers",
            "--hidden-import",
            "numpy",
            "--hidden-import",
            "numpy._core",
            "--hidden-import",
            "numpy._core._multiarray_umath",
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

    # 安装态硬门槛：numpy 扩展必须在（.pyd，不只是目录）
    if _numpy_core_dir(PYI_DIST) is None:
        print(
            "打脑产物缺 numpy._core。请检查 PyInstaller/numpy 版本。",
            file=sys.stderr,
        )
        return 1
    pyd = _numpy_umath_pyd(PYI_DIST)
    if pyd is None:
        print(
            "打脑产物缺 numpy._core._multiarray_umath*.pyd。",
            file=sys.stderr,
        )
        return 1
    print(f"OK numpy 扩展：{pyd.name}", flush=True)

    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PYI_DIST, TARGET)
    readme = TARGET / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# qi-brain\n\n由 `python tools/build_qi_brain.py` 生成；勿手改。\n"
            "安装包使用同级 `qi-brain.zip`（单文件），壳首次启动解压到用户数据目录。\n",
            encoding="utf-8",
        )

    _write_zip(TARGET, ZIP_TARGET)
    # 二次确认 zip 内含关键扩展
    with zipfile.ZipFile(ZIP_TARGET, "r") as zf:
        names = zf.namelist()
    needle = "numpy/_core/"
    if not any(needle in n.replace("\\", "/") and n.endswith(".pyd") for n in names):
        print("qi-brain.zip 内缺少 numpy/_core/*.pyd", file=sys.stderr)
        return 1

    out_exe = TARGET / exe.name
    print(f"已写入：{out_exe}", flush=True)
    print(f"已写入：{ZIP_TARGET}", flush=True)
    print("证伪：python tools/smoke_qi_brain.py", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
