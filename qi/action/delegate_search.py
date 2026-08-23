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

# 弱门控：只判断「值不值得问 delegate LLM」，不用话题词表（契约：懂意思不靠口令）
_QUESTION_SHAPE_RE = re.compile(
    r"[？?]$|"
    r"(什么|多少|哪[里儿]?|几|咋样|怎么样|如何|吗)\s*[？?]?$"
)

# 勿把问栖状态/故障当成查资料
_DELEGATE_EXCLUDE_RE = re.compile(
    r"答非所问|跑题了|你怎么了|你坏了吗|是不是坏了|你卡住了|你卡了吗|"
    r"没接好|听不懂|听不懂吗"
)
_META_ASK_EXACT = frozenset(
    {
        "发生了什么",
        "怎么回事",
        "怎么回事啊",
        "怎么了",
        "你怎么了",
    }
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


def _delegate_excluded(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t in _META_ASK_EXACT:
        return True
    return bool(_DELEGATE_EXCLUDE_RE.search(t))


def _question_shape_delegate_candidate(text: str) -> bool:
    """问句形态：像对外部世界要事实，而非话题关键词表。"""
    t = (text or "").strip()
    if len(t) < 4 or len(t) > 160:
        return False
    return bool(_QUESTION_SHAPE_RE.search(t))


def _weak_delegate_candidate(
    text: str, *, perception_intent: str | None = None
) -> bool:
    """弱门控：感知 request 或问句形态；排除元状态问栖。"""
    t = (text or "").strip()
    if not t or _delegate_excluded(t):
        return False
    if (perception_intent or "").strip().lower() == "request":
        return True
    return _question_shape_delegate_candidate(t)


def _heuristic_query_from_strong(text: str) -> str | None:
    for cue in _SEARCH_CUES:
        if cue in text:
            q = text.split(cue, 1)[-1].strip(" ：:，。.?？")
            if q:
                return q[:120]
    m = re.search(r"(帮我|请).{0,8}(查|搜)\s*(.+)", text)
    if m:
        q = m.group(2).strip(" ：:，。.?？")
        if q:
            return q[:120]
    return text[:120]


async def _llm_delegate_intent(text: str, llm: LLMGateway) -> str | None:
    prompt = (
        "判断用户是否在请人查公开资料（新闻/热点/天气/汇率/百科事实等需联网的信息）。\n"
        '只输出一行 JSON：{"intent":"search"|"neither","query":"≤40字搜索问句或空"}\n'
        "规则：\n"
        "- search：想查实时或公开信息（新闻、热点、天气、某事最新进展等）\n"
        "- neither：闲聊、问栖状态/故障、两人回忆、读文件、看屏幕、打开应用、无关\n"
        "- query：仅 intent=search 时填短问句；不要引号；不编造\n"
        f"红线：{_QUERY_PRIVACY_LINE}。\n"
        f"用户：「{text}」"
    )
    try:
        raw = await llm.call(
            purpose="fact",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
    except Exception:
        logger.debug("delegate_search intent LLM 失败", exc_info=True)
        return None
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        data = json.loads(raw[start : end + 1])
    except Exception:
        return None
    intent = str(data.get("intent") or "").strip().lower()
    if intent != "search":
        return None
    q = str(data.get("query") or "").strip().strip("「」\"'")
    return (q[:120] if q else text[:120])


async def detect_delegate_search_intent(
    message: str | None,
    *,
    llm: LLMGateway | None = None,
    perception_intent: str | None = None,
) -> str | None:
    """懂意思：强启发短路 +（request | 问句形态）弱门控 + LLM 判别 search/neither。"""
    text = (message or "").strip()
    if len(text) < 4 or _delegate_excluded(text):
        return None
    if looks_like_delegate_search(text):
        if llm is not None:
            q = await extract_search_query(text, llm)
            if q:
                return q
        return _heuristic_query_from_strong(text)

    intent = (perception_intent or "").strip().lower() or None
    if intent is None and not _question_shape_delegate_candidate(text):
        return None
    if not _weak_delegate_candidate(text, perception_intent=intent):
        return None
    if llm is None:
        return None
    return await _llm_delegate_intent(text, llm)


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
