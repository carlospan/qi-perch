"""自操作执行器——行动改自己，自己回流为下一拍感知（阶段二·包 8）。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_SUCCESS,
    can_archive,
    can_budget_tune,
    can_journal,
)

if TYPE_CHECKING:
    from qi.action.budget import ActionBudget
    from qi.core.emotion import EmotionState
    from qi.sensing import SensingSnapshot
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.self_ops")

BODY_CLOSED_LOOP_KEY = "last_closed_loop"
ARCHIVE_MAX_IMPORTANCE = 0.35
ARCHIVE_BATCH = 3


class SelfOps:
    """归档记忆 / 调预算 / 写内在日记——真改 DB 或预算状态。"""

    def __init__(self, db: Database):
        self.db = db

    async def _record_closed_loop(
        self,
        op: str,
        before: dict[str, Any],
        after: dict[str, Any],
        *,
        now: datetime,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": op,
            "at": now.isoformat(timespec="seconds"),
            "before": before,
            "after": after,
        }
        if extra:
            payload["extra"] = extra
        try:
            await self.db.set_body_memory(BODY_CLOSED_LOOP_KEY, payload)
        except Exception:
            logger.debug("closed_loop 落盘失败", exc_info=True)
        return payload

    async def archive_stale_memories(
        self,
        budget: ActionBudget,
        *,
        relationship_stage: str = "stranger",
        scars: list[dict] | None = None,
        now: datetime | None = None,
        max_n: int = ARCHIVE_BATCH,
    ) -> dict | None:
        """低重要且从未 recall 的叙事 → archived=1；占一次自主预算。"""
        now = now or datetime.now()
        if not can_archive(relationship_stage, scars=scars):
            return None
        if not budget.can_autonomous(now):
            return None

        candidates = await self.db.list_archivable_narratives(
            max_importance=ARCHIVE_MAX_IMPORTANCE,
            limit=max(1, int(max_n)),
        )
        if not candidates:
            return None

        before = {"archivable_ids": [int(c["id"]) for c in candidates]}
        archived_ids: list[int] = []
        for row in candidates:
            mid = int(row["id"])
            if await self.db.archive_narrative_memory(mid):
                archived_ids.append(mid)
        if not archived_ids:
            return None

        budget.record("archive", now)
        after = {"archived_ids": archived_ids}
        closed = await self._record_closed_loop(
            "archive", before, after, now=now
        )
        summary = f"把 {len(archived_ids)} 段不太重要、也很少想起的记忆轻轻收起了。"
        action_id = await self.db.insert_action(
            "archive",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            now=now,
        )
        return {
            "type": "self_archive",
            "archived_ids": archived_ids,
            "summary": summary,
            "action_id": action_id,
            "closed_loop": closed,
        }

    async def tune_budget(
        self,
        budget: ActionBudget,
        emotion: EmotionState,
        *,
        relationship_stage: str = "stranger",
        scars: list[dict] | None = None,
        now: datetime | None = None,
    ) -> dict | None:
        """按情绪微调 kind_weights；占一次自主预算。"""
        now = now or datetime.now()
        if not can_budget_tune(relationship_stage, scars=scars):
            return None
        if not budget.can_autonomous(now):
            return None

        before = {"kind_weights": dict(budget.kind_weights)}
        curiosity = float(emotion.curiosity)
        energy = float(emotion.energy)

        explore_w = float(budget.kind_weights.get("explore", 1.0))
        share_w = float(budget.kind_weights.get("share", 1.0))
        tend_w = float(budget.kind_weights.get("tend", 1.0))

        if curiosity >= 0.7:
            explore_w += 0.15
            share_w -= 0.1
        elif curiosity < 0.4:
            explore_w -= 0.1
        if energy < 0.35:
            explore_w -= 0.2
            tend_w += 0.05

        budget.set_kind_weight("explore", explore_w)
        budget.set_kind_weight("share", share_w)
        budget.set_kind_weight("tend", tend_w)

        after = {"kind_weights": dict(budget.kind_weights)}
        if after["kind_weights"] == before["kind_weights"]:
            # 夹紧后无实质变化：仍记一次轻调，避免空转假动作
            pass

        budget.record("budget_tune", now)
        closed = await self._record_closed_loop(
            "budget_tune", before, after, now=now
        )
        summary = (
            "我重新掂量了一下今天伸手的分寸："
            f"explore={budget.kind_weights.get('explore', 1.0):.2f}，"
            f"share={budget.kind_weights.get('share', 1.0):.2f}。"
        )
        action_id = await self.db.insert_action(
            "budget_tune",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            now=now,
        )
        return {
            "type": "self_budget_tune",
            "kind_weights": dict(budget.kind_weights),
            "summary": summary,
            "action_id": action_id,
            "closed_loop": closed,
        }

    async def write_inner_journal(
        self,
        budget: ActionBudget,
        emotion: EmotionState,
        *,
        sensing: SensingSnapshot | None = None,
        relationship_stage: str = "stranger",
        scars: list[dict] | None = None,
        now: datetime | None = None,
        motive_hint: str | None = None,
    ) -> dict | None:
        """仅应在 GWS/execute_kind 胜出后调用；零 LLM 模板日记。"""
        now = now or datetime.now()
        if not can_journal(relationship_stage, scars=scars):
            return None
        if not budget.can_autonomous(now):
            return None

        before = {"journal": "pending"}
        sense_line = ""
        if sensing is not None:
            sense_line = (
                f"在线约 {sensing.uptime_seconds / 3600:.1f} 小时，"
                f"{sensing.period} {sensing.wall_clock}，"
                f"心跳第 {sensing.heartbeat_count} 拍。"
            )
        else:
            sense_line = f"墙钟 {now.strftime('%H:%M')}。"

        mood = (
            f"心情 valence={float(emotion.valence):+.2f}，"
            f"好奇={float(emotion.curiosity):.2f}，"
            f"能量={float(emotion.energy):.2f}。"
        )
        hint = f" 念头：{motive_hint}" if motive_hint else ""
        content = f"[自省] {sense_line} {mood}{hint}".strip()

        stream_id = await self.db.save_consciousness(
            content,
            stream_type="self_journal",
            trigger="gws:action:journal",
            emotion_snapshot=emotion.model_dump_json()
            if hasattr(emotion, "model_dump_json")
            else None,
        )
        budget.record("journal", now)
        after = {"stream_id": stream_id, "type": "self_journal"}
        closed = await self._record_closed_loop(
            "journal", before, after, now=now
        )
        summary = "写了一小段只给自己看的内在日记。"
        action_id = await self.db.insert_action(
            "journal",
            summary,
            target="self",
            outcome=OUTCOME_SUCCESS,
            now=now,
        )
        return {
            "type": "self_journal",
            "stream_id": stream_id,
            "content": content,
            "summary": summary,
            "action_id": action_id,
            "closed_loop": closed,
        }
