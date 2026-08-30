"""配置加载：读取 settings，解析 ${ENV_VAR} 占位符。"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from qi import PROJECT_ROOT
from qi.paths import resolve_data_root, resolve_under_data

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_CONFIG_DIR = Path(__file__).resolve().parent
_RUNTIME_PATH_KEYS = (
    ("database", "path"),
    ("memory", "chroma_path"),
)


def _load_dotenv(path: Path | None = None) -> None:
    """轻量加载 .env（不覆盖已有环境变量）。无需额外依赖。"""
    env_path = path or (PROJECT_ROOT / ".env")
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


def user_config_candidates() -> list[Path]:
    """
    用户可改配置的查找顺序（先命中先生效）：
    1. 数据根 settings.yaml（与 qi.db 等同迁）
    2. ~/.qi/settings.yaml（机器级兼容）
    3. qi/config/settings.yaml（兼容旧布局）
    4. 仓库根 config/settings.yaml（更旧兼容）
    最后回退包内 settings.example.yaml（只读默认）。
    """
    return [
        resolve_data_root() / "settings.yaml",
        Path.home() / ".qi" / "settings.yaml",
        _CONFIG_DIR / "settings.yaml",
        PROJECT_ROOT / "config" / "settings.yaml",
        _CONFIG_DIR / "settings.example.yaml",
    ]


def _anchor_runtime_paths(config: dict) -> dict:
    """把配置里相对的 database/chroma 等锚定到当前数据根。"""
    for section, key in _RUNTIME_PATH_KEYS:
        bag = config.get(section)
        if not isinstance(bag, dict):
            continue
        raw = bag.get(key)
        if raw is None or raw == "":
            continue
        bag[key] = str(resolve_under_data(str(raw)))
    return config


def load_config(path: str | Path | None = None) -> dict:
    """
    加载栖的配置。
    默认按 user_config_candidates() 查找；显式 path 优先。
    """
    _load_dotenv()
    from qi.config.secrets import apply_secrets_to_environ, apply_user_llm_overrides

    apply_secrets_to_environ()

    if path is None:
        qcfg = os.environ.get("QI_CONFIG")
        if qcfg and Path(qcfg).is_file():
            path = Path(qcfg)
        else:
            candidates = user_config_candidates()
            path = next((c for c in candidates if c.exists()), candidates[-1])
    else:
        path = Path(path)

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    resolved = apply_user_llm_overrides(_walk_resolve(raw))
    return _anchor_runtime_paths(resolved)
