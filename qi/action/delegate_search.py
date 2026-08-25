"""委托式联网检索——你请她查，与自主 explore 分轨。

意图门控在本模块；改写→多搜→深读→摘要见 `search_plan.DelegateSearchPlanner`。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from qi.action.explore import _QUERY_PRIVACY_LINE
from qi.action.explore_web import WebSearchClient
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS
from qi.action.search_plan import (
    DelegateSearchPlanner,
    build_query_variants,
    format_deep_reads_for_digest,
    format_hits_for_digest,
    merge_search_hits,
    pick_deep_read_hits,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.delegate_search")

__all__ = [
    "DelegateSearchAction",
    "anchor_search_query",
    "build_query_variants",
    "detect_delegate_search_intent",
    "extract_search_query",
    "format_deep_reads_for_digest",
    "format_hits_for_digest",
    "looks_like_delegate_search",
    "looks_like_followup_search",
    "merge_search_hits",
    "pick_deep_read_hits",
    "query_shares_topic",
]

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

# 追问 / 刷到：应再搜，不背旧摘要
_FOLLOWUP_SEARCH_RE = re.compile(
    r"再(查|搜|刷一下|刷)|重新查|再看看网上|刷到了?|抖音|小红书|微博|"
    r"又(看到|听说|刷到)|你再(查|搜|看一下)|最新(的|进展|消息)|有新消息吗"
)

_RECENCY_CUE_RE = re.compile(
    r"最近|近来|刚(刚)?|这几天|今年|当下|实时|新闻|热点|大会|展会"
)

# 指代追问：未点名实体，须锚回 recent_query
_ELLIPTICAL_FOLLOWUP_RE = re.compile(
    r"^(那|这|它|还有)|那是|这个是|今年的还是|往届|刚才(那个|那次)|同上"
)

# 合并问句时丢掉的虚词（不参与「是否同主题」）
_TOPIC_STOP = frozenset(
    {
        "相关",
        "信息",
        "有哪些",
        "什么",
        "怎么",
        "如何",
        "最新",
        "一下",
        "资料",
        "入门",
    }
)


def query_shares_topic(query: str, recent: str) -> bool:
    """抽取问句是否已带上 recent 里的实体词（年份单独不算主题）。"""
    q = (query or "").strip()
    r = (recent or "").strip()
    if not q or not r:
        return False
    q_cf = q.casefold()
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}|\d{4}", r)
    for p in parts:
        if p.isdigit() and len(p) == 4:
            continue
        if p in _TOPIC_STOP:
            continue
        if len(p) >= 2 and (p.casefold() in q_cf or p in q):
            return True
    return False


def needs_topic_anchor(user_text: str, query: str, recent: str | None) -> bool:
    r = (recent or "").strip()
    if not r:
        return False
    if query_shares_topic(query, r):
        return False
    t = (user_text or "").strip()
    if looks_like_followup_search(t):
        return True
    if _ELLIPTICAL_FOLLOWUP_RE.search(t):
        return True
    return False


def anchor_search_query(
    query: str | None,
    recent: str | None,
    user_text: str,
) -> str:
    """追问未带主题时，把 recent 锚回搜索问句；换题不粘。"""
    q = (query or "").strip()
    r = (recent or "").strip()
    if not needs_topic_anchor(user_text, q, r):
        return (q or r)[:120]
    if not q:
        return r[:120]
    if q in r:
        return r[:120]
    if r in q:
        return q[:120]
    return f"{r} {q}"[:120]


def looks_like_followup_search(message: str | None) -> bool:
    """用户像在追问外部时事 / 要求再刷——应再跑检索。"""
    t = (message or "").strip()
    if len(t) < 4:
        return False
    if _FOLLOWUP_SEARCH_RE.search(t):
        return True
    # 「刷到…最近有个…」类陈述也当要查
    if ("刷到" in t or "听说" in t) and _RECENCY_CUE_RE.search(t):
        return True
    return False


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


async def _llm_delegate_intent(
    text: str,
    llm: LLMGateway,
    *,
    recent_query: str | None = None,
) -> str | None:
    recent_hint = ""
    if (recent_query or "").strip():
        recent_hint = (
            f"\n刚才她查过：「{(recent_query or '').strip()[:60]}」。"
            "若用户在追问同一外部话题、或说刷到/又听说/再查/那是今年还是往届，仍判 search；"
            "query 必须带上刚才主题的具体实体（如大会名），"
            "不要只输出「今年还是往届」「最新进展」这类丢掉主题的空指代；勿因她刚查过就 neither。\n"
        )
    prompt = (
        "判断用户是否在请人查公开资料（新闻/热点/天气/汇率/百科事实等需联网的信息）。\n"
        '只输出一行 JSON：{"intent":"search"|"neither","query":"≤40字搜索问句或空"}\n'
        "规则：\n"
        "- search：想查实时或公开信息（新闻、热点、天气、某事最新进展等）；"
        "也包括「你了解吗/听说了吗/刷到…」这类对外部时事的打听\n"
        "- neither：闲聊、问栖状态/故障、两人回忆、读文件、看屏幕、打开应用、无关\n"
        "- query：仅 intent=search 时填短问句；尽量带具体实体与年份线索；不要引号；不编造\n"
        f"{recent_hint}"
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
    recent_query: str | None = None,
) -> str | None:
    """懂意思：强启发短路 +（request | 问句形态 | 追问刷到）弱门控 + LLM 判别。"""
    text = (message or "").strip()
    if len(text) < 4 or _delegate_excluded(text):
        return None
    if looks_like_delegate_search(text):
        if llm is not None:
            q = await extract_search_query(
                text, llm, recent_query=recent_query
            )
            if q:
                return anchor_search_query(q, recent_query, text)
        return anchor_search_query(
            _heuristic_query_from_strong(text), recent_query, text
        )

    follow = looks_like_followup_search(text)
    intent = (perception_intent or "").strip().lower() or None
    if (
        intent is None
        and not _question_shape_delegate_candidate(text)
        and not follow
    ):
        return None
    if not follow and not _weak_delegate_candidate(text, perception_intent=intent):
        return None
    if llm is None:
        if follow and (recent_query or "").strip():
            return (recent_query or "").strip()[:120]
        return None
    q = await _llm_delegate_intent(text, llm, recent_query=recent_query)
    if not q:
        return None
    return anchor_search_query(q, recent_query, text)


async def extract_search_query(
    message: str,
    llm: LLMGateway | None,
    *,
    recent_query: str | None = None,
) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    if llm is None:
        for cue in _SEARCH_CUES:
            if cue in text:
                q = text.split(cue, 1)[-1].strip(" ：:，。.?？")
                return q[:120] if q else None
        return None
    recent = (recent_query or "").strip()
    recent_line = ""
    if recent:
        recent_line = (
            f"刚才查过的主题：「{recent[:60]}」。"
            "若用户是追问/再查/指代（那是、今年还是往届等），"
            "问句必须写上该主题实体，不能只写空指代。\n"
        )
    system = (
        "从用户白话里提取要上网搜索的短问句（≤40字）。"
        f"{recent_line}"
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
    """落库 / 卡片 / 叙事；检索编排委托给 DelegateSearchPlanner。"""

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

    def _planner(self) -> DelegateSearchPlanner | None:
        if self.web is None:
            return None
        cfg = getattr(self.web, "config", None)
        return DelegateSearchPlanner(
            self.web,
            llm=self.llm,
            config=cfg if isinstance(cfg, dict) else {},
        )

    async def _digest_hits(
        self,
        query: str,
        hits: list,
        *,
        deep_pages: list[dict[str, str]] | None = None,
    ) -> str:
        """薄委托：兼容旧测直接调摘要。"""
        planner = self._planner()
        if planner is None:
            return f"我帮你查了「{query}」。"
        return await planner.digest(query, hits, deep_pages=deep_pages)

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
        planner = self._planner()
        if planner is None:
            return {
                "type": "delegate_result",
                "summary": "外部搜索未配置",
                "qi_line": "我现在还查不了网上的东西。",
                "speak": True,
                "outcome": OUTCOME_FAILED_CAPABILITY,
            }

        plan = await planner.run(q, now=now)
        variants = plan.variants
        hits = plan.hits
        deep_pages = plan.deep_pages
        digest = plan.digest

        if not hits:
            await self.db.insert_action(
                "delegate_search",
                f"search:{q[:80]}",
                target="web",
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
                detail_json=json.dumps(
                    {
                        "query": q,
                        "variants": variants,
                        "motive": motive or {},
                    },
                    ensure_ascii=False,
                ),
            )
            return {
                "type": "delegate_result",
                "summary": f"未搜到：{q}",
                "qi_line": f"我查了「{q}」，没搜到什么。不假装看见了。",
                "speak": True,
                "outcome": OUTCOME_FAILED_CAPABILITY,
            }

        found = {
            "entries": [
                {"title": h.title, "snippet": h.snippet, "url": h.url}
                for h in hits
            ],
            "source": "web_delegate",
            "query": q,
            "variants": variants,
            "deep_read": [
                {
                    "url": p["url"],
                    "title": p.get("title") or "",
                    "chars": len(p.get("text") or ""),
                }
                for p in deep_pages
            ],
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
