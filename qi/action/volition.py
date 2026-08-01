"""行动意图形成——与 pick_proactive_kind 并列，不另起决策系统。"""

from __future__ import annotations

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


def looks_like_help_request(message: str | None) -> bool:
    """粗检：用户是否在明确开口请求帮忙。误报宁可少，不可主动塞建议。"""
    text = (message or "").strip()
    if not text:
        return False
    return any(cue in text for cue in _HELP_REQUEST_CUES)


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
) -> list[ActionIntention]:
    """
    返回本拍可考虑的行动意图（倾向，非硬触发）。
    优先级永远低于 respond：有 pending 时 brain 不调用本函数做自主行动。

    - share / tend / explore / archive / budget_tune / journal：自主，占 ActionBudget。
    - assist：仅当用户明确请求才候选；不占自主预算；本阶段不执行（桩）。
    """
    if not user_online or mode == "dreaming":
        return []

    out: list[ActionIntention] = []

    # --- assist 桩：仅响应式，绝不主动（contract 第 25 条）---
    # 本阶段只形成意图候选，不接任何执行路径。
    if looks_like_help_request(user_message):
        out.append(
            ActionIntention(
                kind=KIND_ASSIST,
                priority=0.85,
                reason="用户明确请求帮忙（仅响应式，不执行）",
            )
        )

    # 自主行动：非 awake 独处气质更合适（solitary / ambient）；awake 偏对话
    solitary_like = mode in ("solitary", "ambient")
    can_auto = budget.can_autonomous(now)
    scale = max(0.0, min(1.0, float(season_scale)))

    if can_auto and solitary_like and scale > 0:
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
            # 好奇越高、季节越暖，优先级越高；多数拍仍由 ActionLayer 概率门控
            pri = (0.35 + (curiosity - 0.65) * 0.8) * scale
            pri *= budget.weight_for(KIND_EXPLORE)
            out.append(
                ActionIntention(
                    kind=KIND_EXPLORE,
                    priority=pri,
                    reason="独处时思绪飘远",
                )
            )

        # archive：有可归档叙事时低优先级
        if (
            archivable_count > 0
            and can_archive(relationship_stage, scars)
        ):
            out.append(
                ActionIntention(
                    kind=KIND_ARCHIVE,
                    priority=0.28 * scale,
                    reason=f"有 {archivable_count} 段可轻轻收起的记忆",
                )
            )

        # budget_tune：权重仍中性且好奇/能量偏极端时，或已偏离需再调
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

        # journal：open_loop 或在线过久时略抬（仍低优；执行靠 GWS）
        if can_journal(relationship_stage, scars):
            uptime = float(sensing_uptime_seconds or 0.0)
            if open_loop_count > 0 or uptime >= 6 * 3600:
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

    out.sort(key=lambda i: i.priority, reverse=True)
    return out
