#!/usr/bin/env python3
"""Windows 本机包装入口：检查资源 →（可选）打脑/拉 BGE → tauri build。

用法（仓库根）：
    python tools/pack_windows.py
    python tools/pack_windows.py --build-brain
    python tools/pack_windows.py --with-bge
    python tools/pack_windows.py --build-brain --with-bge

详见 docs/how-to/Windows安装包-本机证伪.md
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "qi" / "embodiment" / "desktop"
RESOURCES = DESKTOP / "src-tauri" / "resources"
BRAIN_EXE = RESOURCES / "qi-brain" / "qi-brain.exe"
BRAIN_ZIP = RESOURCES / "qi-brain.zip"
NUMPY_CORE = RESOURCES / "qi-brain" / "_internal" / "numpy" / "_core"
BGE_ONNX = (
    RESOURCES
    / "bge-small-zh-v1.5"
    / "onnx"
    / "model.onnx"
)


def _npm_cmd() -> list[str]:
    if sys.platform == "win32":
        return ["npm.cmd"]
    return ["npm"]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def main() -> int:
    if sys.platform != "win32":
        print("本脚本只用于 Windows 本机证伪。", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description="Pack Qi Windows installer (local)")
    parser.add_argument(
        "--build-brain",
        action="store_true",
        help="先运行 tools/build_qi_brain.py",
    )
    parser.add_argument(
        "--with-bge",
        action="store_true",
        help="包装前运行 tools/fetch_bge_resource.py（需网络）",
    )
    parser.add_argument(
        "--skip-tauri",
        action="store_true",
        help="只检查/准备资源，不跑 tauri build",
    )
    args = parser.parse_args()

    if args.build_brain or not BRAIN_EXE.is_file():
        if not BRAIN_EXE.is_file() and not args.build_brain:
            print(
                "缺少大脑 onedir\n请先：python tools/build_qi_brain.py\n"
                "或加 --build-brain",
                file=sys.stderr,
            )
            return 1
        _run([sys.executable, str(ROOT / "tools" / "build_qi_brain.py")])
    elif not BRAIN_ZIP.is_file():
        _run(
            [
                sys.executable,
                str(ROOT / "tools" / "build_qi_brain.py"),
                "--zip-only",
            ]
        )

    if not BRAIN_EXE.is_file():
        print(f"打脑后仍缺少：{BRAIN_EXE}", file=sys.stderr)
        return 1
    if not BRAIN_ZIP.is_file():
        print(f"打脑后仍缺少安装用 zip：{BRAIN_ZIP}", file=sys.stderr)
        return 1

    pyds = list(NUMPY_CORE.glob("_multiarray_umath*.pyd")) if NUMPY_CORE.is_dir() else []
    if not pyds:
        print(
            f"大脑 onedir 缺 numpy 扩展（{NUMPY_CORE}）。请重跑 build_qi_brain。",
            file=sys.stderr,
        )
        return 1

    print(f"OK 大脑：{BRAIN_EXE}", flush=True)
    print(f"OK 安装 zip：{BRAIN_ZIP}（{BRAIN_ZIP.stat().st_size / 1e6:.1f} MB）", flush=True)
    print(f"OK numpy：{pyds[0].name}", flush=True)

    if args.with_bge:
        _run([sys.executable, str(ROOT / "tools" / "fetch_bge_resource.py")])

    if BGE_ONNX.is_file():
        print(f"OK BGE：{BGE_ONNX.parent.parent}", flush=True)
    else:
        print(
            "提示：未找到离线 BGE（正式包建议 python tools/fetch_bge_resource.py）。"
            "本刀证伪可不带，记忆检索将偏 n-gram。",
            flush=True,
        )

    if args.skip_tauri:
        print("已跳过 tauri build（--skip-tauri）。", flush=True)
        return 0

    if not (DESKTOP / "node_modules").is_dir():
        _run([*_npm_cmd(), "install"], cwd=DESKTOP)

    _run([*_npm_cmd(), "run", "tauri:build"], cwd=DESKTOP)

    bundle = DESKTOP / "src-tauri" / "target" / "release" / "bundle"
    print(f"\n打包结束。请到目录找安装包：\n  {bundle}", flush=True)
    print("验收步骤见 docs/how-to/Windows安装包-本机证伪.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
