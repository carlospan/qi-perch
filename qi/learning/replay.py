"""经验回放：从 broadcast_traces 按显著性筛选 → 结构化语料样本。

训练 step 默认 dry_run 隔离；不依赖 LLM。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("qi.learning.replay")

# 动机旁路辅助门槛（与 winner_salience floor 取 OR）
_CURIOSITY_FLOOR = 0.7
_WORLD_SURPRISE_FLOOR = 1.0
_PRIORITY_KINDS = frozenset(
    {
        "curiosity",
        "close_loop",
        "proactive:express_feeling",
        "proactive:check_in",
        "proactive:reach_out",
    }
)


def _motive_curiosity(motive: dict | None) -> float:
    if not isinstance(motive, dict):
        return 0.0
    try:
        return float(motive.get("curiosity") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _motive_world_surprise(motive: dict | None) -> float:
    if not isinstance(motive, dict):
        return 0.0
    try:
        return float(motive.get("world_surprise") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _is_priority_kind(kind: str | None) -> bool:
    if not kind:
        return False
    if kind in _PRIORITY_KINDS:
        return True
    return kind.startswith("proactive:")


def _passes_filter(
    row: dict,
    *,
    salience_floor: float,
) -> bool:
    """salience≥floor，或 curiosity / world_surprise 旁路过阈；优先 kind 只影响排序。"""
    sal = float(row.get("winner_salience") or 0.0)
    if sal >= salience_floor:
        return True
    motive = row.get("motive") if isinstance(row.get("motive"), dict) else {}
    if _motive_curiosity(motive) >= _CURIOSITY_FLOOR:
        return True
    if _motive_world_surprise(motive) >= _WORLD_SURPRISE_FLOOR:
        return True
    return False


def _sort_key(row: dict) -> tuple:
    """salience 降序；同 salience 时优先 curiosity/close_loop/proactive。"""
    sal = float(row.get("winner_salience") or 0.0)
    kind = str(row.get("winner_kind") or "")
    priority = 1 if _is_priority_kind(kind) else 0
    return (-sal, -priority, -int(row.get("beat") or 0))


class ReplayBuffer:
    """显著性筛选 + 样本结构化；训练默认隔离。"""

    def __init__(
        self,
        db: Any,
        *,
        salience_floor: float = 0.6,
        limit: int = 200,
    ) -> None:
        self.db = db
        self.salience_floor = float(salience_floor)
        self.limit = int(limit)

    async def collect_candidates(self) -> list[dict]:
        """读近窗 broadcast_traces，确定性按 salience 取高价值拍。"""
        rows = await self.db.list_recent_broadcast_traces(self.limit)
        picked = [
            r for r in rows if _passes_filter(r, salience_floor=self.salience_floor)
        ]
        picked.sort(key=_sort_key)
        return picked

    def to_samples(self, traces: list[dict]) -> list[dict]:
        """broadcast 行 → 结构化训练样本（纯搬运，无 LLM）。"""
        samples: list[dict] = []
        for row in traces:
            kind = str(row.get("winner_kind") or "idle")
            sal = float(row.get("winner_salience") or 0.0)
            motive = row.get("motive") if isinstance(row.get("motive"), dict) else {}
            candidates = (
                row.get("candidates") if isinstance(row.get("candidates"), list) else []
            )
            samples.append(
                {
                    "beat": row.get("beat"),
                    "timestamp": row.get("timestamp"),
                    "winner_kind": kind,
                    "winner_salience": sal,
                    "motive": motive,
                    "candidates": candidates,
                    "prompt_hint": (
                        f"[winner={kind} sal={sal:.3f}] "
                        f"curiosity={_motive_curiosity(motive):.3f} "
                        f"world_surprise={_motive_world_surprise(motive):.3f}"
                    ),
                }
            )
        return samples

    async def run_training(self, *, dry_run: bool = True) -> dict[str, Any]:
        """资源预估；默认 dry_run 不训练。非 dry_run 仅占位（不引重依赖）。"""
        candidates = await self.collect_candidates()
        samples = self.to_samples(candidates)
        n = len(samples)
        estimate = {
            "sample_count": n,
            "scan_limit": self.limit,
            "salience_floor": self.salience_floor,
            "est_minutes": max(1, n // 50),
            "vram_hint": "需显存≥8GB 或维护者显式同意；当前默认不训练",
            "dry_run": bool(dry_run),
        }
        print(
            "[replay] 资源预估: "
            f"samples={n}, est_minutes≈{estimate['est_minutes']}, "
            f"{estimate['vram_hint']}"
        )
        if dry_run:
            print("[replay] dry_run=True — 不触发训练")
            return estimate

        # 真训分支占位：需维护者显式开关；不 import torch/peft/transformers
        print(
            "[replay] dry_run=False — 训练后端未接入（占位）。"
            "请维护者确认资源后接可选依赖。"
        )
        estimate["training"] = "not_implemented"
        return estimate


async def _cli_main() -> None:
    """显式 CLI：仅 dry_run 预估（不接心跳）。"""
    import argparse
    from pathlib import Path

    from qi.paths import under_data
    from qi.storage.database import Database

    parser = argparse.ArgumentParser(description="经验回放资源预估（默认 dry_run）")
    parser.add_argument(
        "--db",
        default=str(under_data("qi.db")),
        help="SQLite 路径",
    )
    args = parser.parse_args()
    db = Database(args.db)
    await db.initialize()
    try:
        await ReplayBuffer(db).run_training(dry_run=True)
    finally:
        await db.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(_cli_main())
