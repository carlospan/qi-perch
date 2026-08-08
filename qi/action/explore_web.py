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
    """explore 外部联网搜索客户端（d-1 首接 Tavily）。"""

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

    async def search(self, query: str, *, top_k: int = 3) -> list[SearchHit] | None:
        q = (query or "").strip()
        if not q or not self.api_key:
            return None
        if self.provider == "tavily":
            return await self._search_tavily(q, top_k=top_k)
        logger.warning("explore_web 未实现的 provider=%s", self.provider)
        return None

    async def _search_tavily(self, query: str, *, top_k: int) -> list[SearchHit] | None:
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(int(top_k), 10)),
            "search_depth": "basic",
            "include_answer": False,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
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
