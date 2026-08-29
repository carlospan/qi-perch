"""用户密钥文件：设置页写入；不进 settings.yaml 明文。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from qi import PROJECT_ROOT

# 与 settings.yaml 里 ${ZHIPU_API_KEY} 兼容；同时认 QI_API_KEY
SECRET_API_KEY = "QI_API_KEY"
SECRET_API_KEY_ALIAS = "ZHIPU_API_KEY"
SECRET_BASE_URL = "QI_BASE_URL"
SECRET_MODEL = "QI_MODEL"

_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def user_secrets_path() -> Path:
    """仓库 data/ 下（已被 gitignore）；与库同迁。"""
    return PROJECT_ROOT / "data" / "user_secrets.env"


def read_secrets_file(path: Path | None = None) -> dict[str, str]:
    p = path or user_secrets_path()
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip().strip("'").strip('"')
        out[key] = val
    return out


def write_secrets_file(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    path: Path | None = None,
) -> Path:
    """合并写入；空字符串表示清除该可选字段。api_key=None 表示保留原值。"""
    p = path or user_secrets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = read_secrets_file(p)

    if api_key is not None:
        key = api_key.strip()
        if key:
            cur[SECRET_API_KEY] = key
            cur[SECRET_API_KEY_ALIAS] = key
        else:
            cur.pop(SECRET_API_KEY, None)
            cur.pop(SECRET_API_KEY_ALIAS, None)

    if base_url is not None:
        b = base_url.strip()
        if b:
            cur[SECRET_BASE_URL] = b
        else:
            cur.pop(SECRET_BASE_URL, None)

    if model is not None:
        m = model.strip()
        if m:
            cur[SECRET_MODEL] = m
        else:
            cur.pop(SECRET_MODEL, None)

    lines = [
        "# 栖 · 用户密钥（设置页写入；勿提交）",
        f"# path: {p}",
    ]
    for k in (
        SECRET_API_KEY,
        SECRET_API_KEY_ALIAS,
        SECRET_BASE_URL,
        SECRET_MODEL,
    ):
        if k in cur and cur[k]:
            lines.append(f"{k}={cur[k]}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def apply_secrets_to_environ(secrets: dict[str, str] | None = None) -> None:
    """写入进程环境（覆盖已有），供 load_config 展开 ${VAR}。

    若用户密钥文件存在且未含 API key，则清掉进程里的钥匙后再从 .env 回填
    （设置页清空 ≠ 禁止开发者用 .env）。
    """
    data = secrets if secrets is not None else read_secrets_file()
    file_exists = secrets is not None or user_secrets_path().is_file()

    for k, v in data.items():
        if v:
            os.environ[k] = v

    if not file_exists:
        return

    if SECRET_BASE_URL not in data or not data.get(SECRET_BASE_URL):
        os.environ.pop(SECRET_BASE_URL, None)
    if SECRET_MODEL not in data or not data.get(SECRET_MODEL):
        os.environ.pop(SECRET_MODEL, None)

    if not (data.get(SECRET_API_KEY) or data.get(SECRET_API_KEY_ALIAS)):
        os.environ.pop(SECRET_API_KEY, None)
        os.environ.pop(SECRET_API_KEY_ALIAS, None)
        _refill_api_keys_from_dotenv()


def _refill_api_keys_from_dotenv() -> None:
    """密钥文件未存 key 时，允许 .env 继续供开发使用。"""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    wanted = {SECRET_API_KEY, SECRET_API_KEY_ALIAS}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in wanted:
            continue
        value = value.strip().strip("'").strip('"')
        if key and value and key not in os.environ:
            os.environ[key] = value


def mask_api_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return "••••" + k[-2:]
    return k[:3] + "••••" + k[-4:]


def settings_llm_snapshot() -> dict:
    """给前端：不回传完整 key。"""
    data = read_secrets_file()
    key = (data.get(SECRET_API_KEY) or data.get(SECRET_API_KEY_ALIAS) or "").strip()
    # 也认进程环境（仅 .env、尚未写入 secrets 时）
    if not key:
        key = (
            os.environ.get(SECRET_API_KEY)
            or os.environ.get(SECRET_API_KEY_ALIAS)
            or ""
        ).strip()
    base = (data.get(SECRET_BASE_URL) or os.environ.get(SECRET_BASE_URL) or "").strip()
    model = (data.get(SECRET_MODEL) or os.environ.get(SECRET_MODEL) or "").strip()
    return {
        "has_key": bool(key),
        "api_key_masked": mask_api_key(key) if key else "",
        "base_url": base,
        "model": model,
    }


def apply_user_llm_overrides(config: dict) -> dict:
    """用 QI_BASE_URL / QI_MODEL / 密钥覆盖默认 provider。"""
    llm = config.setdefault("llm", {})
    name = str(llm.get("default_provider") or "zhipu")
    bag = llm.get("custom_providers") or llm.get("providers") or {}
    if not isinstance(bag, dict):
        return config
    # 确保写回 custom_providers
    providers = llm.setdefault("custom_providers", dict(bag) if bag else {})
    if name not in providers and bag:
        # 从 providers 拷一份
        src = bag.get(name)
        if isinstance(src, dict):
            providers[name] = dict(src)
    cfg = providers.get(name)
    if not isinstance(cfg, dict):
        cfg = {"base_url": "", "api_key": "", "models": {"fast": "gpt-4o-mini", "strong": "gpt-4o-mini"}}
        providers[name] = cfg

    key = (
        os.environ.get(SECRET_API_KEY)
        or os.environ.get(SECRET_API_KEY_ALIAS)
        or ""
    ).strip()
    if key:
        cfg["api_key"] = key

    base = (os.environ.get(SECRET_BASE_URL) or "").strip()
    if base:
        cfg["base_url"] = base

    model = (os.environ.get(SECRET_MODEL) or "").strip()
    if model:
        models = cfg.setdefault("models", {})
        if not isinstance(models, dict):
            models = {}
            cfg["models"] = models
        models["fast"] = model
        models["strong"] = model

    return config
