"""状态封存 / 迁移（阶段四·包 14）。

索引 + 关键状态；不重存整个 db。库内不终止进程。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from qi import PROJECT_ROOT
from qi.core.emotion import EmotionState
from qi.stasis.pressure import STASIS_INTENTS_KEY

logger = logging.getLogger("qi.stasis.checkpoint")

CHECKPOINT_VERSION = 1
DEFAULT_CHECKPOINT_DIR = PROJECT_ROOT / "data" / "checkpoint"
_CHECKPOINT_RE = re.compile(r"^checkpoint_\d{8}T\d{6}\.json$")


def default_checkpoint_dir() -> Path:
    return DEFAULT_CHECKPOINT_DIR


async def serialize_checkpoint(brain: Any) -> dict[str, Any]:
    """收集关键状态（非空壳）。"""
    now = datetime.now()
    db = getattr(brain, "_db", None)
    stasis_intents = None
    if db is not None:
        try:
            stasis_intents = await db.get_body_memory(STASIS_INTENTS_KEY)
        except Exception:
            logger.debug("读 stasis_intents 失败", exc_info=True)

    action_budget = None
    action = getattr(brain, "action", None)
    if action is not None and hasattr(action, "snapshot"):
        try:
            action_budget = action.snapshot()
        except Exception:
            logger.debug("读 action_budget 失败", exc_info=True)

    proactive = getattr(brain, "proactive", None)
    proactive_gate = None
    if proactive is not None and hasattr(proactive, "snapshot"):
        try:
            proactive_gate = proactive.snapshot()
        except Exception:
            logger.debug("读 proactive_gate 失败", exc_info=True)

    world = getattr(brain, "world", None)
    world_state = None
    if world is not None:
        if hasattr(world, "export_state"):
            world_state = world.export_state(now=now)
        elif hasattr(world, "snapshot"):
            world_state = world.snapshot(now=now)

    emotion = getattr(brain, "emotion", None)
    emotion_data = None
    if emotion is not None:
        emotion_data = emotion.model_dump(mode="json")

    ledger = getattr(brain, "ledger", None)
    ledger_data = ledger.snapshot() if ledger is not None else None

    return {
        "version": CHECKPOINT_VERSION,
        "ts": now.isoformat(timespec="seconds"),
        "emotion": emotion_data,
        "ledger": ledger_data,
        "world": world_state,
        "action_budget": action_budget,
        "proactive_gate": proactive_gate,
        "stasis_intents": stasis_intents,
        "starving": bool(getattr(ledger, "starving", False)) if ledger else False,
    }


async def write_checkpoint(
    brain: Any,
    dir_path: str | Path | None = None,
) -> Path:
    """序列化写 checkpoint_{ts}.json，返回路径。"""
    root = Path(dir_path) if dir_path is not None else default_checkpoint_dir()
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = root / f"checkpoint_{ts}.json"
    payload = await serialize_checkpoint(brain)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path.resolve()


def latest_checkpoint(dir_path: str | Path | None = None) -> Path | None:
    root = Path(dir_path) if dir_path is not None else default_checkpoint_dir()
    if not root.is_dir():
        return None
    files = [
        p for p in root.iterdir() if p.is_file() and _CHECKPOINT_RE.match(p.name)
    ]
    if not files:
        return None
    files.sort(key=lambda p: p.name)
    return files[-1].resolve()


async def restore_checkpoint(brain: Any, path: str | Path) -> bool:
    """读 JSON 重建内存态；损坏/缺失 → False。"""
    p = Path(path)
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False

    emo = data.get("emotion")
    if isinstance(emo, dict):
        try:
            brain.emotion = EmotionState.model_validate(emo)
        except Exception:
            logger.debug("restore emotion 失败", exc_info=True)
            return False

    ledger_data = data.get("ledger")
    if isinstance(ledger_data, dict) and getattr(brain, "ledger", None) is not None:
        brain.ledger.restore(ledger_data)
        if "starving" in data:
            brain.ledger.starving = bool(data["starving"])

    world_data = data.get("world")
    if isinstance(world_data, dict) and getattr(brain, "world", None) is not None:
        brain.world.restore(world_data)
        try:
            brain.last_world = brain.world.snapshot(now=datetime.now())
        except Exception:
            brain.last_world = world_data.get("view")

    action_budget = data.get("action_budget")
    action = getattr(brain, "action", None)
    if isinstance(action_budget, dict) and action is not None:
        if hasattr(action, "restore"):
            action.restore(action_budget)
        elif hasattr(action, "budget"):
            action.budget.restore(action_budget)

    proactive_gate = data.get("proactive_gate")
    proactive = getattr(brain, "proactive", None)
    if isinstance(proactive_gate, dict) and proactive is not None:
        proactive.restore(proactive_gate)

    db = getattr(brain, "_db", None)
    intents = data.get("stasis_intents")
    if db is not None and intents is not None:
        try:
            await db.set_body_memory(STASIS_INTENTS_KEY, intents)
        except Exception:
            logger.debug("restore stasis_intents 失败", exc_info=True)

    return True


async def restore_latest(
    brain: Any,
    dir_path: str | Path | None = None,
) -> bool:
    latest = latest_checkpoint(dir_path)
    if latest is None:
        return False
    return await restore_checkpoint(brain, latest)


def bind_cli_halt(on_halt: Callable[[], None] | None = None) -> Callable[[], None]:
    """CLI 用：默认进程退出；库内测试勿用。"""
    import sys

    def _halt() -> None:
        if on_halt is not None:
            on_halt()
        sys.exit(0)

    return _halt
