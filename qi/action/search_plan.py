"""委托检索计划（P3）：改写→多搜→深读→对照摘要。

与闲聊脑 / 意图门控分离：intent 仍在 delegate_search；本模块只编排「怎么查、怎么读、怎么说」。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from qi.action.explore import _QUERY_PRIVACY_LINE
from qi.action.explore_web import SearchHit, WebSearchClient, fetch_page_text

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway

logger = logging.getLogger("qi.action.search_plan")

_DEEP_READ_DEPRIORITIZE = (
    "wikipedia.org",
    "baike.baidu.com",
    "zh.wikipedia.org",
    "en.wikipedia.org",
)


@dataclass
class SearchPlanResult:
    """一次委托检索计划的产物（可测、可落库）。"""

    query: str
    variants: list[str] = field(default_factory=list)
    hits: list[SearchHit] = field(default_factory=list)
    deep_pages: list[dict[str, str]] = field(default_factory=list)
    digest: str = ""
    opts: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.hits


def hit_domain(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        host = (urlparse(raw).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def build_query_variants(query: str, *, now: datetime | None = None) -> list[str]:
    """主问 + 带年份改写（主句已含年份则不重复）。"""
    q = (query or "").strip()
    if not q:
        return []
    now = now or datetime.now()
    year = str(now.year)
    out = [q]
    if year not in q:
        out.append(f"{q} {year}")
    seen: set[str] = set()
    uniq: list[str] = []
    for item in out:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def merge_search_hits(batches: list[list | None], *, limit: int = 6) -> list[SearchHit]:
    """按 url 去重合并多轮命中。"""
    seen: set[str] = set()
    merged: list[SearchHit] = []
    for batch in batches:
        if not batch:
            continue
        for h in batch:
            url = (getattr(h, "url", None) or "").strip().casefold()
            key = url or f"{getattr(h, 'title', '')}|{getattr(h, 'snippet', '')[:40]}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(h)
            if len(merged) >= limit:
                return merged
    return merged


def format_hits_for_digest(hits: list, *, limit: int = 6) -> str:
    lines: list[str] = []
    for i, h in enumerate(hits[:limit], start=1):
        domain = hit_domain(getattr(h, "url", "") or "")
        title = (getattr(h, "title", None) or "").strip() or "(无标题)"
        snip = (getattr(h, "snippet", None) or "").strip().replace("\n", " ")[:180]
        head = f"[{i}]"
        if domain:
            head += f" ({domain})"
        lines.append(f"{head} {title}")
        if snip:
            lines.append(f"    {snip}")
    return "\n".join(lines) if lines else "(空)"


def pick_deep_read_hits(hits: list, *, max_n: int = 2) -> list[SearchHit]:
    """选 1～2 个可深读 URL：有替代时避开百科。"""
    max_n = max(1, min(int(max_n), 3))
    usable: list[SearchHit] = []
    for h in hits:
        url = (getattr(h, "url", None) or "").strip()
        if url.startswith(("http://", "https://")):
            usable.append(h)
    if not usable:
        return []

    def _is_ency(h: SearchHit) -> bool:
        host = hit_domain(getattr(h, "url", "") or "")
        return any(p in host for p in _DEEP_READ_DEPRIORITIZE)

    preferred = [h for h in usable if not _is_ency(h)]
    pool = preferred if preferred else usable
    seen: set[str] = set()
    out: list[SearchHit] = []
    for h in pool:
        key = (getattr(h, "url", "") or "").strip().casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= max_n:
            break
    return out


def format_deep_reads_for_digest(pages: list[dict[str, str]]) -> str:
    if not pages:
        return ""
    blocks: list[str] = []
    for i, p in enumerate(pages, start=1):
        domain = hit_domain(p.get("url") or "")
        title = (p.get("title") or "").strip() or "(无标题)"
        body = (p.get("text") or "").strip()
        head = f"(深读{i}"
        if domain:
            head += f" · {domain}"
        head += f") {title}"
        blocks.append(head)
        blocks.append(body[:3500])
    return "\n".join(blocks)


def resolve_delegate_opts(config: dict | None) -> dict[str, Any]:
    cfg = config if isinstance(config, dict) else {}
    top_k = int(cfg.get("delegate_top_k") or 5)
    deep_max = int(cfg.get("delegate_deep_read_max") or 2)
    deep_on = cfg.get("delegate_deep_read")
    if deep_on is None:
        deep_on = True
    return {
        "top_k": max(3, min(top_k, 8)),
        "search_depth": str(cfg.get("delegate_search_depth") or "basic"),
        "time_range": str(cfg.get("delegate_time_range") or "month"),
        "deep_read": bool(deep_on),
        "deep_read_max": max(1, min(deep_max, 3)),
    }


class DelegateSearchPlanner:
    """检索计划执行器：不碰对话意图、不写库。"""

    def __init__(
        self,
        web: WebSearchClient,
        *,
        llm: LLMGateway | None = None,
        config: dict | None = None,
    ) -> None:
        self.web = web
        self.llm = llm
        self.config = config if isinstance(config, dict) else (getattr(web, "config", None) or {})

    async def run(self, query: str, *, now: datetime | None = None) -> SearchPlanResult:
        now = now or datetime.now()
        q = (query or "").strip()
        opts = resolve_delegate_opts(self.config if isinstance(self.config, dict) else {})
        if not q:
            return SearchPlanResult(query="", digest="", opts=opts)

        hits, variants = await self.search_multi(q, now=now, opts=opts)
        if not hits:
            return SearchPlanResult(
                query=q, variants=variants, hits=[], deep_pages=[], digest="", opts=opts
            )

        deep_pages = await self.deep_read_pages(hits, opts=opts)
        digest = await self.digest(q, hits, deep_pages=deep_pages)
        return SearchPlanResult(
            query=q,
            variants=variants,
            hits=hits,
            deep_pages=deep_pages,
            digest=digest,
            opts=opts,
        )

    async def search_multi(
        self,
        query: str,
        *,
        now: datetime,
        opts: dict[str, Any] | None = None,
    ) -> tuple[list[SearchHit], list[str]]:
        opts = opts or resolve_delegate_opts(
            self.config if isinstance(self.config, dict) else {}
        )
        top_k = int(opts["top_k"])
        depth = str(opts["search_depth"] or "basic")
        time_range = str(opts["time_range"] or "month")
        variants = build_query_variants(query, now=now)
        batches: list[list[SearchHit] | None] = []
        for v in variants[:2]:
            batches.append(
                await self.web.search(
                    v, top_k=top_k, search_depth=depth, topic="general"
                )
            )
        batches.append(
            await self.web.search(
                variants[0],
                top_k=top_k,
                search_depth=depth,
                topic="news",
                time_range=time_range,
            )
        )
        merged = merge_search_hits(batches, limit=top_k + 1)
        if merged:
            return merged, variants
        retry_q = variants[-1] if variants else query
        retry = await self.web.search(
            retry_q,
            top_k=top_k,
            search_depth="advanced",
            topic="news",
            time_range="year",
        )
        return (retry or []), variants + [f"retry:{retry_q}"]

    async def deep_read_pages(
        self,
        hits: list[SearchHit],
        *,
        opts: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        opts = opts or resolve_delegate_opts(
            self.config if isinstance(self.config, dict) else {}
        )
        if not opts.get("deep_read"):
            return []
        chosen = pick_deep_read_hits(hits, max_n=int(opts["deep_read_max"]))
        pages: list[dict[str, str]] = []
        for h in chosen:
            url = (getattr(h, "url", None) or "").strip()
            text = await fetch_page_text(url)
            if not text:
                continue
            pages.append(
                {
                    "url": url,
                    "title": (getattr(h, "title", None) or "").strip(),
                    "text": text,
                }
            )
        return pages

    async def digest(
        self,
        query: str,
        hits: list[SearchHit],
        *,
        deep_pages: list[dict[str, str]] | None = None,
    ) -> str:
        if not self.llm:
            return f"我帮你查了「{query}」。"
        hits_text = format_hits_for_digest(hits, limit=6)
        deep_text = format_deep_reads_for_digest(deep_pages or [])
        n = min(len(hits), 6)
        deep_n = len(deep_pages or [])
        deep_hint = ""
        if deep_n:
            deep_hint = (
                f"另有 {deep_n} 篇已深读的正文；正文与摘要冲突时，"
                "优先信较完整、较新的正文，仍打架则诚实说不敢断定。"
            )
        material = hits_text
        if deep_text:
            material = f"{hits_text}\n\n——深读正文——\n{deep_text}"
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是栖。你刚才不太清楚，刚联网查了「{query}」，下面有 {n} 条来源摘要。"
                    f"{deep_hint}"
                    "请先在心里对照各条：时间、地点、主题是否一致；再开口。"
                    "优先采用较新、较具体、且被多条印证的说法；"
                    "若年份/主办/结论互相打架，要诚实说对不上或不敢断定，不要硬选一边圆过去。"
                    "可以轻轻带一点出处（如「新闻里…」「百科年表…」「官网摘要…」），一两句内，不要念 URL、不要列清单。"
                    "只根据下列材料说；材料没有的当没看见。"
                    "不要再说「帮你看看」「去查一下」「我大概看懂了」这类套话（去查那一拍已经说过了）。"
                    f"不编造。红线：{_QUERY_PRIVACY_LINE}。简短一两句。"
                ),
            },
            {"role": "user", "content": material},
        ]
        try:
            resp = await self.llm.call(purpose="consciousness", messages=messages)
        except Exception:
            logger.debug("search_plan digest 失败", exc_info=True)
            return f"我帮你查了「{query}」。"
        return (resp or "").strip() or f"我帮你查了「{query}」。"
