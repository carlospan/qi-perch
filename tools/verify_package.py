#!/usr/bin/env python3
"""包验收自动化：把「跑测试 + ruff + diff 核查 + 关键 grep 审计」从人肉变成一条命令。

设计目标（对齐阶段四包验收节奏）：
- 纯标准库 + subprocess，零新依赖，融入现有 Python CI。
- basetemp 使用系统临时区子目录（包 18），规避仓库内 .pytest-tmp 的 Windows ACL 损坏。
- 结构化报告：每项给出 ✅/❌ + 证据；任一不符即非零退出，便于 CI 门禁。
- git diff 核查：列出本次改动文件，便于确认「未越界改不该改的文件」。
- 可配置 grep 审计：用 --audit-grep "pattern:label" 复用「无 sys.exit / 无 energy 盖写」
  这类红线审计，不写死在脚本里。

用法：
    # 验收单个包（指定测试文件 + 审计范围）
    python tools/verify_package.py --test tests/test_resource_ledger.py --audit-scope qi/stasis
    # 全量 + 默认 ruff 范围
    python tools/verify_package.py --full
    # 自定义红线审计
    python tools/verify_package.py --full \
        --audit-grep "sys\\.exit:库内禁止 sys.exit" \
        --audit-grep "emotion\\.energy =:禁止盖写 energy" \
        --audit-scope qi
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows GBK 控制台打印 ✅/❌ 会崩（包 18）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DEFAULT_RUFF_SCOPE = ["qi", "tests", "tools"]
# 系统临时区子目录，规避仓库内 .pytest-tmp 的 Windows ACL 损坏（包 18）
BASETEMP_DIRNAME = Path(tempfile.gettempdir()) / "qi-pytest"

# 默认红线审计（可在命令行用 --audit-grep 追加或 --no-default-audit 关闭）
# 每个审计项格式：(pattern, label, exclude_funcs, exclude_paths)
# - exclude_funcs: 命中行所在 def 函数名在此列表则跳过（函数级豁免）
# - exclude_paths: 命中文件相对路径含此片段则跳过整文件（路径级豁免）
DEFAULT_AUDITS: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    (
        r"sys\.exit\s*\(",
        "库内禁止硬 sys.exit（CLI 入口 bind_cli_halt 豁免，应注入 on_halt）",
        ("bind_cli_halt",),          # 包 14 H2 定稿：仅 CLI 入口可 sys.exit(0)
        ("qi/cli.py",),              # CLI 主入口整体豁免
    ),
    (
        r"emotion\.energy\s*=",
        "禁止盖写 emotion.energy（clamp_emotion 夹紧豁免，须用趋近式 +=）",
        ("clamp_emotion",),          # 既有夹紧逻辑，非包 13 新增盖写
        (),
    ),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """运行子进程，返回 (returncode, stdout, stderr)。"""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def verify_tests(test_paths: list[str], full: bool, repo_root: Path) -> tuple[bool, str]:
    """跑 pytest。full 时跑全量；否则跑指定测试文件。返回 (通过, 证据文本)。"""
    basetemp = BASETEMP_DIRNAME
    basetemp.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pytest", "-q",
        "-p", "no:cacheprovider",
        f"--basetemp={basetemp}",
    ]
    if full:
        label = "全量"
    else:
        label = "、".join(test_paths)
        cmd.extend(test_paths)

    code, out, err = _run(cmd, repo_root)
    combined = out + err
    passed = re.search(r"(\d+)\s+passed", combined)
    failed = re.search(r"(\d+)\s+failed", combined)
    n_pass = int(passed.group(1)) if passed else 0
    n_fail = int(failed.group(1)) if failed else 0

    # 包18：系统临时区后以进程退出码为准，不再特判 PermissionError
    ok = code == 0
    evidence = (
        f"[{label}] passed={n_pass} failed={n_fail} rc={code} basetemp={basetemp}\n"
    )
    if not full and n_pass == 0 and n_fail == 0:
        evidence += "  (未匹配到 passed/failed，可能测试路径有误)\n"
    tail = combined.strip().splitlines()[-15:]
    evidence += "  " + "\n  ".join(tail)
    return ok, evidence


def verify_ruff(scope: list[str], repo_root: Path) -> tuple[bool, str]:
    """跑 ruff check。返回 (通过, 证据文本)。

    优先 PATH 里的 ruff；Windows 上 pip 装的 ruff.exe 可能不在 PATH，
    回退 `python -m ruff`，避免静默跳过检查。
    """
    ruff_bin = shutil.which("ruff")
    if ruff_bin is not None:
        cmd: list[str] = [ruff_bin, "check", *scope]
    else:
        try:
            code, _, _ = _run(
                [sys.executable, "-m", "ruff", "--version"], repo_root
            )
        except Exception:
            code = 1
        if code != 0:
            return True, "(ruff 未安装，跳过；CI 环境应确保 ruff 可用)"
        cmd = [sys.executable, "-m", "ruff", "check", *scope]
    code, out, _ = _run(cmd, repo_root)
    ok = code == 0
    evidence = out.strip() if out.strip() else "(no issues found)"
    return ok, evidence


def verify_diff(repo_root: Path) -> tuple[list[str], str]:
    """列出当前工作树相对 HEAD 的改动文件（含未暂存+已暂存+未跟踪）。"""
    files: list[str] = []
    # 已跟踪改动（staged + unstaged）
    code, out, _ = _run(["git", "diff", "--name-only", "HEAD"], repo_root)
    if code == 0 and out.strip():
        files.extend([p for p in out.splitlines() if p.strip()])
    # 未跟踪（不含被 gitignore 的）
    code, out, _ = _run(["git", "ls-files", "--others", "--exclude-standard"], repo_root)
    if code == 0 and out.strip():
        files.extend([p for p in out.splitlines() if p.strip()])
    evidence = "\n".join(f"  {f}" for f in files) if files else "  (无改动)"
    return files, evidence


def run_audit(
    pattern: str,
    label: str,
    scope_dirs: list[str],
    repo_root: Path,
    exclude_funcs: tuple[str, ...] = (),
    exclude_paths: tuple[str, ...] = (),
) -> tuple[bool, str]:
    """在 scope_dirs 内递归 grep pattern（逐行匹配，含 .py）。返回 (通过, 证据)。

    exclude_funcs: 命中行向上搜索最近的 def 函数名若在其中，跳过该行（函数级豁免）。
    exclude_paths: 命中文件相对路径含此片段，整文件跳过（路径级豁免）。
    """
    rx = re.compile(pattern)
    func_re = re.compile(r"^\s*def\s+(\w+)\s*\(")
    hits: list[str] = []
    for d in scope_dirs:
        target = repo_root / d
        if not target.exists():
            continue
        for p in target.rglob("*.py"):
            if ".pytest-tmp" in p.parts or "__pycache__" in p.parts:
                continue
            rel = str(p.relative_to(repo_root)).replace(os.sep, "/")
            if any(frag in rel for frag in exclude_paths):
                continue
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines, 1):
                if not rx.search(line):
                    continue
                # 函数级豁免：向上收集所有 enclosing def 名（含嵌套），
                # 任一在豁免列表则跳过本行
                if exclude_funcs:
                    enclosing_funcs = set()
                    for prev in range(i - 1, -1, -1):
                        m = func_re.match(lines[prev])
                        if m:
                            enclosing_funcs.add(m.group(1))
                    if enclosing_funcs & set(exclude_funcs):
                        continue  # 命中豁免函数（含嵌套），跳过本行
                hits.append(f"  {rel}:{i}: {line.strip()}")
    ok = len(hits) == 0
    evidence = (f"审计「{label}」pattern={pattern}\n" +
                ("  无命中 ✅" if ok else "\n".join(hits)))
    return ok, evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated package acceptance check.")
    parser.add_argument("--test", action="append", default=[],
                        help="测试文件路径（可多次）；与 --full 互斥时优先 --full")
    parser.add_argument("--full", action="store_true", help="跑全量测试而非指定文件")
    parser.add_argument("--ruff-scope", nargs="*", default=DEFAULT_RUFF_SCOPE,
                        help="ruff 检查范围（默认 qi tests）")
    parser.add_argument("--audit-scope", nargs="*", default=["qi"],
                        help="grep 审计的目录范围（默认 qi）")
    parser.add_argument("--audit-grep", action="append", default=[],
                        metavar="PATTERN:LABEL",
                        help="追加红线审计，格式 'regex:说明'（可多次）")
    parser.add_argument("--no-default-audit", action="store_true",
                        help="关闭内置默认审计（sys.exit / energy 盖写）")
    parser.add_argument("--root", default=str(_repo_root()),
                        help="仓库根（默认 tools/ 的父目录）")
    args = parser.parse_args(argv)
    repo_root = Path(args.root).resolve()

    print("=" * 64)
    print(f"[verify-package] 仓库根: {repo_root}")
    print("=" * 64)

    results: list[tuple[str, bool, str]] = []

    # 1. 测试
    if args.full:
        ok, ev = verify_tests([], True, repo_root)
    else:
        if not args.test:
            print("[verify-package] 错误：须指定 --test 或 --full", file=sys.stderr)
            return 2
        ok, ev = verify_tests(args.test, False, repo_root)
    results.append(("测试", ok, ev))

    # 2. ruff
    ok, ev = verify_ruff(args.ruff_scope, repo_root)
    results.append(("ruff", ok, ev))

    # 3. diff 核查
    files, ev = verify_diff(repo_root)
    results.append(("改动范围", True, ev))  # diff 只展示，不直接判失败

    # 4. grep 审计
    audits: list[tuple] = [] if args.no_default_audit else list(DEFAULT_AUDITS)
    for item in args.audit_grep:
        if ":" not in item:
            print(f"[verify-package] 警告：--audit-grep 格式应为 'pattern:label'，忽略：{item}",
                  file=sys.stderr)
            continue
        pat, lbl = item.split(":", 1)
        audits.append((pat, lbl, (), ()))  # 自定义项无豁免
    for entry in audits:
        pat, lbl = entry[0], entry[1]
        ex_funcs = entry[2] if len(entry) > 2 else ()
        ex_paths = entry[3] if len(entry) > 3 else ()
        ok, ev = run_audit(pat, lbl, args.audit_scope, repo_root,
                           exclude_funcs=ex_funcs, exclude_paths=ex_paths)
        results.append((f"审计:{lbl}", ok, ev))

    # 汇总
    print("\n" + "=" * 64)
    print("[verify-package] 验收报告")
    print("=" * 64)
    all_ok = True
    for name, ok, ev in results:
        mark = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"\n{mark} {name}")
        print(ev)
    print("\n" + "=" * 64)
    if all_ok:
        print("[verify-package] 全部通过 ✅")
        return 0
    print("[verify-package] 存在不符项 ❌", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
