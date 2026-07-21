"""配置加载：读取 settings.yaml，解析 ${ENV_VAR} 占位符。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path | None = None) -> None:
    """轻量加载 .env（不覆盖已有环境变量）。无需额外依赖。"""
    env_path = path or (_ROOT / ".env")
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_env(value: str) -> str:
    """把 ${VAR} 替换成环境变量值；未设置则替换为空串。"""

    def replacer(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return _ENV_PATTERN.sub(replacer, value)


def _walk_resolve(obj):
    if isinstance(obj, dict):
        return {k: _walk_resolve(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_resolve(v) for v in obj]
    if isinstance(obj, str):
        return _resolve_env(obj)
    return obj


def load_config(path: str | Path | None = None) -> dict:
    """
    加载栖的配置。
    默认读项目根目录下的 config/settings.yaml；
    若不存在，回退到 settings.example.yaml。
    """
    _load_dotenv()

    if path is None:
        candidate = _ROOT / "config" / "settings.yaml"
        if not candidate.exists():
            candidate = _ROOT / "config" / "settings.example.yaml"
        path = candidate
    else:
        path = Path(path)

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return _walk_resolve(raw)
