"""行动层协调器——意志伸手的那一拍。"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.assist import AssistAction
from qi.action.budget import BODY_MEMORY_KEY, ActionBudget
from qi.action.disk import DiskAction, DiskRequest
from qi.action.explore import ExploreAction
from qi.action.explore_web import WebSearchClient
from qi.action.look import LookAction
from qi.action.open import OpenAction, OpenRequest
from qi.action.permission import OUTCOME_OVERSTEPPED, outcome_creates_scar
from qi.action.self_ops import SelfOps
from qi.action.share import ShareAction
from qi.action.tend import TendAction
from qi.action.together import TogetherAction, TogetherRequest
from qi.action.volition import action_intentions
from qi.action.write import WriteAction, WriteRequest

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.sensing import SensingSnapshot
    from qi.storage.database import Database

logger = logging.getLogger("qi.action")

# 补丁 C：awake 仅放行低打扰自反；share/tend/explore 仍需独处气质
_AWAKE_SELF_OPS = frozenset({"archive", "journal", "budget_tune"})

# 与 L5 SEASON_BEHAVIOR_HINTS 并列；可通过 config.action.season_scale 覆盖
SEASON_ACTION_SCALE = {
    "spring": 1.0,
    "summer": 0.8,
    "autumn": 0.5,
    "winter": 0.2,
}


def resolve_season_scale(season: str, config: dict | None = None) -> float:
    scales = dict(SEASON_ACTION_SCALE)
    cfg = ((config or {}).get("action") or {}).get("season_scale") or {}
    if isinstance(cfg, dict):
        scales.update({k: float(v) for k, v in cfg.items()})
    return float(scales.get(season, 1.0))


class ActionLayer:
    """
    tick：形成意图 → 门控/预算/季节 → 至多一个自主行动 → 留痕。
    LLM 不直接调工具；结果经 prompt_extras 注入下一轮对话。
    self_ops（archive/budget_tune/journal）不进 tick 随机主路径，走 execute_kind。
    """

    def __init__(
        self,
        db: Database,
        config: dict | None = None,
        narrative: NarrativeMemory | None = None,
        llm: LLMGateway | None = None,
    ):
        self.db = db
        self.config = config or {}
        self.llm = llm
        self.budget = ActionBudget(self.config)
        self.share = ShareAction(db, narrative=narrative, config=self.config)
        self.tend = TendAction(db, narrative=narrative)
        web = self._build_explore_web()
        self.explore = ExploreAction(
            db,
            narrative=narrative,
            config=self.config,
            web=web,
            llm=llm,
        )
        self.self_ops = SelfOps(db)
        self.assist = AssistAction(db, llm=llm, narrative=narrative)
        self.look = LookAction(db, config=self.config, llm=llm)
        self.open = OpenAction(db, llm=llm, config=self.config, look=self.look)
        self.disk = DiskAction(db, config=self.config)
        self.write = WriteAction(db, config=self.config)
        self.together = TogetherAction(db, config=self.config)
        self.last_result: dict | None = None
        self.last_closed_loop: dict[str, Any] | None = None

    def _build_explore_web(self) -> WebSearchClient | None:
        """enabled + api_key 配齐才建；否则外部分支禁用。"""
        ext = (self.config.get("action") or {}).get("explore_external") or {}
        if not isinstance(ext, dict):
            return None
        if not ext.get("enabled"):
            return None
        key = str(ext.get("api_key") or "").strip()
        if not key:
            return None
        provider = str(ext.get("provider") or "tavily").strip() or "tavily"
        return WebSearchClient(provider=provider, api_key=key, config=ext)

    def season_scale(self, season: str) -> float:
        return resolve_season_scale(season, self.config)

    def _note_closed_loop(self, result: dict | None) -> None:
        if result and isinstance(result.get("closed_loop"), dict):
            self.last_closed_loop = result["closed_loop"]

    async def _maybe_save_scar(
        self,
        result: dict,
        kind: str,
        now: datetime,
        *,
        trust: float = 0.5,
    ) -> None:
        """Step 5 收尾：失败行动形成伤疤。"""
        outcome = result.get("outcome")
        if not outcome_creates_scar(outcome):
            return
        severity = 0.7 if outcome == OUTCOME_OVERSTEPPED else 0.3
        origin = f"[action:{kind}] {(result.get('summary') or '')[:80]}"
        try:
            scar_id = await self.db.save_scar(
                origin_event=origin,
                severity=severity,
                trust_before=float(trust or 0.5),
            )
            result["created_scar"] = scar_id
            logger.info(
                "行动形成伤疤 kind=%s outcome=%s scar_id=%s",
                kind,
                outcome,
                scar_id,
            )
        except Exception:
            logger.debug("save_scar 失败", exc_info=True)

    async def detect_tend_occasion(
        self, season: str, now: datetime
    ) -> str | None:
        """相识纪念日或季节更替；由调用方/本层给出 occasion。"""
        last_season = await self.db.get_body_memory("tend_last_season")
        if last_season != season:
            return f"season:{season}"

        firsts = await self.db.list_first_times()
        if firsts:
            raw = firsts[0].get("timestamp")
            try:
                t0 = datetime.fromisoformat(str(raw))
            except ValueError:
                t0 = None
            if t0 is not None and t0.month == now.month and t0.day == now.day:
                # 同一天首次相遇的周年；同年只记一次
                marked = await self.db.get_body_memory("tend_last_anniversary_year")
                if marked != now.year:
                    return "anniversary"
        return None

    async def _mark_tend_done(
        self, occasion: str, season: str, now: datetime
    ) -> None:
        if occasion.startswith("season:"):
            await self.db.set_body_memory("tend_last_season", season)
        elif occasion == "anniversary":
            await self.db.set_body_memory("tend_last_anniversary_year", now.year)

    async def _intention_context(
        self,
        *,
        season: str,
        now: datetime,
        sensing: SensingSnapshot | None = None,
    ) -> tuple[Any, str | None, float, int, int, float | None]:
        undelivered = await self.db.load_unshared_creation()
        tend_occasion = await self.detect_tend_occasion(season, now)
        scale = self.season_scale(season)
        archivable = await self.db.list_archivable_narratives(limit=3)
        archivable_count = len(archivable)
        open_loop_count = 0
        try:
            loops = await self.db.get_body_memory("open_loops")
            if isinstance(loops, list):
                open_loop_count = len(loops)
            elif isinstance(loops, dict):
                items = loops.get("items") or loops.get("loops")
                if isinstance(items, list):
                    open_loop_count = len(items)
        except Exception:
            open_loop_count = 0
        uptime = None
        if sensing is not None:
            uptime = float(sensing.uptime_seconds)
        return (
            undelivered,
            tend_occasion,
            scale,
            archivable_count,
            open_loop_count,
            uptime,
        )

    async def tick(
        self,
        emotion: EmotionState,
        relationship_stage: str,
        season: str,
        now: datetime,
        *,
        mode: str,
        user_online: bool = True,
        scars: list[dict] | None = None,
        sensing: SensingSnapshot | None = None,
        pressure: Any | None = None,
        trust: float = 0.5,
        silence_seconds: float | None = None,
        speaking: bool = False,
    ) -> dict | None:
        """
        独处一拍：至多做一个自主行动。
        dreaming / 离线 → None。assist / self_ops 不在此执行。
        """
        self.last_result = None
        if not user_online or mode == "dreaming":
            return None
        if mode not in ("solitary", "ambient"):
            # awake 偏对话；自主伸手留给独处气质
            return None
        if not self.budget.can_autonomous(now):
            return None

        (
            undelivered,
            tend_occasion,
            scale,
            archivable_count,
            open_loop_count,
            uptime,
        ) = await self._intention_context(
            season=season, now=now, sensing=sensing
        )

        intents = action_intentions(
            mode=mode,
            relationship_stage=relationship_stage,
            curiosity=float(emotion.curiosity),
            valence=float(emotion.valence),
            has_undelivered_creation=undelivered is not None,
            tend_occasion=tend_occasion,
            user_message=None,
            budget=self.budget,
            now=now,
            season_scale=scale,
            scars=scars,
            user_online=user_online,
            archivable_count=archivable_count,
            open_loop_count=open_loop_count,
            sensing_uptime_seconds=uptime,
            energy=float(emotion.energy),
            pressure=pressure,
            silence_seconds=silence_seconds,
        )
        # tick 只跑 share/tend/explore/look，self_ops 留给 GWS execute_kind
        autos = [
            i
            for i in intents
            if i.kind in ("share", "tend", "explore", "look")
        ]
        if not autos:
            return None

        chosen = autos[0]
        # C4 时机阀：priority 过阈后随机仅扰动释放时刻（非动机来源）；冬天几乎不动手
        if random.random() > min(1.0, max(0.0, chosen.priority)):
            return None

        result: dict | None = None
        if chosen.kind == "share":
            result = await self.share.try_share(
                emotion,
                relationship_stage,
                self.budget,
                season=season,
                now=now,
            )
        elif chosen.kind == "tend" and tend_occasion:
            result = await self.tend.tend(
                tend_occasion, emotion, season, now=now, speak=False
            )
            if result is not None:
                self.budget.record("tend", now)
                await self._mark_tend_done(tend_occasion, season, now)
        elif chosen.kind == "explore":
            result = await self.explore.drift(
                float(emotion.curiosity),
                emotion,
                season,
                season_scale=scale,
                now=now,
                pressure=pressure,
            )
            if result is not None:
                self.budget.record("explore", now)
        elif chosen.kind == "look":
            result = await self.look.try_autonomous(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
                mode=mode,
                speaking=speaking,
            )
            if result is not None and result.get("outcome") == "success":
                self.budget.record("look", now)

        if result is not None:
            await self._maybe_save_scar(result, chosen.kind, now, trust=trust)
        self.last_result = result
        return result

    async def execute_kind(
        self,
        kind: str,
        emotion: EmotionState,
        relationship_stage: str,
        season: str,
        now: datetime,
        *,
        mode: str,
        user_online: bool = True,
        scars: list[dict] | None = None,
        sensing: SensingSnapshot | None = None,
        pressure: Any | None = None,
        trust: float = 0.5,
        op: str | None = None,
        target_path: str | None = None,
        confirmed: bool = False,
        payload: Any | None = None,
        selected_index: int | None = None,
    ) -> dict | None:
        """GWS 分发：执行指定行动 kind，跳过 tick 内随机软门。"""
        self.last_result = None
        if not user_online or mode == "dreaming":
            return None
        # B1：awake 放行 self_ops + assist + look + open + disk（响应式）
        if mode == "awake":
            if kind not in _AWAKE_SELF_OPS and kind not in (
                "assist",
                "look",
                "open",
                "disk",
                "write",
                "together",
            ):
                return None
        elif mode not in ("solitary", "ambient"):
            return None
        # B2：响应式不占预算
        if kind not in (
            "assist",
            "look",
            "open",
            "disk",
            "write",
            "together",
        ) and not self.budget.can_autonomous(
            now
        ):
            return None

        undelivered = await self.db.load_unshared_creation()
        tend_occasion = await self.detect_tend_occasion(season, now)
        scale = self.season_scale(season)
        result: dict | None = None

        if kind == "share":
            if undelivered is None:
                return None
            result = await self.share.try_share(
                emotion,
                relationship_stage,
                self.budget,
                season=season,
                now=now,
            )
        elif kind == "tend":
            if not tend_occasion:
                return None
            result = await self.tend.tend(
                tend_occasion, emotion, season, now=now, speak=False
            )
            if result is not None:
                self.budget.record("tend", now)
                await self._mark_tend_done(tend_occasion, season, now)
        elif kind == "explore":
            result = await self.explore.drift(
                float(emotion.curiosity),
                emotion,
                season,
                season_scale=scale,
                now=now,
                force=True,
                pressure=pressure,
            )
            if result is not None:
                self.budget.record("explore", now)
                # 真读闭环：有条目时记一笔差异
                if result.get("found"):
                    closed = {
                        "op": "explore",
                        "at": now.isoformat(timespec="seconds"),
                        "before": {"found": None},
                        "after": {
                            "entries": list(
                                (result["found"] or {}).get("entries") or []
                            )[:8]
                        },
                    }
                    result = {**result, "closed_loop": closed}
                    try:
                        await self.db.set_body_memory(
                            "last_closed_loop", closed
                        )
                    except Exception:
                        logger.debug("explore closed_loop 落盘失败", exc_info=True)
        elif kind == "archive":
            result = await self.self_ops.archive_stale_memories(
                self.budget,
                relationship_stage=relationship_stage,
                scars=scars,
                now=now,
            )
        elif kind == "budget_tune":
            result = await self.self_ops.tune_budget(
                self.budget,
                emotion,
                relationship_stage=relationship_stage,
                scars=scars,
                now=now,
            )
        elif kind == "journal":
            result = await self.self_ops.write_inner_journal(
                self.budget,
                emotion,
                sensing=sensing,
                relationship_stage=relationship_stage,
                scars=scars,
                now=now,
            )
        elif kind == "assist":
            # assist 响应式，不占 ActionBudget
            if not target_path or not op:
                result = None
            else:
                result = await self.assist.execute(
                    op,
                    target_path,
                    relationship_stage=relationship_stage,
                    trust=trust,
                    scars=scars,
                    confirmed=confirmed,
                    season=season,
                    now=now,
                )
        elif kind == "look":
            reactive = op == "invite" or bool(confirmed)
            result = await self.look.glance(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
                reactive=reactive,
                user_question=target_path if reactive else None,
                mode=mode,
            )
            if (
                result is not None
                and not reactive
                and result.get("outcome") == "success"
            ):
                self.budget.record("look", now)
        elif kind == "open":
            open_req = payload if isinstance(payload, OpenRequest) else None
            if open_req is None and target_path:
                intent = op or "open"
                url_like = str(target_path).startswith(("http://", "https://"))
                open_req = OpenRequest(
                    intent=intent
                    if intent in ("open", "open_and_look", "allow", "teach")
                    else "open",
                    target_type="url" if url_like else "app",
                    target=str(target_path),
                )
            if open_req is None:
                result = None
            else:
                result = await self.open.execute(
                    open_req,
                    relationship_stage=relationship_stage,
                    confirmed=confirmed,
                    season=season,
                    now=now,
                    selected_index=selected_index,
                )
        elif kind == "disk":
            disk_req = payload if isinstance(payload, DiskRequest) else None
            if disk_req is None and target_path:
                intent = op or "list_dir"
                if intent not in ("list_dir", "open_file"):
                    intent = "list_dir"
                disk_req = DiskRequest(intent=intent, path=str(target_path))
            if disk_req is None:
                result = None
            else:
                result = await self.disk.execute(
                    disk_req,
                    relationship_stage=relationship_stage,
                    confirmed=confirmed,
                    season=season,
                    now=now,
                )
        elif kind == "write":
            write_req = payload if isinstance(payload, WriteRequest) else None
            if write_req is None and target_path:
                write_req = WriteRequest(
                    intent=op or "write",
                    path=str(target_path),
                )
            if write_req is None:
                result = None
            else:
                result = await self.write.execute(
                    write_req,
                    relationship_stage=relationship_stage,
                    confirmed=confirmed,
                    season=season,
                    now=now,
                    llm=self.llm,
                )
        elif kind == "together":
            tog_req = payload if isinstance(payload, TogetherRequest) else None
            if tog_req is None and target_path:
                tog_req = TogetherRequest(
                    target_type="url"
                    if str(target_path).startswith("http")
                    else "app",
                    target=str(target_path),
                )
            if tog_req is None:
                result = None
            else:
                result = await self.together.execute(
                    tog_req,
                    relationship_stage=relationship_stage,
                    confirmed=confirmed,
                    season=season,
                    now=now,
                )
        else:
            return None

        self._note_closed_loop(result)
        if result is not None:
            await self._maybe_save_scar(result, kind, now, trust=trust)
        self.last_result = result
        return result

    async def prompt_extras(self, limit: int = 3) -> dict[str, str]:
        """栖最近做过的事——经历背景，不报流水账。"""
        rows = await self.db.list_recent_actions(limit=limit)
        if not rows:
            return {"recent_actions": "（最近没有特别伸过手）"}
        # 时间倒序已由 list_recent_actions 保证；用叙事摘要
        lines = []
        for row in rows:
            summary = str(row.get("summary") or "").strip()
            if not summary:
                continue
            line = f"- {summary}"
            # assist-6：assist 行附「刚读的文件 + 内容概览」，追问可诚实回答
            if row.get("kind") == "assist":
                detail = row.get("detail_json")
                if detail:
                    try:
                        d = json.loads(str(detail))
                    except (json.JSONDecodeError, TypeError):
                        d = {}
                    tp = str(d.get("target_path") or "").strip()
                    preview = str(d.get("content_preview") or "").strip()
                    if tp or preview:
                        name = (
                            tp.replace("\\", "/").rsplit("/", 1)[-1]
                            if tp
                            else ""
                        )
                        note = "（刚读：" + name
                        if preview:
                            note += "——" + preview
                        note += "）"
                        line += " " + note
            lines.append(line)
        if not lines:
            return {"recent_actions": "（最近没有特别伸过手）"}
        body = "\n".join(lines)
        return {
            "recent_actions": (
                "这些是你近来做过的事。知道就好，不必挂在嘴上，"
                "更不要当成任务清单念出来。\n" + body
            )
        }

    def snapshot(self) -> dict:
        """封存用：委托 ActionBudget（包 14）。"""
        return self.budget.snapshot()

    def restore(self, data: dict | None) -> None:
        """封存恢复：委托 ActionBudget（包 14）。"""
        self.budget.restore(data)

    async def persist_budget(self) -> None:
        try:
            await self.db.set_body_memory(BODY_MEMORY_KEY, self.budget.snapshot())
        except Exception:
            logger.exception("行动预算持久化失败")

    async def restore_budget(self) -> None:
        data = await self.db.get_body_memory(BODY_MEMORY_KEY)
        if isinstance(data, dict):
            self.budget.restore(data)
        loop = await self.db.get_body_memory("last_closed_loop")
        if isinstance(loop, dict):
            self.last_closed_loop = loop
