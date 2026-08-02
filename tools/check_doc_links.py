#!/usr/bin/env python3
"""检查仓库内 Markdown 文档的本地相对链接是否有效（死链扫描）。

设计目标（对齐 docs 体系重构 CI 化方案 v2）：
- 纯标准库、零新依赖，融入现有 Python CI。
- 支持中文路径（pathlib + NFC 归一）。
- 区分「仓库根相对」(docs/、qi/、仓库根文件名) 与「文件相对」(./、../)。
- 跳过 fenced/inline code、http(s)/mailto、纯 #fragment。
- 目标为 .md/.yaml/.py/目录 均「存在即过」。
- 输出 `文件:行号:链接`，发现死链则非零退出，便于 CI 门禁。

用法：
    python tools/check_doc_links.py            # 扫描默认范围
    python tools/check_doc_links.py --root .   # 指定仓库根
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 强校验的扫描根（相对仓库根）
SCAN_ROOTS = ["docs", "README.md", "qi"]

# 强校验排除（Glob 风格前缀，相对仓库根）；archive 史料故意留旧路径，不验
EXCLUDE_PREFIXES = [
    "docs/specs/archive/",
]

# 噪音目录：第三方依赖 / VCS / 缓存，不扫
NOISE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

# 显式跳过文件（机制预留；当前为空——重构已清残留旧路径）
SKIP_FILES: list[str] = []

# 仓库根相对链接的裸前缀判定
ROOT_REL_PREFIXES = ("docs/", "qi/")

# 视为「目标存在即过」的扩展名（目录无扩展名也过）
ALLOWED_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".txt", ".json", ".png", ".html"}

# 行内链接：[text](target) 或 [text](target "title")
# 注意：先剥离 code，再匹配，避免误报。
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# fenced code block：``` ... ```
FENCE_RE = re.compile(r"^\s*```")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
# 图片 ![alt](path)
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _strip_inline_code(line: str) -> str:
    """移除行内 code，避免其中的伪链接被扫到。"""
    return INLINE_CODE_RE.sub("", line)


def _resolve_target(src_file: Path, target: str, repo_root: Path) -> Path | None:
    """将链接 target 解析为仓库内绝对路径；无法判定返回 None（跳过）。"""
    # 解码 %XX（中文路径偶发）
    raw = target.split("#")[0].split("?")[0]
    if not raw:
        return None
    raw = _nfc(raw)
    try:
        raw = bytes(raw, "utf-8").decode("utf-8")
    except Exception:
        pass
    # 移除可能的 url 编码
    raw = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), raw)

    # 跳过外部 / 协议链接 / 纯锚点
    if raw.startswith(("http://", "https://", "mailto:", "ftp://")):
        return None
    if raw.startswith("#"):
        return None

    # 仓库根相对：裸 docs/、qi/ 前缀，或仓库根存在的文件名
    if raw.startswith(ROOT_REL_PREFIXES):
        candidate = repo_root / raw
        return candidate
    # 仓库根文件名（如 README.md、LICENSE）
    if (repo_root / raw).is_file() or (repo_root / raw).is_dir():
        return repo_root / raw

    # 文件相对：./ ../ 或裸相对（相对当前 md 所在目录）
    if raw.startswith(("./", "../")) or not raw.startswith("/"):
        candidate = (src_file.parent / raw).resolve()
        return candidate

    return None


def _exists(target: Path) -> bool:
    if target is None:
        return False
    p = target
    # 目录或已知扩展名文件存在即过
    if p.is_dir():
        return True
    if p.is_file():
        return True
    # 容忍无扩展名目标：若去掉扩展名后文件存在也放过（保守）
    return False


def check_file(src_file: Path, repo_root: Path) -> list[tuple[int, str]]:
    """返回该文件的死链列表 [(行号, 链接)]。"""
    dead: list[tuple[int, str]] = []
    in_fence = False
    try:
        text = src_file.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return dead

    for lineno, line in enumerate(text.splitlines(), start=1):
        # fenced code 切换
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # 移除行内 code 再扫
        cleaned = _strip_inline_code(line)
        # 图片与行内链接一网打尽
        for m in list(IMG_RE.finditer(cleaned)) + list(LINK_RE.finditer(cleaned)):
            target = m.group(1)
            resolved = _resolve_target(src_file, target, repo_root)
            if resolved is None:
                continue  # 外部/锚点/不可判定 → 跳过
            if not _exists(resolved):
                dead.append((lineno, target))
    return dead


def collect_md_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    # README.md at root
    for name in SCAN_ROOTS:
        p = repo_root / name
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
    # qi/**/README.md
    qi_readmes = sorted((repo_root / "qi").rglob("README.md")) if (repo_root / "qi").is_dir() else []
    files.extend(qi_readmes)
    # 过滤噪音目录
    files = [f for f in files if not any(part in NOISE_DIRS for part in f.parts)]
    # 去重 + 排除 archive + SKIP_FILES
    seen = set()
    out = []
    for f in files:
        try:
            rel = str(f.relative_to(repo_root)).replace(os.sep, "/")
        except ValueError:
            continue
        if rel in seen:
            continue
        seen.add(rel)
        if any(rel.startswith(ex) for ex in EXCLUDE_PREFIXES):
            continue
        if rel in SKIP_FILES:
            continue
        out.append(f)
    return out


def check(repo_root: Path) -> list[tuple[Path, list[tuple[int, str]]]]:
    """入口：扫描全部文件，返回 [(文件, 死链列表)]。供 CLI 与测试复用。"""
    results = []
    for f in collect_md_files(repo_root):
        dead = check_file(f, repo_root)
        if dead:
            results.append((f, dead))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local markdown links in repo.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository root (default: parent of tools/)",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.root).resolve()

    results = check(repo_root)
    if not results:
        print(f"[doc-link-check] OK — no dead links under {repo_root}")
        return 0

    print("[doc-link-check] FAILED — dead links found:")
    for f, dead in results:
        rel = str(f.relative_to(repo_root)).replace(os.sep, "/")
        for lineno, target in dead:
            print(f"  {rel}:{lineno}: {target}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
