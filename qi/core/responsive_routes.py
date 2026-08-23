"""L7 响应式路由优先级表（执行真源：`qi.core.dialogue_router`）。"""

from __future__ import annotations

from qi.core.dialogue_router import FALLTHROUGH, try_responsive_world_reach

ROUTE_ORDER: tuple[str, ...] = (
    "pending_confirmation",
    "assist_reexec",
    "look_pause",
    "look_resume",
    "irreversible",
    "delegate_search",
    "together",
    "write",
    "disk",
    "open",
    "look_invite",
    "assist",
    "dialogue_fallthrough",
)

execute_responsive_plan = try_responsive_world_reach

__all__ = ["FALLTHROUGH", "ROUTE_ORDER", "execute_responsive_plan"]
