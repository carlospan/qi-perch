"""栖 · 运行时数据根（大厂方案：平台用户目录；开发旧仓兼容）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from qi import PROJECT_ROOT

ENV_DATA_DIR = "QI_DATA_DIR"

_LEGACY_MARKERS = (
    "qi.db",
    "user_secrets.env",
    "chroma",
    "settings.yaml",
    "checkpoint",
    "corpus",
)


def platform_data_root() -> Path:
    """平台默认用户数据目录（不含「是否已有旧仓」逻辑）。"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        return Path(base) / "Qi"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Qi"
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg:
        return Path(xdg) / "Qi"
    return Path.home() / ".local" / "share" / "Qi"


def legacy_repo_data() -> Path | None:
    """
    开发检出或已有运行产物的仓库旁 data/。
    空目录且非 pyproject 仓库（如未来安装根）不视为旧仓，以免挡住 AppData 默认。
    """
    d = PROJECT_ROOT / "data"
    if not d.is_dir():
        return None
    if (PROJECT_ROOT / "pyproject.toml").is_file():
        return d.resolve()
    if any((d / name).exists() for name in _LEGACY_MARKERS):
        return d.resolve()
    return None


def resolve_data_root() -> Path:
    """
    优先级：QI_DATA_DIR → 旧仓/开发 data/ → 平台默认。
    不自动 mkdir；调用方写入前自行 ensure。
    """
    env = (os.environ.get(ENV_DATA_DIR) or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    legacy = legacy_repo_data()
    if legacy is not None:
        return legacy
    return platform_data_root().resolve()


def ensure_data_root() -> Path:
    root = resolve_data_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def under_data(*parts: str | Path) -> Path:
    return resolve_data_root().joinpath(*[str(p) for p in parts])


def strip_data_prefix(rel: Path) -> Path:
    """配置里历史写法 data/qi.db → qi.db，避免 data_root/data/qi.db。"""
    parts = rel.parts
    if not parts:
        return Path()
    if parts[0] == "data":
        return Path(*parts[1:]) if len(parts) > 1 else Path()
    return rel


def resolve_under_data(configured: str | Path) -> Path:
    p = Path(configured).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (resolve_data_root() / strip_data_prefix(p)).resolve()


def open_data_folder(path: Path | None = None) -> tuple[bool, str]:
    """在本机文件管理器中打开数据根。返回 (ok, message)。"""
    root = path or resolve_data_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"无法创建数据目录：{e}"
    target = str(root)
    try:
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", target], check=False)
        else:
            subprocess.run(["xdg-open", target], check=False)
        return True, target
    except OSError as e:
        return False, f"打不开数据文件夹：{e}"
