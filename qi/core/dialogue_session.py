"""对话会话粘性状态（架构整顿 Phase 2）。

跨轮 pending、disk 列表记忆、write 欲望、together 池、assist 目标等
从 Brain 收敛到单一上下文对象，供 dialogue_router 与后续计划层复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class DialogueSessionContext:
    """单用户对话会话内的 L7 多轮粘性状态（仅内存）。"""

    pending_assist_confirmation: Any | None = None
    pending_assist_confirmation_at: datetime | None = None
    pending_assist_heartbeats: int = 0
    last_disk_listing: dict | None = None
    write_desire: dict | None = None
    together_pool: list = field(default_factory=list)
    last_assist_target: str | None = None
    last_assist_target_at: datetime | None = None
    last_assist_request: Any | None = None

    def clear_pending_assist(self) -> None:
        self.pending_assist_confirmation = None
        self.pending_assist_confirmation_at = None
        self.pending_assist_heartbeats = 0

    def clear_assist_target(self) -> None:
        self.last_assist_target = None
        self.last_assist_target_at = None

    def assist_target_fresh(self, now: datetime) -> bool:
        if self.last_assist_target_at is None:
            return False
        return now - self.last_assist_target_at <= timedelta(minutes=5)

    def tick_pending_timeout(self, now: datetime) -> None:
        """pending 确认超时或心跳次数过多时清空。"""
        if self.pending_assist_confirmation is None:
            return
        self.pending_assist_heartbeats += 1
        timed_out = False
        if self.pending_assist_confirmation_at is not None:
            elapsed = (now - self.pending_assist_confirmation_at).total_seconds()
            if elapsed > 300:
                timed_out = True
        if timed_out or self.pending_assist_heartbeats >= 3:
            self.clear_pending_assist()
            self.clear_assist_target()

    def remember_disk_listing(self, result: dict | None) -> None:
        if not result or not result.get("listing_sticky"):
            return
        entries = result.get("listing_entries") or []
        if not entries:
            return
        self.last_disk_listing = {
            "dir": result.get("listing_dir"),
            "entries": entries,
            "at": datetime.now(),
        }

    def disk_listing_fresh(self, now: datetime | None = None) -> bool:
        if not self.last_disk_listing:
            return False
        at = self.last_disk_listing.get("at")
        if not isinstance(at, datetime):
            return False
        now = now or datetime.now()
        try:
            from qi.action.disk import LISTING_STICKY_MINUTES

            mins = float(LISTING_STICKY_MINUTES)
        except Exception:
            mins = 5.0
        return (now - at).total_seconds() <= mins * 60

    def remember_write_desire(self, result: dict | None) -> None:
        if not result or not result.get("remember_desire"):
            return
        self.write_desire = {
            "intent": str(result.get("desire_intent") or "write"),
            "topic": str(result.get("desire_topic") or ""),
            "at": datetime.now(),
        }

    def write_desire_fresh(self, now: datetime | None = None) -> bool:
        if not self.write_desire:
            return False
        at = self.write_desire.get("at")
        if not isinstance(at, datetime):
            return False
        now = now or datetime.now()
        return (now - at).total_seconds() <= 10 * 60

    def ingest_together_pool(self, result: dict | None) -> None:
        try:
            from qi.action.together import candidates_from_action_result
        except Exception:
            return
        added = candidates_from_action_result(result)
        if not added:
            return
        now = datetime.now()
        for e in added:
            e = dict(e)
            e["at"] = now
            self.together_pool = [
                x
                for x in self.together_pool
                if str(x.get("target")) != str(e.get("target"))
            ]
            self.together_pool.append(e)
        if len(self.together_pool) > 20:
            self.together_pool = self.together_pool[-20:]

    def arm_disk_pending_from_result(self, disk_req: object, result: dict) -> None:
        pending: object = disk_req
        if result.get("promote_intent") == "list_dir":
            try:
                from qi.action.disk import DiskRequest

                path = str(
                    result.get("list_path") or getattr(disk_req, "path", "") or ""
                )
                pending = DiskRequest(intent="list_dir", path=path)
            except Exception:
                pending = disk_req
        self.pending_assist_confirmation = pending
        self.pending_assist_confirmation_at = datetime.now()
        self.pending_assist_heartbeats = 0
        self.clear_assist_target()

    def arm_open_after_allow(self, result: dict | None) -> None:
        if not result or not result.get("offer_open_now"):
            return
        alias = str(result.get("allow_alias") or "").strip()
        if not alias:
            return
        try:
            from qi.action.open import OpenRequest
        except Exception:
            return
        self.pending_assist_confirmation = OpenRequest(
            intent="open",
            target_type="app",
            target=alias,
        )
        self.pending_assist_confirmation_at = datetime.now()
        self.pending_assist_heartbeats = 0
        self.clear_assist_target()

    def arm_write_pending(self, write_req: object, result: dict) -> None:
        try:
            from qi.action.write import WriteRequest

            if isinstance(write_req, WriteRequest):
                content = str(result.get("write_content") or "").strip()
                if content:
                    write_req.content = content
                mode = str(result.get("write_mode") or "")
                if mode:
                    write_req.meta["write_mode"] = mode
                diary_dir = str(result.get("diary_dir") or "").strip()
                if diary_dir:
                    write_req.path = diary_dir
                    write_req.meta["diary_bootstrap"] = True
        except Exception:
            pass
        self.pending_assist_confirmation = write_req
        self.pending_assist_confirmation_at = datetime.now()
        self.pending_assist_heartbeats = 0
        self.clear_assist_target()
