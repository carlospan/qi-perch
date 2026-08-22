"""委托式联网检索——你请她查，与自主 explore 分轨。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.explore import _QUERY_PRIVACY_LINE
from qi.action.explore_web import WebSearchClient
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.delegate_search")

_SEARCH_CUES = (
    "查一下",
    "查查",
    "搜一下",
    "搜索",
    "帮我查",
    "帮我搜",
    "上网查",
    "网上查",
    "查资料",
    "帮我看看网上",
)


def looks_like_delegate_search(message: str | None) -> bool:
    text = (message or "").strip()
    if len(text) < 4:
        return False
    if any(cue in text for cue in _SEARCH_CUES):
        return True
    if re.search(r"(帮我|请).{0,8}(查|搜)", text):
        return True
    return False


async def extract_search_query(message: str, llm: LLMGateway | None) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if llm is None:
        for cue in _SEARCH_CUES:
            if cue in text:
                q = text.split(cue, 1)[-1].strip(" ：:，。.?？")
                return q[:120] if q else None
        return None
    system = (
        "从用户白话里提取要上网搜索的短问句（≤40字）。"
        "只输出问句本身，不要解释、不要引号。"
        f"红线：{_QUERY_PRIVACY_LINE}。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    try:
        resp = await llm.call(purpose="consciousness", messages=messages)
    except Exception:
        logger.debug("delegate_search query LLM 失败", exc_info=True)
        return None
    q = (resp or "").strip().strip("「」\"'").splitlines()[0].strip()
    return q[:120] if q else None


class DelegateSearchAction:
    def __init__(
        self,
        db: Database,
        *,
        web: WebSearchClient | None = None,
        llm: LLMGateway | None = None,
        narrative: NarrativeMemory | None = None,
    ) -> None:
        self.db = db
        self.web = web
        self.llm = llm
        self.narrative = narrative

    async def _digest_hits(self, query: str, hits: list) -> str:
        if not self.llm:
            return f"我帮你查了「{query}」。"
        hits_text = "\n".join(
            f"- {h.title}: {(h.snippet or '')[:120]}" for h in hits[:3]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是栖。你刚应他的请，查了「{query}」。"
                    "用你的语气轻声说你看懂了什么。"
                    f"不编造。红线：{_QUERY_PRIVACY_LINE}。简短一两句。"
                ),
            },
            {"role": "user", "content": hits_text or "(空)"},
        ]
        try:
            resp = await self.llm.call(purpose="consciousness", messages=messages)
        except Exception:
            return f"我帮你查了「{query}」。"
        return (resp or "").strip() or f"我帮你查了「{query}」。"

    async def execute(
        self,
        query: str,
        *,
        season: str = "spring",
        now: datetime | None = None,
        user_text: str = "",
        motive: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        q = (query or "").strip()
        if not q:
            return {
                "type": "delegate_result",
                "summary": "没听清要查什么",
                "qi_line": "你想让我查什么？",
                "speak": True,
                "outcome": OUTCOME_FAILED_CAPABILITY,
            }
        if self.web is None:
            return {
                "type": "delegate_result",
                "summary": "外部搜索未配置",
                "qi_line": "我现在还查不了网上的东西。",
                "speak": True,
                "outcome": OUTCOME_FAILED_CAPABILITY,
            }
        hits = await self.web.search(q)
        if not hits:
            await self.db.insert_action(
                "delegate_search",
                f"search:{q[:80]}",
                target="web",
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
                detail_json=json.dumps(
                    {"query": q, "motive": motive or {}}, ensure_ascii=False
                ),
            )
            return {
                "type": "delegate_result",
                "summary": f"未搜到：{q}",
                "qi_line": f"我查了「{q}」，没搜到什么。不假装看见了。",
                "speak": True,
                "outcome": OUTCOME_FAILED_CAPABILITY,
            }

        digest = await self._digest_hits(q, hits)
        found = {
            "entries": [
                {"title": h.title, "snippet": h.snippet, "url": h.url}
                for h in hits
            ],
            "source": "web_delegate",
            "query": q,
        }
        action_id = await self.db.insert_action(
            "delegate_search",
            digest[:200],
            target="web",
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {
                    "query": q,
                    "motive": motive or {},
                    "found": found,
                },
                ensure_ascii=False,
            ),
        )
        card = {
            "type": "explore_drift",
            "found": found,
            "summary": digest,
            "qi_line": digest,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "season": season,
            "action_id": action_id,
            "curiosity": 0.0,
            "source": "web_delegate",
            "sandbox": "",
            "delegate": True,
        }
        if self.narrative is not None:
            from qi.action.judgment import write_delegate_fulfillment_narrative

            await write_delegate_fulfillment_narrative(
                self.narrative,
                kind="查资料",
                summary=digest,
                user_hint=user_text or q,
            )
        return card
