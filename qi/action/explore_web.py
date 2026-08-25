"""explore 外部源：contemplative drift 时向外面看一眼。

红线：只返回真搜到的；失败/空 → None。不编造。不入库。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("qi.action.explore_web")

_TAVILY_URL = "https://api.tavily.com/search"


@dataclass(frozen=True)
class SearchHit:
    title: str
    snippet: str
    url: str


class WebSearchClient:
    """explore / delegate 外部联网搜索客户端（Tavily）。"""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str | None,
        config: dict | None = None,
    ) -> None:
        self.provider = (provider or "tavily").strip().lower()
        self.api_key = (api_key or "").strip() or None
        self.config = config or {}

    async def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        search_depth: str | None = None,
        topic: str | None = None,
        time_range: str | None = None,
        days: int | None = None,
    ) -> list[SearchHit] | None:
        q = (query or "").strip()
        if not q or not self.api_key:
            return None
        if self.provider == "tavily":
            return await self._search_tavily(
                q,
                top_k=top_k,
                search_depth=search_depth,
                topic=topic,
                time_range=time_range,
                days=days,
            )
        logger.warning("explore_web 未实现的 provider=%s", self.provider)
        return None

    def _exclude_domains(self) -> list[str]:
        """config 已是 explore_external 扁平子段（见 layer._build_explore_web）。"""
        raw = self.config.get("exclude_domains") or []
        if not isinstance(raw, list):
            return []
        return [str(d).strip().lower() for d in raw if str(d).strip()]

    def _default_depth(self) -> str:
        d = str(self.config.get("search_depth") or "basic").strip().lower()
        return d if d in ("basic", "advanced", "fast", "ultra-fast") else "basic"

    async def _search_tavily(
        self,
        query: str,
        *,
        top_k: int,
        search_depth: str | None,
        topic: str | None,
        time_range: str | None,
        days: int | None,
    ) -> list[SearchHit] | None:
        depth = (search_depth or self._default_depth()).strip().lower()
        if depth not in ("basic", "advanced", "fast", "ultra-fast"):
            depth = "basic"
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(int(top_k), 10)),
            "search_depth": depth,
            "include_answer": False,
        }
        if topic in ("general", "news", "finance"):
            payload["topic"] = topic
        if time_range in ("day", "week", "month", "year", "d", "w", "m", "y"):
            payload["time_range"] = time_range
        if days is not None and int(days) > 0:
            payload["days"] = int(days)
        exclude = self._exclude_domains()
        if exclude:
            payload["exclude_domains"] = exclude
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(_TAVILY_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("Tavily 搜索失败 query=%r", query[:80], exc_info=True)
            return None

        raw = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw, list) or not raw:
            return None

        hits: list[SearchHit] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("content") or item.get("snippet") or "").strip()
            url = str(item.get("url") or "").strip()
            if not (title or snippet or url):
                continue
            hits.append(SearchHit(title=title or url, snippet=snippet, url=url))
            if len(hits) >= top_k:
                break
        return hits or None


def _html_to_text(html: str) -> str:
    """极简抽正文：去 script/style，剥标签。不引入额外依赖。"""
    import re
    from html import unescape

    if not html:
        return ""
    text = re.sub(
        r"(?is)<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>",
        " ",
        html,
    )
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def fetch_page_text(
    url: str,
    *,
    timeout: float = 12.0,
    max_chars: int = 4000,
) -> str | None:
    """拉取公开页并抽纯文本；失败返回 None（不编造）。"""
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "qi-perch-delegate/1.0 (+local; research)",
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
        ) as client:
            resp = await client.get(u)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text/" not in ctype and ctype:
                # 空 content-type 时仍尝试按文本解
                if "json" in ctype or "image" in ctype or "octet" in ctype:
                    return None
            raw = resp.text or ""
    except Exception:
        logger.debug("深读拉取失败 url=%r", u[:120], exc_info=True)
        return None
    text = _html_to_text(raw)
    if len(text) < 40:
        return None
    return text[: max(500, int(max_chars))]
