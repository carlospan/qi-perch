"""身份快照——过渡脚手架（阶段三前）。

定位（架构方案 §五 阶段一）：
  规则拼装「此刻的我」，统一注入对话/意识流/梦，缓解每次从头拼栖的断裂。
  **不解决内生性**（仍是 prompt 输入）；阶段三由 GWS + 世界模型替代。
  零 LLM：只读 self_model / 关系 / emotion_states / traces 压缩标签。

失效闭环（防顶着旧自我认知用一周）::

    置位 mark_identity_snapshot_stale(db)
      ← SelfModel.reflect 成功写入后（后台 maybe_reflect 同路径）
      ← 关系 stage 升迁
      ← season 变更
      ← |Δvalence| 超阈（与反思 surge 同阈）
    消费 ensure_identity_snapshot(...)
      ← dirty==True 或 距上次建成 ≥ N=30 拍 或 无缓存 → 重建并清 dirty
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from qi.inner_life.self_model import VALENCE_SURGE_FOR_REFLECT

logger = logging.getLogger("qi.identity_snapshot")

CACHE_KEY = "identity_snapshot"
DIRTY_KEY = "identity_snapshot_dirty"

CACHE_BEATS = 30
TARGET_MAX = 800
SELF_CHARS = 320

# 进程内：距上次建成的拍数（重启归零；dirty 持久化保证 reflect 后必重建）
_beats_since_build: int = 0

# 与反思共用的 valence 冲击阈
SNAPSHOT_VALENCE_SURGE = VALENCE_SURGE_FOR_REFLECT


def note_snapshot_beat() -> None:
    """每心跳调用一次。"""
    global _beats_since_build
    _beats_since_build += 1


async def mark_identity_snapshot_stale(db: Any) -> None:
    """置位：下次 ensure 必须重建。"""
    try:
        await db.set_body_memory(DIRTY_KEY, True)
    except Exception:
        logger.debug("置位身份快照 dirty 失败", exc_info=True)


def _trust_band(trust: float) -> str:
    if trust < 0.25:
        return "信任还薄"
    if trust < 0.5:
        return "信任在长"
    if trust < 0.75:
        return "信任较稳"
    return "信任很深"


def _normalize_culture(shared_culture: str | list | None) -> str | list | None:
    if isinstance(shared_culture, str):
        s = shared_culture.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return s
    return shared_culture


def _culture_one_liner(shared_culture: str | list | None) -> str:
    shared_culture = _normalize_culture(shared_culture)
    if not shared_culture:
        return "还没有只属于你们的默契"
    if isinstance(shared_culture, str):
        line = shared_culture.strip().splitlines()[0] if shared_culture.strip() else ""
        line = line.lstrip("- ").strip()
        if not line:
            return "还没有只属于你们的默契"
        return (line[:40] + "…") if len(line) > 40 else line
    if isinstance(shared_culture, list) and shared_culture:
        item = shared_culture[0]
        if isinstance(item, dict):
            pat = str(item.get("pattern") or "")[:36]
            kind = item.get("type") or "默契"
            return f"{kind}：{pat}" if pat else "有一点共同气息"
        return str(item)[:40]
    return "还没有只属于你们的默契"


def _valence_band(v: float) -> str:
    if v < -0.3:
        return "低落"
    if v > 0.3:
        return "偏暖"
    return "平"


def _energy_band(e: float) -> str:
    if e < 0.3:
        return "疲"
    if e > 0.6:
        return "充"
    return "中"


def _trace_tag(traces: list[dict] | None, at_iso: str | None) -> str:
    """同一拍附近的压缩事件标签（可进快照，不进对话流水账）。"""
    if not traces or not at_iso:
        return ""
    key = str(at_iso)[:16]
    for t in reversed(traces):
        if str(t.get("at") or "")[:16] != key:
            continue
        kind = t.get("proactive_kind")
        action = t.get("action")
        if kind:
            return f"·{kind}"
        if action:
            return f"·{action}"
        if t.get("want_express"):
            return "·想开口"
    return ""


def format_recent_arc(
    emotions: list[dict],
    traces: list[dict] | None = None,
    *,
    limit: int = 8,
) -> str:
    """近 N 拍摘要；emotions 为时间倒序（load_recent_emotions）。"""
    if not emotions:
        return "近拍情绪轨迹还很短。"
    rows = list(reversed(emotions[:limit]))
    lines: list[str] = []
    for row in rows:
        ts = str(row.get("timestamp") or "")
        try:
            clock = datetime.fromisoformat(ts).strftime("%H:%M")
        except ValueError:
            clock = "??:??"
        v = float(row.get("valence") or 0)
        e = float(row.get("energy") or 0.5)
        tag = _trace_tag(traces, ts)
        lines.append(f"{clock} {_valence_band(v)}/{_energy_band(e)}{tag}")
    return "；".join(lines)


async def _self_summary(db: Any, max_chars: int = SELF_CHARS) -> str:
    row = await db.load_self_model()
    if not row or not row.get("identity_narrative"):
        return ""
    text = str(row["identity_narrative"]).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "……"


def assemble_identity_text(
    *,
    self_summary: str,
    stage: str,
    trust: float,
    season: str,
    culture_line: str,
    recent_arc: str,
) -> str:
    """纯函数拼装（零 LLM）。素材足时目标约 500–800 字。"""
    self_part = (self_summary or "").strip() or "（还在认识自己）"
    if len(self_part) > SELF_CHARS:
        self_part = self_part[:SELF_CHARS] + "……"

    rel = (
        f"和他：阶段 {stage}，{_trust_band(trust)}，内在节奏 {season}；"
        f"{culture_line}。"
    )
    arc = f"近拍：{recent_arc}"
    text = f"{self_part}\n{rel}\n{arc}"
    if len(text) > TARGET_MAX:
        budget = TARGET_MAX - len(self_part) - len(rel) - 2
        if budget < 40:
            text = f"{self_part}\n{rel}"
        else:
            text = f"{self_part}\n{rel}\n近拍：{recent_arc[:budget]}…"
    return text.strip()


async def ensure_identity_snapshot(
    db: Any,
    *,
    stage: str = "stranger",
    trust: float = 0.0,
    season: str = "spring",
    shared_culture: str | list | None = None,
    traces: list[dict] | None = None,
    force: bool = False,
) -> str:
    """消费点：dirty / N 拍 / 无缓存 → 规则重建并清 dirty。"""
    global _beats_since_build

    dirty = False
    try:
        dirty = bool(await db.get_body_memory(DIRTY_KEY))
    except Exception:
        logger.debug("读身份快照 dirty 失败", exc_info=True)

    cached: dict | None = None
    try:
        raw = await db.get_body_memory(CACHE_KEY)
        if isinstance(raw, dict) and raw.get("text"):
            cached = raw
    except Exception:
        logger.debug("读身份快照缓存失败", exc_info=True)

    need = force or dirty or cached is None or _beats_since_build >= CACHE_BEATS
    if not need and cached is not None:
        return str(cached["text"])

    self_summary = ""
    try:
        self_summary = await _self_summary(db)
    except Exception:
        logger.debug("读自我叙事失败", exc_info=True)

    emotions: list[dict] = []
    try:
        emotions = await db.load_recent_emotions(limit=8)
    except Exception:
        logger.debug("读近期情绪失败", exc_info=True)

    text = assemble_identity_text(
        self_summary=self_summary,
        stage=stage or "stranger",
        trust=float(trust or 0),
        season=season or "spring",
        culture_line=_culture_one_liner(shared_culture),
        recent_arc=format_recent_arc(emotions, traces, limit=8),
    )

    payload = {
        "text": text,
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        await db.set_body_memory(CACHE_KEY, payload)
        await db.set_body_memory(DIRTY_KEY, False)
    except Exception:
        logger.debug("写身份快照缓存失败", exc_info=True)

    _beats_since_build = 0
    return text


def reset_snapshot_runtime_for_tests() -> None:
    """测试用：清空进程内拍计数。"""
    global _beats_since_build
    _beats_since_build = 0
