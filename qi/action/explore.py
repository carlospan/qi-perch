"""沉思式探索——contemplative drift，不是刷信息流。"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

# 多数拍不飘出去。curiosity 越高、季节越暖，越容易「看一眼」。
EXPLORE_BASE_PROBABILITY = 0.12

# 沙箱扫描：限深、限条；跳过体积大的向量目录
_SKIP_DIR_NAMES = frozenset({"chroma", ".git", "__pycache__", "node_modules"})
_MAX_ENTRIES = 24
_MAX_DEPTH = 2
_SECRET_KEY_FRAGMENTS = ("key", "token", "secret", "password", "api_key")


def resolve_sandbox_root(
    db: Database,
    config: dict | None = None,
) -> Path:
    """沙箱根：显式 config.action.sandbox 或数据库文件所在目录（通常即 data/）。"""
    action_cfg = (config or {}).get("action") or {}
    explicit = action_cfg.get("sandbox")
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    db_path = getattr(db, "db_path", None)
    if db_path:
        return Path(str(db_path)).expanduser().resolve().parent
    return Path("data").resolve()


def _scan_sandbox(root: Path) -> list[str]:
    """列目录/文件名（限深限条）；不读文件内容。"""
    if not root.is_dir():
        return []
    entries: list[str] = []

    def walk(current: Path, depth: int, prefix: str) -> None:
        if len(entries) >= _MAX_ENTRIES or depth > _MAX_DEPTH:
            return
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for child in children:
            if len(entries) >= _MAX_ENTRIES:
                return
            name = child.name
            rel = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
            if child.is_dir():
                if name.lower() in _SKIP_DIR_NAMES or name.startswith("."):
                    entries.append(f"{rel}/")
                    continue
                entries.append(f"{rel}/")
                walk(child, depth + 1, rel)
            else:
                entries.append(rel)

    walk(root, 0, "")
    return entries


def _config_key_names(root: Path) -> list[str]:
    """可选：读 settings*.yaml 的顶层键名（不读密钥值）。"""
    keys: list[str] = []
    for fname in ("settings.yaml", "settings.example.yaml"):
        path = root / fname
        if not path.is_file():
            # 沙箱常是 data/，配置可能在上一级
            alt = root.parent / fname
            path = alt if alt.is_file() else path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            if line[:1].isspace():
                continue
            key = stripped.split(":", 1)[0].strip()
            if not key or any(f in key.lower() for f in _SECRET_KEY_FRAGMENTS):
                continue
            if key not in keys:
                keys.append(key)
            if len(keys) >= 12:
                return keys
    return keys


class ExploreAction:
    """
    注意力偶然飘向自己的沙箱。
    红线：只陈述真实读到的条目；无内容则 found=None，绝不编造外面有什么。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
        *,
        base_probability: float = EXPLORE_BASE_PROBABILITY,
        config: dict | None = None,
    ):
        self.db = db
        self.narrative = narrative
        self.base_probability = base_probability
        self.config = config or {}

    async def drift(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        *,
        season_scale: float = 1.0,
        now: datetime | None = None,
        force: bool = False,
    ) -> dict | None:
        """
        返回 None 表示这拍没有飘出去（多数时候）。
        若飘出去：真读沙箱清单；空则 found=None。
        """
        now = now or datetime.now()
        if not force:
            # 好奇不够 → 不飘
            if curiosity < 0.65:
                return None
            warmth = max(0.0, (curiosity - 0.65) / 0.35)
            p = self.base_probability * max(0.0, season_scale) * (0.4 + 0.6 * warmth)
            if random.random() > p:
                return None

        root = resolve_sandbox_root(self.db, self.config)
        entries = _scan_sandbox(root)
        key_names = _config_key_names(root) if entries or root.is_dir() else []

        found: dict[str, Any] | None = None
        if entries:
            found = {
                "entries": entries[:_MAX_ENTRIES],
                "source": str(root),
            }
            if key_names:
                found["config_keys"] = key_names
            preview = "、".join(entries[:6])
            if len(entries) > 6:
                preview += "…"
            summary = f"我看了看自己这边的架子（{root.name}/）：{preview}。"
        else:
            summary = "我看了看自己的架子，空的。没有去查外面，也没有假装看见了什么。"

        emotion_ctx = None
        if emotion is not None and hasattr(emotion, "model_dump_json"):
            emotion_ctx = emotion.model_dump_json()

        action_id = await self.db.insert_action(
            "explore",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            emotion_context=emotion_ctx,
            season=season,
            now=now,
        )

        # 探索见闻不强制织叙事；只留 actions 痕迹
        _ = self.narrative

        return {
            "type": "explore_drift",
            "found": found,
            "summary": summary,
            "action_id": action_id,
            "season": season,
            "curiosity": curiosity,
            "sandbox": str(root),
        }
