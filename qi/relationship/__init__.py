"""关系系统。"""

from __future__ import annotations

from typing import Any

__all__ = ["RelationshipEngine", "RelationshipState"]


def __getattr__(name: str) -> Any:
    # 惰性导出，避免 emotion→stages 时拉起 engine→perception→emotion 环
    if name in ("RelationshipEngine", "RelationshipState"):
        from qi.relationship.engine import RelationshipEngine, RelationshipState

        return {
            "RelationshipEngine": RelationshipEngine,
            "RelationshipState": RelationshipState,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
