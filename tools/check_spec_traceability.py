#!/usr/bin/env python3
"""规格可追溯性自检：防止「包已标 ✅ 但过程稿缺失」的史料缺口。

设计目标（对齐 SDD-GUIDE §二「过程稿落盘归档不删」纪律）：
- 纯标准库、零新依赖，融入现有 Python CI。
- 扫描 docs/specs/tasks/*-主线.md 中标记为 ✅ 已验收的包，反查
  docs/specs/archive/ 下是否存在对应的 CodeBuddy 验收记录文件。
- 缺失即非零退出，便于 CI 门禁——把「人肉核对过程稿三件套」变成机器校验，
  防未来出现阶段零/一那种过程稿缺口。

判定规则：
- 主线包标题行形如「## 包 12：...✅ 已验收...」→ 视为已验收，须有验收记录。
- 验收记录文件：在 docs/specs/archive/ 任意子目录下递归搜
  「包{号}-PR方案-CodeBuddy验收记录.md」存在即过（不依赖目录命名规律）。
- 状态为 ⬜ / ⏸️ 阻塞 的包视为未完，不要求验收记录（跳过）。

用法：
    python tools/check_spec_traceability.py
    python tools/check_spec_traceability.py --specs docs/specs   # 指定根
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Windows GBK 控制台打印 ✅/❌ 会 UnicodeEncodeError；统一 UTF-8（errors=replace）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 主线文件匹配：docs/specs/tasks/*-主线.md
TASKS_GLOB = "*-主线.md"
# 包标题行：## 包 12：...  （允许「包 12」或「包 9b」）
PACKAGE_RE = re.compile(r"^##\s+包\s+([\w]+)\s*[：:]\s*(.*)$")
# 已验收标记
DONE_RE = re.compile(r"✅")
# 未完标记（跳过）
PENDING_RE = re.compile(r"[⬜⏸️]")
# 验收记录文件名模板
ACCEPTANCE_NAME = "包{no}-PR方案-CodeBuddy验收记录.md"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_accepted_packages(tasks_dir: Path) -> list[tuple[str, str, str]]:
    """返回 [(包号, 包标题, 主线文件相对路径)] 中所有已验收（✅）的包。"""
    out: list[tuple[str, str, str]] = []
    for task_file in sorted(tasks_dir.glob(TASKS_GLOB)):
        rel = str(task_file.relative_to(tasks_dir.parent.parent)).replace(os.sep, "/")
        try:
            lines = task_file.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for line in lines:
            m = PACKAGE_RE.match(line)
            if not m:
                continue
            pkg_no = m.group(1)
            title = m.group(2).strip()
            # 仅验收态纳入；跳过未完/阻塞
            if PENDING_RE.search(line):
                continue
            if not DONE_RE.search(line):
                continue
            out.append((pkg_no, title, rel))
    return out


def has_acceptance_record(pkg_no: str, archive_dir: Path) -> bool:
    """在 archive 下递归是否存在 包{no}-PR方案-CodeBuddy验收记录.md。"""
    target = ACCEPTANCE_NAME.format(no=pkg_no)
    if not archive_dir.exists():
        return False
    return any(archive_dir.rglob(target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check spec traceability (accepted packages have acceptance records).")
    parser.add_argument(
        "--specs",
        default=str(_repo_root() / "docs" / "specs"),
        help="docs/specs root (default: <repo>/docs/specs)",
    )
    args = parser.parse_args(argv)
    specs_root = Path(args.specs).resolve()
    tasks_dir = specs_root / "tasks"
    archive_dir = specs_root / "archive"

    if not tasks_dir.exists():
        print(f"[spec-trace] 错误：tasks 目录不存在 {tasks_dir}", file=sys.stderr)
        return 2

    accepted = find_accepted_packages(tasks_dir)
    if not accepted:
        print("[spec-trace] OK — 未发现已验收（✅）的包，无需校验。")
        return 0

    missing: list[tuple[str, str, str]] = []
    ok_list: list[tuple[str, str]] = []
    for pkg_no, title, src in accepted:
        if has_acceptance_record(pkg_no, archive_dir):
            ok_list.append((pkg_no, title))
        else:
            missing.append((pkg_no, title, src))

    print("=" * 64)
    print(f"[spec-trace] 已验收包 {len(accepted)} 个，溯源校验：")
    for pkg_no, _title in ok_list:
        print(f"  ✅ 包 {pkg_no}：验收记录存在")
    for pkg_no, _title, src in missing:
        print(f"  ❌ 包 {pkg_no}：缺验收记录（主线 {src} 标 ✅，但 archive 下无 "
              f"包{pkg_no}-PR方案-CodeBuddy验收记录.md）")
    print("=" * 64)

    if missing:
        print(f"[spec-trace] FAILED — {len(missing)} 个已验收包缺过程稿，违反 SDD-GUIDE 归档纪律。",
              file=sys.stderr)
        return 1
    print(f"[spec-trace] OK — 全部 {len(accepted)} 个已验收包均有验收记录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
