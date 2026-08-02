#!/usr/bin/env python3
"""异时测试骨架 CLI：对比两版经验回放语料（不训练）。

用法：
    python tools/replay_drift_check.py --a path/to/corpus_a.jsonl --b path/to/corpus_b.jsonl

真训练后的响应漂移对比可复用 qi.learning.drift_check（届时喂模型输出）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让仓库根可 import qi
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qi.learning.drift_check import diff_versions, format_diff_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two replay corpus versions (no training)."
    )
    parser.add_argument("--a", required=True, help="Path to corpus A jsonl")
    parser.add_argument("--b", required=True, help="Path to corpus B jsonl")
    args = parser.parse_args(argv)
    report = diff_versions(args.a, args.b)
    print(format_diff_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
