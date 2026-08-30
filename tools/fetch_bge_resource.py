#!/usr/bin/env python3
"""把 BGE ONNX 拉到 Tauri 资源目录（权重不入库）。

用法（仓库根；需网络，国内可设 HF_ENDPOINT）：
    python tools/fetch_bge_resource.py
    $env:HF_ENDPOINT="https://hf-mirror.com"; python tools/fetch_bge_resource.py

产物：
    qi/embodiment/desktop/src-tauri/resources/bge-small-zh-v1.5/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = (
    ROOT
    / "qi"
    / "embodiment"
    / "desktop"
    / "src-tauri"
    / "resources"
    / "bge-small-zh-v1.5"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch BGE ONNX into Tauri resources")
    parser.add_argument(
        "--dir",
        type=Path,
        default=TARGET,
        help=f"目标目录（默认 {TARGET}）",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from qi.memory.vector_store import ensure_bge_model

    dest = args.dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    print(f"下载到 {dest} …", flush=True)
    ensure_bge_model(dest)
    print("完成。可离线；勿 git add 权重文件。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
