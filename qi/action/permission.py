"""信任门控——行动的正当性来自关系，不来自能力。"""

from __future__ import annotations

from typing import Any

from qi.relationship.stages import stage_at_least

FRIEND_PLUS = ("friend", "bonded")


def can_share(relationship_stage: str) -> bool:
    """
    递出创作：friend+（与 L4 提起门槛一致；递出不得比提起更松）。
    stranger / acquaintance 不向对方递东西。
    """
    return relationship_stage in FRIEND_PLUS


def can_tend(_relationship_stage: str = "stranger") -> bool:
    """打理自己的世界：不触碰用户，不需信任门控（仍受 budget + season）。"""
    return True


def can_explore(_relationship_stage: str = "stranger") -> bool:
    """沉思式探索（为己）：不触碰用户，不需信任门控（仍受 budget + season）。"""
    return True


def can_archive(
    _relationship_stage: str = "stranger",
    scars: list[dict] | None = None,
) -> bool:
    """归档自己的叙事：自反动作，默认允许；伤疤可收紧。"""
    return scar_caution_multiplier("archive", scars) > 0


def can_budget_tune(
    _relationship_stage: str = "stranger",
    scars: list[dict] | None = None,
) -> bool:
    """自调行动权重：自反，默认允许。"""
    return scar_caution_multiplier("budget_tune", scars) > 0


def can_journal(
    _relationship_stage: str = "stranger",
    scars: list[dict] | None = None,
) -> bool:
    """写内在日记：自反，默认允许；仅应由 GWS/execute_kind 触发。"""
    return scar_caution_multiplier("journal", scars) > 0


def can_read_user_file(
    relationship_stage: str,
    trust: float = 0.5,
    scars: list[dict] | None = None,
) -> tuple[bool, bool]:
    """
    读用户文件：(allowed, needs_confirmation)。
    friend+ 允许但需确认。伤疤谨慎会收紧（见 scar_blocks_kind）。
    """
    _ = trust  # 预留：将来可用信任阈值微调
    if scar_blocks_kind("assist", scars):
        return False, True
    if stage_at_least(relationship_stage, "friend"):
        return True, True
    return False, True


def can_write_user_file(
    relationship_stage: str,
    trust: float = 0.5,
    scars: list[dict] | None = None,
) -> tuple[bool, bool]:
    """写用户文件：bonded 允许但需确认。"""
    _ = trust
    if scar_blocks_kind("assist", scars):
        return False, True
    if relationship_stage == "bonded":
        return True, True
    return False, True


def can_irreversible(
    relationship_stage: str = "bonded",
    trust: float = 1.0,
    scars: list[dict] | None = None,
) -> tuple[bool, bool]:
    """
    不可逆世界动作（发消息/花钱等）：永远 needs_confirmation=True，
    哪怕 bonded、信任再高。伤疤严重时 allowed=False。
    """
    _ = relationship_stage, trust
    if scar_blocks_kind("irreversible", scars):
        return False, True
    return True, True


def scar_blocks_kind(kind: str, scars: list[dict] | None) -> bool:
    """
    某类行动若曾造成未愈伤疤，把手缩回去（更谨慎 → 暂时不敢做）。
    伤疤复用 L5：origin_event 文本里带行动 kind 标记时命中。
    实际接线在 Step 5 留痕；此处只提供查询。
    """
    if not scars:
        return False
    marker = f"[action:{kind}]"
    for scar in scars:
        if scar.get("healed"):
            continue
        origin = str(scar.get("origin_event") or "")
        if marker in origin or f"行动:{kind}" in origin:
            return True
    return False


def scar_caution_multiplier(kind: str, scars: list[dict] | None) -> float:
    """
    0~1：伤疤对冲动的缩放。未愈同类伤疤 → 0（阻断）；
    已愈但仍有 behavioral_mark → 略降。默认 1.0。
    """
    if scar_blocks_kind(kind, scars):
        return 0.0
    if not scars:
        return 1.0
    marker = f"[action:{kind}]"
    for scar in scars:
        if not scar.get("healed"):
            continue
        origin = str(scar.get("origin_event") or "")
        if marker in origin or f"行动:{kind}" in origin:
            return 0.5
    return 1.0


# ---------------------------------------------------------------------------
# 行动失败三层（留痕规则；成功路径几乎不留疤）
#
# - failed_capability（搜不到、找不到）：老实说，不形成伤疤。
# - failed_judgment（做了但不该在这时给你看）：形成伤疤 → db.save_scar。
# - overstepped（做了不该做的事）：严重伤疤，与「在不该说话时说话」同级。
#
# 写入复用 Database.save_scar，不另造 API。实际伤疤接线在 Step 5。
# ---------------------------------------------------------------------------

OUTCOME_SUCCESS = "success"
OUTCOME_FAILED_CAPABILITY = "failed_capability"
OUTCOME_FAILED_JUDGMENT = "failed_judgment"
OUTCOME_OVERSTEPPED = "overstepped"


def outcome_creates_scar(outcome: str) -> bool:
    return outcome in (OUTCOME_FAILED_JUDGMENT, OUTCOME_OVERSTEPPED)


def permission_summary(
    relationship_stage: str,
    trust: float = 0.5,
    scars: list[dict] | None = None,
) -> dict[str, Any]:
    """调试/测试用：当前关系下各能力门控快照。"""
    read_ok, read_confirm = can_read_user_file(relationship_stage, trust, scars)
    write_ok, write_confirm = can_write_user_file(relationship_stage, trust, scars)
    irrev_ok, irrev_confirm = can_irreversible(relationship_stage, trust, scars)
    return {
        "share": can_share(relationship_stage),
        "tend": can_tend(relationship_stage),
        "explore": can_explore(relationship_stage),
        "archive": can_archive(relationship_stage, scars),
        "budget_tune": can_budget_tune(relationship_stage, scars),
        "journal": can_journal(relationship_stage, scars),
        "read_user_file": {"allowed": read_ok, "needs_confirmation": read_confirm},
        "write_user_file": {"allowed": write_ok, "needs_confirmation": write_confirm},
        "irreversible": {"allowed": irrev_ok, "needs_confirmation": irrev_confirm},
    }
