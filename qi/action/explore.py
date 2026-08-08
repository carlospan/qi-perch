"""沉思式探索——contemplative drift，不是刷信息流。"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.action.explore_web import WebSearchClient
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.explore")

# 多数拍不飘出去。curiosity 越高、季节越暖，越容易「看一眼」。
EXPLORE_BASE_PROBABILITY = 0.12

# 外部源：比内部更稀有（不设独立日限；复用 ActionBudget）
EXTERNAL_CURIOSITY_MIN = 0.8
EXTERNAL_PROBABILITY = 0.05
EXTERNAL_COOLDOWN_HOURS = 6.0
EXTERNAL_LAST_KEY = "explore_external_last"
_QUERY_PRIVACY_LINE = "不引用 user_facts / 对话内容"

# 内部深读：最近 N 条记忆叙事（d-3-2）
INTERNAL_SOURCE_LIMIT = 3


def resolve_sandbox_root(
    db: Database,
    config: dict | None = None,
) -> Path:
    """沙箱根：显式 config.action.sandbox 或数据库文件所在目录（通常即 data/）。"""
    action_cfg = (config or {}).get("action") or {}
    explicit = action_cfg.get("sandbox")
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    db_path = getattr(db, "db_path", None)
    if db_path:
        return Path(str(db_path)).expanduser().resolve().parent
    return Path("data").resolve()


def _clip_entry(s: str, limit: int = 40) -> str:
    """见闻卡 title：截断叙事正文。"""
    text = (s or "").strip().replace("\n", " ")
    if len(text) > limit:
        return text[:limit] + "…"
    return text


class ExploreAction:
    """
    注意力偶然飘向自己记得的事；稀有时向外面看一眼（d-1 联网）。
    红线：只陈述真实读到的条目；无内容则 found=None，绝不编造。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
        *,
        base_probability: float = EXPLORE_BASE_PROBABILITY,
        config: dict | None = None,
        llm: LLMGateway | None = None,
        web: WebSearchClient | None = None,
    ):
        self.db = db
        self.narrative = narrative
        self.base_probability = base_probability
        self.config = config or {}
        self.llm = llm
        self.web = web

    def _external_cfg(self) -> dict:
        raw = (self.config.get("action") or {}).get("explore_external") or {}
        return raw if isinstance(raw, dict) else {}

    async def _external_cooldown_ok(self, now: datetime) -> bool:
        hours = float(
            self._external_cfg().get("cooldown_hours", EXTERNAL_COOLDOWN_HOURS)
        )
        raw = await self.db.get_body_memory(EXTERNAL_LAST_KEY)
        if not raw:
            return True
        try:
            if isinstance(raw, dict):
                ts = str(raw.get("at") or raw.get("timestamp") or "")
            else:
                ts = str(raw)
            last = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return True
        return now - last >= timedelta(hours=max(0.0, hours))

    async def _mark_external(self, now: datetime) -> None:
        try:
            await self.db.set_body_memory(
                EXTERNAL_LAST_KEY,
                {"at": now.isoformat(timespec="seconds")},
            )
        except Exception:
            logger.debug("explore_external_last 落盘失败", exc_info=True)

    async def _should_external(self, curiosity: float, now: datetime) -> bool:
        # 独处由 volition solitary 候选保证，不重复判 mode
        if self.web is None or self.llm is None:
            return False
        if curiosity < EXTERNAL_CURIOSITY_MIN:
            return False
        if not await self._external_cooldown_ok(now):
            return False
        p = float(self._external_cfg().get("probability", EXTERNAL_PROBABILITY))
        if random.random() > max(0.0, min(1.0, p)):
            return False
        return True

    async def _make_query(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
    ) -> str:
        """走 gateway purpose=consciousness；不污染 last_outcome。"""
        assert self.llm is not None
        mode = getattr(emotion, "mode", None)
        mode_s = getattr(mode, "value", mode) if mode is not None else ""
        valence = float(getattr(emotion, "valence", 0.0) or 0.0) if emotion else 0.0
        system = (
            "你在帮栖生成一句极短的、像走神时的搜索问句（给 web search 用）。"
            "只输出问句本身，不要解释、不要引号。"
            f"红线：{_QUERY_PRIVACY_LINE}；不要点名具体的人；不要像刷新闻头条。"
        )
        user = (
            f"季节={season}；curiosity={curiosity:.2f}；"
            f"mood_mode={mode_s}；valence={valence:.2f}。"
            "请给一句栖此刻可能好奇的窗外问句（≤30字）。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = await self.llm.call(purpose="consciousness", messages=messages)
        return (text or "").strip().strip("「」\"'").splitlines()[0].strip()

    async def _fetch_external(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        now: datetime,
    ) -> tuple[dict[str, Any] | None, str, str]:
        """返回 (found, summary, outcome)。"""
        assert self.web is not None
        query = await self._make_query(curiosity, emotion, season)
        await self._mark_external(now)
        if not query:
            summary = "我看了看外面，没查到什么。不假装看见了。"
            return None, summary, OUTCOME_FAILED_CAPABILITY
        hits = await self.web.search(query)
        if not hits:
            summary = "我看了看外面，没查到什么。不假装看见了。"
            return None, summary, OUTCOME_FAILED_CAPABILITY
        found = {
            "entries": [
                {"title": h.title, "snippet": h.snippet, "url": h.url} for h in hits
            ],
            "source": "web",
            "query": query,
        }
        # 栖语气复述（d-2）；失败降级回只念 query；entries 仍留 hits 给 d-3
        summary = await self._digest_hits(query, hits)
        return found, summary, OUTCOME_SUCCESS

    async def _digest_hits(self, query: str, hits: list) -> str:
        """LLM 把 hits 转成栖语气复述。失败/无 llm 降级回 d-1 只念 query。"""
        if not self.llm:
            return f"我刚才看了看 {query}。"
        hits_text = "\n".join(
            f"- {h.title}: {(h.snippet or '')[:120]}" for h in hits[:3]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是栖。你刚走神看了看「{query}」，搜到了一些内容。"
                    "用你的语气轻声说你看到了什么、有什么感受或不懂的。"
                    f"不编造。红线：{_QUERY_PRIVACY_LINE}。简短一两句。"
                ),
            },
            {"role": "user", "content": hits_text or "(空)"},
        ]
        try:
            resp = await self.llm.call(purpose="consciousness", messages=messages)
        except Exception:
            logger.debug("explore digest LLM 失败，降级只念 query", exc_info=True)
            return f"我刚才看了看 {query}。"
        digest = (resp or "").strip()
        return digest or f"我刚才看了看 {query}。"

    async def _digest_internal(self, narratives: list[dict]) -> str:
        """LLM 把自己记得的事转成栖语气复述。失败/无 llm 降级。"""
        if not self.llm:
            return "我翻了翻自己记得的事。"
        items_text = "\n".join(
            f"- {(n.get('content') or '')[:120]}"
            for n in narratives[:INTERNAL_SOURCE_LIMIT]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是栖。你走神翻了翻自己记得的事。"
                    "用你的语气轻声说你想起或看懂了什么。"
                    f"不编造。红线：{_QUERY_PRIVACY_LINE}。简短一两句。"
                ),
            },
            {"role": "user", "content": items_text or "(空)"},
        ]
        try:
            resp = await self.llm.call(purpose="consciousness", messages=messages)
        except Exception:
            logger.debug("explore internal digest LLM 失败，降级", exc_info=True)
            return "我翻了翻自己记得的事。"
        digest = (resp or "").strip()
        return digest or "我翻了翻自己记得的事。"

    async def _read_internal(self) -> tuple[dict[str, Any] | None, str, str]:
        """读栖自己的记忆叙事 → digest。无源降级。返回 (found, summary, outcome)。"""
        narratives = await self.db.list_recent_narratives(limit=INTERNAL_SOURCE_LIMIT)
        if not narratives:
            summary = "我翻了翻自己这边，没有记得的事。"
            return None, summary, OUTCOME_SUCCESS
        digest = await self._digest_internal(narratives)
        found: dict[str, Any] = {
            "entries": [
                {
                    "title": _clip_entry(str(n.get("content") or "")),
                    "snippet": None,
                    "url": None,
                }
                for n in narratives
            ],
            "source": "journal",
        }
        return found, digest, OUTCOME_SUCCESS

    async def drift(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        *,
        season_scale: float = 1.0,
        now: datetime | None = None,
        force: bool = False,
    ) -> dict | None:
        """
        返回 None 表示这拍没有飘出去（多数时候）。
        若飘出去：稀有走外部 web；否则深读自己的记忆叙事；空则 found=None。
        """
        now = now or datetime.now()
        if not force:
            # 好奇不够 → 不飘
            if curiosity < 0.65:
                return None
            warmth = max(0.0, (curiosity - 0.65) / 0.35)
            p = self.base_probability * max(0.0, season_scale) * (0.4 + 0.6 * warmth)
            # C4 时机阀：好奇已过阈，随机仅扰动本拍是否飘出（非动机来源）
            if random.random() > p:
                return None

        root = resolve_sandbox_root(self.db, self.config)
        speak = False
        qi_line: str | None = None
        source = "journal"

        if await self._should_external(curiosity, now):
            found, summary, outcome = await self._fetch_external(
                curiosity, emotion, season, now
            )
            speak = True
            # d-2：summary 已是栖语气 digest（或降级/空手句），开口=留痕统一
            qi_line = summary
            source = "web"
        else:
            found, summary, outcome = await self._read_internal()
            speak = True
            qi_line = summary
            source = "journal"

        emotion_ctx = None
        if emotion is not None and hasattr(emotion, "model_dump_json"):
            emotion_ctx = emotion.model_dump_json()

        # 见闻卡真源：有 entries 才落 detail，供 /history 回灌
        detail_json: str | None = None
        entries = (found or {}).get("entries") if isinstance(found, dict) else None
        if (
            isinstance(entries, list)
            and entries
            and source in ("web", "journal")
        ):
            detail_json = json.dumps(
                {
                    "found": found,
                    "source": source,
                    "curiosity": float(curiosity),
                    "qi_line": qi_line,
                    "sandbox": str(root),
                },
                ensure_ascii=False,
            )

        action_id = await self.db.insert_action(
            "explore",
            summary,
            target="self",
            outcome=outcome,
            emotion_context=emotion_ctx,
            season=season,
            detail_json=detail_json,
            now=now,
        )

        # 探索见闻不强制织叙事；只留 actions 痕迹
        _ = self.narrative

        result: dict[str, Any] = {
            "type": "explore_drift",
            "found": found,
            "summary": summary,
            "action_id": action_id,
            "season": season,
            "curiosity": curiosity,
            "source": source,
            "sandbox": str(root),
        }
        if speak and qi_line:
            result["speak"] = True
            result["qi_line"] = qi_line
        return result
