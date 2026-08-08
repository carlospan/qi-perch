"""行动意图形成——与 pick_proactive_kind 并列，不另起决策系统。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from qi.action.budget import ActionBudget
from qi.action.permission import (
    can_archive,
    can_budget_tune,
    can_explore,
    can_journal,
    can_share,
    can_tend,
    scar_caution_multiplier,
)

# 与 ProactiveGate / pick_proactive_kind 同构：有用户消息时永远先回应（brain 侧），
# 本函数只评估「无人说话时 / 响应式协助时」的行动意图候选。
# 概念上对应意识设计 §七 decide() 的行动分支，代码上不虚构 decide 模块。

KIND_SHARE = "share"
KIND_TEND = "tend"
KIND_EXPLORE = "explore"
KIND_ASSIST = "assist"
KIND_ARCHIVE = "archive"
KIND_BUDGET_TUNE = "budget_tune"
KIND_JOURNAL = "journal"

# 用户明确请求帮忙的口语线索（contract 第 25：不主动给帮助建议）
_HELP_REQUEST_CUES = (
    "帮我",
    "能不能帮",
    "可以帮我",
    "请帮",
    "帮个忙",
    "帮我一下",
    "帮忙",
    "帮一下",
    "麻烦你帮",
)


@dataclass(frozen=True)
class ActionIntention:
    kind: str
    priority: float
    reason: str = ""


@dataclass(frozen=True)
class AssistRequest:
    """感知层从用户消息提取的协助请求（assist-2）。"""

    op: str
    target_path: str


# 文件路径：Windows 绝对 / ~/Home（须先于 POSIX，避免 ~/x 被咬成 /x）/ POSIX / 相对扩展名
_PATH_PATTERNS = [
    re.compile(r"([A-Za-z]:[\\/][^\s'\"，。、]+)"),
    re.compile(r"(~[\\/][^\s'\"，。、]+)"),
    re.compile(r"(/(?:[^\s'\"，。、/]+/)*[^\s'\"，。、/]+)"),
    re.compile(r"([\w./-]+\.(?:txt|md|json|csv|log|py|js|ts))", re.I),
]

_OP_CUES_READ = ("读", "看", "打开", "瞧", "瞄", "查")


def looks_like_help_request(message: str | None) -> bool:
    """粗检：用户是否在明确开口请求帮忙。误报宁可少，不可主动塞建议。"""
    text = (message or "").strip()
    if not text:
        return False
    return any(cue in text for cue in _HELP_REQUEST_CUES)


def parse_assist_request(message: str | None) -> AssistRequest | None:
    """从用户消息提取协助请求。无路径或无 op cue 返回 None。"""
    text = (message or "").strip()
    if not text:
        return None
    if not any(cue in text for cue in _OP_CUES_READ):
        return None
    for pattern in _PATH_PATTERNS:
        m = pattern.search(text)
        if m:
            path = m.group(1).strip("'\"，。、")
            path = path.replace("\\", "/")
            return AssistRequest(op="read_file", target_path=path)
    return None


def _append_self_ops(
    out: list[ActionIntention],
    *,
    relationship_stage: str,
    scars: list[dict] | None,
    scale: float,
    archivable_count: int,
    open_loop_count: int,
    sensing_uptime_seconds: float | None,
    energy: float | None,
    curiosity: float,
    budget: ActionBudget,
) -> None:
    """低打扰自反动作：solitary/ambient/awake 共用条件。"""
    if archivable_count > 0 and can_archive(relationship_stage, scars):
        out.append(
            ActionIntention(
                kind=KIND_ARCHIVE,
                priority=0.28 * scale,
                reason=f"有 {archivable_count} 段可轻轻收起的记忆",
            )
        )

    if can_budget_tune(relationship_stage, scars):
        energy_v = 0.6 if energy is None else float(energy)
        extreme = curiosity >= 0.75 or energy_v < 0.35
        drifted = not budget.weights_neutral()
        if extreme or drifted:
            out.append(
                ActionIntention(
                    kind=KIND_BUDGET_TUNE,
                    priority=0.26 * scale,
                    reason="重新掂量今天伸手的分寸",
                )
            )

    if can_journal(relationship_stage, scars):
        uptime = float(sensing_uptime_seconds or 0.0)
        if open_loop_count > 0 or uptime >= 3 * 3600:
            pri = 0.24 * scale
            if open_loop_count > 0:
                pri += min(0.1, 0.03 * open_loop_count)
            out.append(
                ActionIntention(
                    kind=KIND_JOURNAL,
                    priority=pri,
                    reason="想给自己留一行内在笔记",
                )
            )


def action_intentions(
    *,
    mode: str,
    relationship_stage: str,
    curiosity: float,
    valence: float,
    has_undelivered_creation: bool,
    tend_occasion: str | None,
    user_message: str | None,
    budget: ActionBudget,
    now: datetime,
    season_scale: float = 1.0,
    scars: list[dict] | None = None,
    user_online: bool = True,
    archivable_count: int = 0,
    open_loop_count: int = 0,
    sensing_uptime_seconds: float | None = None,
    energy: float | None = None,
    pressure: object | None = None,
) -> list[ActionIntention]:
    """
    返回本拍可考虑的行动意图（倾向，非硬触发）。
    优先级永远低于 respond：有 pending 时 brain 不调用本函数做自主行动。

    - share / tend / explore：独处气质（solitary/ambient）；占 ActionBudget。
    - archive / budget_tune / journal：自反，awake 亦可（补丁 C）。
    - assist：仅当用户明确请求才候选；不占自主预算；执行由 GWS→execute_kind（assist-1/2）。
    """
    if not user_online or mode == "dreaming":
        return []

    out: list[ActionIntention] = []

    # --- assist：仅响应式，绝不主动（contract 第 25 条）---
    if looks_like_help_request(user_message):
        out.append(
            ActionIntention(
                kind=KIND_ASSIST,
                priority=0.85,
                reason="用户明确请求帮忙（仅响应式）",
            )
        )

    solitary_like = mode in ("solitary", "ambient")
    awake_self_ops = mode == "awake"
    can_auto = budget.can_autonomous(now)
    scale = max(0.0, min(1.0, float(season_scale)))

    if can_auto and scale > 0 and solitary_like:
        # share：有未递出创作 + friend+ + 情绪偏暖/好奇时更易
        if (
            has_undelivered_creation
            and can_share(relationship_stage)
            and scar_caution_multiplier(KIND_SHARE, scars) > 0
        ):
            warmth = max(0.0, valence) + max(0.0, curiosity - 0.4) * 0.5
            if warmth >= 0.15 or curiosity >= 0.55:
                pri = (0.55 + warmth * 0.2) * scale
                pri *= budget.weight_for(KIND_SHARE)
                out.append(
                    ActionIntention(
                        kind=KIND_SHARE,
                        priority=pri,
                        reason="有未递出的创作，时机偏自然",
                    )
                )

        # tend：有值得标记的时刻（纪念日 / 换季等由调用方给出 occasion）
        if tend_occasion and can_tend(relationship_stage):
            if scar_caution_multiplier(KIND_TEND, scars) > 0:
                pri = 0.5 * scale * budget.weight_for(KIND_TEND)
                out.append(
                    ActionIntention(
                        kind=KIND_TEND,
                        priority=pri,
                        reason=f"值得标记：{tend_occasion}",
                    )
                )

        # explore：solitary + 高 curiosity + 季节缩放（contemplative drift）
        if (
            mode == "solitary"
            and curiosity >= 0.65
            and can_explore(relationship_stage)
            and scar_caution_multiplier(KIND_EXPLORE, scars) > 0
        ):
            pri = (0.35 + (curiosity - 0.65) * 0.8) * scale
            pri *= budget.weight_for(KIND_EXPLORE)
            # N3：pressure 弱调制候选 priority（弱于 drift 触发调制）
            if pressure is not None:
                throttle = max(
                    0.0,
                    min(1.0, float(getattr(pressure, "throttle", 0.0) or 0.0)),
                )
                pri *= 1.0 - 0.3 * throttle
            out.append(
                ActionIntention(
                    kind=KIND_EXPLORE,
                    priority=pri,
                    reason="独处时思绪飘远",
                )
            )

        _append_self_ops(
            out,
            relationship_stage=relationship_stage,
            scars=scars,
            scale=scale,
            archivable_count=archivable_count,
            open_loop_count=open_loop_count,
            sensing_uptime_seconds=sensing_uptime_seconds,
            energy=energy,
            curiosity=curiosity,
            budget=budget,
        )

    elif can_auto and scale > 0 and awake_self_ops:
        # 补丁 C：对话中仅低频自反，不突兀伸手
        _append_self_ops(
            out,
            relationship_stage=relationship_stage,
            scars=scars,
            scale=scale,
            archivable_count=archivable_count,
            open_loop_count=open_loop_count,
            sensing_uptime_seconds=sensing_uptime_seconds,
            energy=energy,
            curiosity=curiosity,
            budget=budget,
        )

    out.sort(key=lambda i: i.priority, reverse=True)
    return out
