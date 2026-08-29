"""情绪快照推送——可见变化才广播；约 1s 合并。"""

from __future__ import annotations

from typing import Any

# HITL：合并窗口约 1 秒
EMOTION_PUSH_DEBOUNCE_S = 1.0


def build_emotion_snapshot(brain: Any) -> dict:
    """与 /state 推送字段对齐。"""
    e = brain.emotion
    mode = (
        brain.public_mode()
        if hasattr(brain, "public_mode")
        else getattr(getattr(e, "mode", None), "value", "") or ""
    )
    return {
        "energy": e.energy,
        "valence": e.valence,
        "arousal": e.arousal,
        "security": e.security,
        "curiosity": e.curiosity,
        "attachment": e.attachment,
        "mode": mode,
        "stasis": bool(getattr(brain, "in_stasis", False)),
        "description": e.description(),
        "stage": getattr(brain, "relationship_stage", "") or "",
    }


def _round_num(v: Any) -> float | None:
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def emotion_snapshot_fingerprint(payload: dict) -> tuple:
    """可见变化指纹：数值两位小数 + 模式/描述/阶段。"""
    return (
        _round_num(payload.get("energy")),
        _round_num(payload.get("valence")),
        _round_num(payload.get("arousal")),
        _round_num(payload.get("security")),
        _round_num(payload.get("curiosity")),
        _round_num(payload.get("attachment")),
        str(payload.get("mode") or ""),
        bool(payload.get("stasis")),
        str(payload.get("description") or ""),
        str(payload.get("stage") or ""),
    )


def emotion_snapshot_changed(prev: dict | None, current: dict) -> bool:
    if prev is None:
        return True
    return emotion_snapshot_fingerprint(prev) != emotion_snapshot_fingerprint(current)
