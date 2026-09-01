#!/usr/bin/env python3
"""Windows 本机包装入口：检查资源 → 打脑（若缺）→ 默认拉 BGE → tauri build。

用法（仓库根）：
    python tools/pack_windows.py              # 正式推荐：默认带 BGE
    python tools/pack_windows.py --skip-bge   # 无网/证伪可跳过
    python tools/pack_windows.py --build-brain
    python tools/pack_windows.py --with-bge   # 兼容旧旗标（默认已带，等同无操作）

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
        help="兼容旧用法：正式包默认已带 BGE，此旗标可省略",
    )
    parser.add_argument(
        "--skip-bge",
        action="store_true",
        help="跳过 BGE（无网/快速证伪）；正式发版勿用",
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

    if args.skip_bge:
        if BGE_ONNX.is_file():
            print(f"OK BGE（已有，--skip-bge 未删除）：{BGE_ONNX.parent.parent}", flush=True)
        else:
            print(
                "已 --skip-bge：无离线 BGE，记忆检索将偏 n-gram（正式发版勿用此旗标）。",
                flush=True,
            )
    else:
        if not BGE_ONNX.is_file():
            print("未找到离线 BGE，开始 fetch（需网络；国内可设 HF_ENDPOINT）…", flush=True)
            try:
                _run([sys.executable, str(ROOT / "tools" / "fetch_bge_resource.py")])
            except subprocess.CalledProcessError as e:
                print(
                    "BGE fetch 失败。正式包默认须带 BGE。\n"
                    "  · 检查网络 / 设 HF_ENDPOINT=https://hf-mirror.com 后重试\n"
                    "  · 或显式：python tools/pack_windows.py --skip-bge",
                    file=sys.stderr,
                )
                return e.returncode or 1
        if not BGE_ONNX.is_file():
            print(
                f"fetch 后仍缺少 {BGE_ONNX}。\n"
                "正式包默认须带 BGE；或加 --skip-bge。",
                file=sys.stderr,
            )
            return 1
        print(f"OK BGE：{BGE_ONNX.parent.parent}", flush=True)
        if args.with_bge:
            print("（--with-bge 已兼容；默认行为即带 BGE）", flush=True)

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
