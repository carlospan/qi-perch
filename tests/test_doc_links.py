"""钉死 docs 链接检查器的解析规则（对齐方案 v2 §5.2）。

复用 tools/check_doc_links.check，不另写一套逻辑。
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# 让 tests/ 能 import tools/
import sys

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import check_doc_links as cdl  # noqa: E402


# ---------------------------------------------------------------------------
# 1. 文件相对 ./ ../ （含中文名）
# ---------------------------------------------------------------------------

def test_relative_parent(tmp_path: Path):
    # docs/a/中文.md 链 ../b/target.md
    (tmp_path / "docs" / "a").mkdir(parents=True)
    (tmp_path / "docs" / "b").mkdir()
    (tmp_path / "docs" / "b" / "target.md").write_text("# t", encoding="utf-8")
    src = tmp_path / "docs" / "a" / "中文.md"
    src.write_text("见 [目标](../b/target.md)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


def test_relative_parent_dead(tmp_path: Path):
    (tmp_path / "docs" / "a").mkdir(parents=True)
    src = tmp_path / "docs" / "a" / "中文.md"
    src.write_text("见 [目标](../b/missing.md)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == [(1, "../b/missing.md")]


def test_current_dir_prefix(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("# x", encoding="utf-8")
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 [x](./x.md)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 2. 仓库根相对 docs/、qi/
# ---------------------------------------------------------------------------

def test_root_rel_docs(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ref.md").write_text("# r", encoding="utf-8")
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 [r](docs/ref.md)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


def test_root_rel_docs_dead(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 [r](docs/missing.md)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == [(1, "docs/missing.md")]


def test_root_rel_qi(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "qi" / "pkg").mkdir(parents=True)
    (tmp_path / "qi" / "pkg" / "mod.py").write_text("#", encoding="utf-8")
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 [m](qi/pkg/mod.py)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 3. 目录链接（layers/）存在即过
# ---------------------------------------------------------------------------

def test_directory_link(tmp_path: Path):
    (tmp_path / "docs" / "reference" / "layers").mkdir(parents=True)
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 [层](docs/reference/layers/)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 4. 跳过项：http(s)/mailto/纯 #fragment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "link",
    [
        "[ext](https://openai.com/docs)",
        "[mail](mailto:a@b.com)",
        "[anchor](#section-1)",
    ],
)
def test_skip_external_and_anchor(tmp_path: Path, link: str):
    (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "index.md"
    src.write_text(f"见 {link}", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 5. 假阳性防护：fenced / 行内 code 不扫
# ---------------------------------------------------------------------------

def test_skip_fenced_code(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "index.md"
    content = textwrap.dedent(
        """
        text

        ```python
        path = (docs/design/old.md)
        ```
        """
    )
    src.write_text(content, encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


def test_skip_inline_code(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    src = tmp_path / "docs" / "index.md"
    src.write_text("见 `docs/design/old.md` 这样的代码", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 6. 图片链接 ![alt](path)
# ---------------------------------------------------------------------------

def test_image_link(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "img").mkdir()
    (tmp_path / "docs" / "img" / "a.png").write_text("x", encoding="utf-8")
    src = tmp_path / "docs" / "index.md"
    src.write_text("![图](docs/img/a.png)", encoding="utf-8")
    assert cdl.check_file(src, tmp_path) == []


# ---------------------------------------------------------------------------
# 7. archive 排除 + 噪音目录排除（collect 层）
# ---------------------------------------------------------------------------

def test_archive_excluded(tmp_path: Path):
    (tmp_path / "docs" / "specs" / "archive").mkdir(parents=True)
    (tmp_path / "docs" / "specs" / "archive" / "old.md").write_text(
        "见 [dead](docs/design/gone.md)", encoding="utf-8"
    )
    files = cdl.collect_md_files(tmp_path)
    rels = [str(f.relative_to(tmp_path)).replace("\\", "/") for f in files]
    assert not any(r.startswith("docs/specs/archive/") for r in rels)


def test_noise_dir_excluded(tmp_path: Path):
    (tmp_path / "qi" / "pkg" / "node_modules" / "x").mkdir(parents=True)
    (tmp_path / "qi" / "pkg" / "node_modules" / "x" / "README.md").write_text(
        "见 [dead](../../missing.md)", encoding="utf-8"
    )
    (tmp_path / "qi" / "pkg" / "README.md").write_text("ok", encoding="utf-8")
    files = cdl.collect_md_files(tmp_path)
    rels = [str(f.relative_to(tmp_path)).replace("\\", "/") for f in files]
    assert not any("node_modules" in r for r in rels)
    assert any(r == "qi/pkg/README.md" for r in rels)


# ---------------------------------------------------------------------------
# 8. 集成测：对真实仓库跑一遍，必须无死链
# ---------------------------------------------------------------------------

def test_integration_repo_clean():
    repo_root = TOOLS_DIR.parent
    results = cdl.check(repo_root)
    assert results == [], "\n".join(
        f"{str(f.relative_to(repo_root)).replace(chr(92), '/')}:{ln}:{t}"
        for f, dead in results
        for ln, t in dead
    )
