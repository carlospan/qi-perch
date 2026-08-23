"""L7 together——邀你同看她世界里的一页（确认后打开）。

契约：懂意思；同伴文案；不与 open 抢「纯打开」。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_together,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.together")

STICKY_MINUTES = 12.0
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)
_TOGETHER_CUES = re.compile(
    r"(一起看|同看|陪我看|一起瞧瞧|一块看|共同看)",
    re.I,
)
_OPEN_ONLY = re.compile(r"^(打开|帮我开|开一下)\b", re.I)


@dataclass
class TogetherRequest:
    intent: str = "together"  # together | neither
    target_type: str = "url"  # url | app
    target: str = ""
    title: str = ""
    source: str = ""  # explore | share | open | user
    meta: dict[str, Any] = field(default_factory=dict)


def looks_like_together_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _TOGETHER_CUES.search(t):
        return True
    # 「一起看：url」卡片句
    if t.startswith("一起看") and _URL_RE.search(t):
        return True
    return False


def looks_like_pure_open(text: str) -> bool:
    """纯打开义 → 应走 open，不抢 together。"""
    t = (text or "").strip()
    if not t:
        return False
    if _TOGETHER_CUES.search(t):
        return False
    return bool(_OPEN_ONLY.search(t) and _URL_RE.search(t))


async def detect_together_intent(
    text: str,
    *,
    pool: list[dict[str, Any]] | None = None,
    llm: LLMGateway | None = None,
) -> TogetherRequest | None:
    t = (text or "").strip()
    if not t:
        return None
    if looks_like_pure_open(t):
        return None

    url_m = _URL_RE.search(t)
    if looks_like_together_intent(t) or (
        llm is not None and _weak_together(t)
    ):
        if url_m:
            url = url_m.group(0).rstrip("，。、；;)）]")
            return TogetherRequest(
                target_type="url",
                target=url,
                title="",
                source="user",
            )
        picked = resolve_from_pool(t, pool or [])
        if picked is not None:
            return picked
        if looks_like_together_intent(t):
            # 有同看义但池空/对不上 → 仍返回空 target，execute 会老实说
            return TogetherRequest(source="user")
        if llm is not None:
            return await _llm_together(t, llm, pool or [])
    return None


def _weak_together(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and len(t) <= 80 and (
        "看" in t and ("一起" in t or "同" in t or "陪" in t)
    )


async def _llm_together(
    text: str, llm: LLMGateway, pool: list[dict[str, Any]]
) -> TogetherRequest | None:
    pool_hint = json.dumps(pool[:5], ensure_ascii=False) if pool else "[]"
    prompt = (
        "判断用户是否要和栖「一起看」某个链接/应用（同伴同看，不是单纯帮开）。"
        "只输出一行 JSON：\n"
        '{"intent":"together"|"neither","target":"url或空","title":""}\n'
        f"可选对象池：{pool_hint}\n"
        f"用户：{text}"
    )
    try:
        raw = await llm.call(
            "fact",
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception:
        return None
    m = re.search(r"\{[^{}]+\}", (raw or "").strip())
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    if str(data.get("intent") or "") != "together":
        return None
    target = str(data.get("target") or "").strip()
    if not target and pool:
        return resolve_from_pool("一起看", pool)
    if not target:
        return TogetherRequest(source="user")
    tt = "url" if target.startswith("http") else "app"
    return TogetherRequest(
        target_type=tt,
        target=target,
        title=str(data.get("title") or ""),
        source="user",
    )


def resolve_from_pool(
    text: str, pool: list[dict[str, Any]]
) -> TogetherRequest | None:
    fresh = [e for e in pool if _entry_fresh(e)]
    if not fresh:
        return None
    t = (text or "").strip()
    m = re.search(r"第\s*([1-9])\s*(个|条)", t)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(fresh):
            return _req_from_entry(fresh[idx])
    if re.search(r"刚才|那个|这个|刚看", t):
        return _req_from_entry(fresh[-1])
    # 标题子串
    for e in reversed(fresh):
        title = str(e.get("title") or "")
        if title and title in t:
            return _req_from_entry(e)
    if looks_like_together_intent(t) or t in ("好", "一起看吧", "看吧", "行"):
        return _req_from_entry(fresh[-1])
    return None


def _entry_fresh(entry: dict[str, Any], now: datetime | None = None) -> bool:
    at = entry.get("at")
    if not isinstance(at, datetime):
        return False
    now = now or datetime.now()
    return (now - at).total_seconds() <= STICKY_MINUTES * 60


def _req_from_entry(e: dict[str, Any]) -> TogetherRequest:
    return TogetherRequest(
        target_type=str(e.get("target_type") or "url"),
        target=str(e.get("target") or ""),
        title=str(e.get("title") or ""),
        source=str(e.get("source") or ""),
    )


def candidates_from_action_result(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """从 explore / open / share 结果抽出可同看条目（无 at，由 brain 盖戳）。"""
    if not result:
        return []
    now_placeholder: list[dict[str, Any]] = []
    rtype = result.get("type")

    if rtype == "explore_drift":
        # 委托查资料复用 explore_drift 卡片 UI，但不进同看池（勿在查天气后软邀「一起看」）
        if result.get("delegate") or result.get("source") == "web_delegate":
            return now_placeholder
        found = result.get("found") or {}
        entries = found.get("entries") if isinstance(found, dict) else None
        if isinstance(entries, list):
            for e in entries:
                if not isinstance(e, dict):
                    continue
                url = str(e.get("url") or "").strip()
                if not url.startswith("http"):
                    continue
                now_placeholder.append(
                    {
                        "target_type": "url",
                        "target": url,
                        "title": str(e.get("title") or "")[:80],
                        "source": "explore",
                    }
                )

    if rtype in ("open_result",) or result.get("intent") in (
        "open",
        "open_and_look",
    ):
        # open 成功后的目标
        if result.get("outcome") == OUTCOME_SUCCESS:
            target = str(
                result.get("opened_target")
                or result.get("target_path")
                or result.get("target")
                or ""
            ).strip()
            if target.startswith("http"):
                now_placeholder.append(
                    {
                        "target_type": "url",
                        "target": target,
                        "title": target[:60],
                        "source": "open",
                    }
                )
            elif target and result.get("target_type") == "app":
                now_placeholder.append(
                    {
                        "target_type": "app",
                        "target": target,
                        "title": str(result.get("allow_alias") or target)[:40],
                        "source": "open",
                    }
                )

    if rtype == "creation_card":
        body = str(result.get("body") or result.get("summary") or "")
        for m in _URL_RE.finditer(body):
            url = m.group(0).rstrip("，。、；;)）]")
            now_placeholder.append(
                {
                    "target_type": "url",
                    "target": url,
                    "title": str(result.get("title") or "")[:80],
                    "source": "share",
                }
            )

    return now_placeholder


def pool_has_openable(pool: list[dict[str, Any]]) -> bool:
    return any(_entry_fresh(e) and e.get("target") for e in pool)


class TogetherAction:
    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    async def execute(
        self,
        req: TogetherRequest,
        *,
        relationship_stage: str,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        if not can_together(relationship_stage):
            return await self._fail(
                "我们再熟一点，再一起看外面的东西吧。",
                f"关系不够：{relationship_stage}",
                season=season,
                now=now,
            )

        if not req.target:
            return {
                "type": "together_need_target",
                "kind": "together",
                "summary": "no target",
                "qi_line": "想一起看哪个？见闻里有的话指一下，或把链接发我。",
                "speak": True,
                "outcome": OUTCOME_SUCCESS,
                "need_target": True,
            }

        if req.target_type == "url":
            parsed = urlparse(req.target)
            if parsed.scheme.lower() not in ("http", "https"):
                return await self._fail(
                    "这种链接我不太敢一起点开。",
                    f"非法协议：{req.target}",
                    season=season,
                    now=now,
                )

        label = req.title or req.target
        try:
            if req.target_type == "url":
                await asyncio.to_thread(webbrowser.open, req.target, 2)
            else:
                # 应用：交给 open 白名单路径较稳；此处仅尝试 start
                import os
                import sys

                if sys.platform == "win32":
                    await asyncio.to_thread(os.startfile, req.target)  # type: ignore[attr-defined]
                else:
                    await asyncio.to_thread(webbrowser.open, req.target)
        except Exception as e:
            return await self._fail(
                "没打开成，我们换一个？",
                f"together 打开失败：{e}",
                season=season,
                now=now,
            )

        await self.db.insert_action(
            "together",
            f"together:{req.target}",
            target=req.target,
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {
                    "title": req.title,
                    "source": req.source,
                    "target_type": req.target_type,
                },
                ensure_ascii=False,
            ),
        )
        return {
            "type": "together_result",
            "summary": f"together {req.target}",
            "qi_line": "好，我们一起看。",
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "target": req.target,
            "opened_target": req.target,
            "target_type": req.target_type,
        }

    async def _fail(
        self,
        qi_line: str,
        detail: str,
        *,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        logger.info("together fail: %s", detail)
        try:
            await self.db.insert_action(
                "together",
                detail[:200],
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )
        except Exception:
            pass
        return {
            "type": "together_result",
            "summary": detail,
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_FAILED_CAPABILITY,
        }
