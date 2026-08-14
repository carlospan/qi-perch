"""L7 open——确认后打开 URL / 白名单应用；可对话教会写入白名单。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_open,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.open")

WHITELIST_KEY = "open_app_whitelist"
DEBOUNCE_KEY = "open_debounce"
DEBOUNCE_SECONDS = 8.0
LOOK_AFTER_OPEN_DELAY_SEC = 1.2


def look_after_delay(config: dict | None) -> float:
    return float(_open_cfg(config).get("look_after_delay_seconds", LOOK_AFTER_OPEN_DELAY_SEC))

_URL_RE = re.compile(r"https?://[^\s'\"<>，。、）\]]+", re.I)

_OPEN_NEG = re.compile(
    r"(帮我看(看|一下|下)?.{0,12}(文件|代码|\.txt|\.py|\.md)|"
    r"[A-Za-z]:[\\/].+\.(txt|md|py|json|csv|log))",
    re.I,
)


@dataclass
class OpenRequest:
    """对话拍解析出的打开 / 教会请求。"""

    intent: str  # open | open_and_look | teach
    target_type: str  # url | app
    target: str  # url 或应用别名
    launch_path: str | None = None
    candidates: list[dict[str, str]] = field(default_factory=list)
    selected_index: int = 0


def _open_cfg(config: dict | None) -> dict:
    raw = ((config or {}).get("action") or {}).get("open") or {}
    return raw if isinstance(raw, dict) else {}


def debounce_seconds(config: dict | None) -> float:
    return float(_open_cfg(config).get("debounce_seconds", DEBOUNCE_SECONDS))


def extract_http_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    if not m:
        return None
    url = m.group(0)
    while url and url[-1] in ")。,.，。]":
        url = url[:-1]
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    return url


def _heuristic_gate(text: str) -> bool:
    """值不值得问模型 / 强短路。"""
    if not text or len(text) > 120:
        return False
    if _OPEN_NEG.search(text):
        return False
    if extract_http_url(text):
        return True
    if re.search(r"(打开|开一下|帮我开|启动|教会|以后.*开|你可以帮我开)", text):
        return True
    if re.search(r"看看.{0,6}(链接|网址|这个网|网页)", text):
        return True
    return False


def _strong_intent(text: str) -> OpenRequest | None:
    """强信号短路，不调 LLM。"""
    if _OPEN_NEG.search(text):
        return None
    url = extract_http_url(text)
    if url:
        # 「看看/瞧瞧…链接」→ open_and_look；纯打开 → open
        if re.search(r"(看(看|一眼|瞧)|瞧瞧).{0,12}(链接|网址|网页|这个)|链接.{0,6}看", text):
            return OpenRequest(intent="open_and_look", target_type="url", target=url)
        if re.search(r"(打开|开一下|帮我开|启动)", text) or text.strip() == url:
            return OpenRequest(intent="open", target_type="url", target=url)
        if re.search(r"看看|瞧瞧", text) and re.search(r"链接|网址|http", text, re.I):
            return OpenRequest(intent="open_and_look", target_type="url", target=url)
        return None

    # 教会
    teach_m = re.search(
        r"(以后|下次)?(.{0,12}?)(你可以帮我开|你帮我开|能帮我开|教会你开|记住.*开)",
        text,
    )
    if teach_m or re.search(r"教会|教你开|加入白名单|你可以开", text):
        alias = _guess_app_alias(text)
        if alias:
            return OpenRequest(intent="teach", target_type="app", target=alias)
        return None

    # 打开应用（无 URL）
    if re.search(r"(打开|开一下|帮我开|启动)", text):
        alias = _guess_app_alias(text)
        if alias:
            return OpenRequest(intent="open", target_type="app", target=alias)
    return None


def _guess_app_alias(text: str) -> str | None:
    """从句子里抠应用称呼（粗）；白名单匹配不区分大小写。"""
    t = text.strip()
    # 去掉常见动词壳
    t2 = re.sub(
        r"(帮我|请|以后|下次|你可以|能|把|将|一下|开一下|打开|启动|教会|教你|记住|白名单)",
        " ",
        t,
    )
    t2 = re.sub(r"[？?！!。.…\s]+", " ", t2).strip()
    parts = [p for p in t2.split() if len(p) >= 2]
    if not parts:
        # 中文无空格：取「开」后片段
        m = re.search(r"(?:打开|开一下|帮我开|启动|开)\s*([^\s，。、]{2,16})", text)
        if m:
            return m.group(1).strip("的了吗呢")
        return None
    # 取最长非虚词片段
    parts.sort(key=len, reverse=True)
    return parts[0][:32]


async def _llm_intent(llm: Any, text: str) -> OpenRequest | None:
    prompt = (
        "判断用户意图，只输出一行 JSON，不要其它字：\n"
        '{"intent":"open"|"open_and_look"|"teach"|"neither","target_type":"url"|"app"|null,'
        '"target":"url或应用名或null"}\n'
        "规则：\n"
        "- open：只要打开链接或应用，不要求看内容\n"
        "- open_and_look：想打开并看看链接/页面上是什么\n"
        "- teach：以后允许打开某应用（教会/记住你可以开）\n"
        "- neither：读文件、看屏幕在做什么、闲聊、无关\n"
        f"用户：「{text}」"
    )
    try:
        raw = (
            await llm.call(
                "fact", [{"role": "user", "content": prompt}], temperature=0.0
            )
            or ""
        ).strip()
    except Exception:
        logger.debug("open intent LLM 失败", exc_info=True)
        return None
    # 抽 JSON
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end < 0:
            return None
        data = json.loads(raw[start : end + 1])
    except Exception:
        return None
    intent = str(data.get("intent") or "neither").strip()
    if intent not in ("open", "open_and_look", "teach"):
        return None
    target = (data.get("target") or "").strip() or None
    url = extract_http_url(text) or (
        extract_http_url(target) if target else None
    )
    if intent in ("open", "open_and_look"):
        if url:
            return OpenRequest(
                intent=intent, target_type="url", target=url
            )
        alias = target or _guess_app_alias(text)
        if not alias:
            return None
        return OpenRequest(intent=intent, target_type="app", target=alias)
    # teach
    alias = target or _guess_app_alias(text)
    if not alias:
        return None
    return OpenRequest(intent="teach", target_type="app", target=alias)


async def detect_open_intent(
    message: str | None, *, llm: Any | None = None
) -> OpenRequest | None:
    """懂意思：强启发式短路 + 弱候选 LLM。"""
    text = (message or "").strip()
    if not text or not _heuristic_gate(text):
        return None
    strong = _strong_intent(text)
    if strong is not None:
        return strong
    if llm is None:
        return None
    return await _llm_intent(llm, text)


def looks_like_open_intent(message: str | None) -> bool:
    """同步：仅强信号（测试用）。"""
    text = (message or "").strip()
    if not text or not _heuristic_gate(text):
        return False
    return _strong_intent(text) is not None


# ---------------------------------------------------------------------------
# 白名单
# ---------------------------------------------------------------------------


async def load_whitelist(db: Database) -> list[dict[str, str]]:
    raw = await db.get_body_memory(WHITELIST_KEY)
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict) and x.get("alias") and x.get("path")]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if isinstance(data, list):
            return [
                x
                for x in data
                if isinstance(x, dict) and x.get("alias") and x.get("path")
            ]
    return []


async def save_whitelist(db: Database, entries: list[dict[str, str]]) -> None:
    await db.set_body_memory(WHITELIST_KEY, entries)


def find_whitelist_entry(
    entries: list[dict[str, str]], alias: str
) -> dict[str, str] | None:
    key = alias.strip().lower()
    for e in entries:
        if str(e.get("alias", "")).strip().lower() == key:
            return e
        # 别名互相包含
        a = str(e.get("alias", "")).strip().lower()
        if key in a or a in key:
            return e
    return None


def find_app_candidates(alias: str, *, limit: int = 3) -> list[dict[str, str]]:
    """Windows：where + 若像路径则直接用；不做全盘 rglob（太慢）。"""
    alias = (alias or "").strip()
    if not alias:
        return []
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(path: Path, label: str | None = None) -> None:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        if resolved.lower() in seen:
            return
        if not path.is_file():
            return
        seen.add(resolved.lower())
        found.append(
            {
                "alias": alias,
                "path": resolved,
                "label": label or path.name,
            }
        )

    # 用户直接给了路径
    as_path = Path(alias.strip('"'))
    if as_path.is_file():
        _add(as_path)
        return found[:limit]

    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["where", alias],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            for line in (r.stdout or "").splitlines():
                line = line.strip()
                if line and line.lower().endswith((".exe", ".bat", ".cmd")):
                    _add(Path(line))
                    if len(found) >= limit:
                        return found[:limit]
        except Exception:
            logger.debug("where 查询失败", exc_info=True)
        # 再试 alias.exe
        if not found and not alias.lower().endswith(".exe"):
            try:
                r = subprocess.run(
                    ["where", f"{alias}.exe"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    if line:
                        _add(Path(line))
                        if len(found) >= limit:
                            return found[:limit]
            except Exception:
                pass
    else:
        try:
            r = subprocess.run(
                ["which", alias],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            line = (r.stdout or "").strip().splitlines()
            if line:
                _add(Path(line[0]))
        except Exception:
            pass

    return found[:limit]


class OpenAction:
    """响应式打开：确认后开 URL / 白名单应用；teach 写入白名单。"""

    def __init__(
        self,
        db: Database,
        *,
        llm: LLMGateway | None = None,
        config: dict | None = None,
        look: Any | None = None,
    ) -> None:
        self.db = db
        self.llm = llm
        self.config = config or {}
        self.look = look

    async def execute(
        self,
        req: OpenRequest,
        *,
        relationship_stage: str,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
        selected_index: int | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        if selected_index is not None:
            req.selected_index = selected_index

        if not can_open(relationship_stage):
            return await self._fail(
                "我们再熟一点，我再帮你开这类东西。",
                f"关系不够：{relationship_stage}",
                season=season,
                now=now,
            )

        if req.intent == "teach":
            return await self._execute_teach(
                req, confirmed=confirmed, season=season, now=now
            )

        if req.target_type == "url":
            return await self._execute_url(
                req,
                confirmed=confirmed,
                season=season,
                now=now,
                relationship_stage=relationship_stage,
            )
        return await self._execute_app(
            req,
            confirmed=confirmed,
            season=season,
            now=now,
            relationship_stage=relationship_stage,
        )

    async def _execute_teach(
        self,
        req: OpenRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        if not req.candidates:
            req.candidates = find_app_candidates(req.target, limit=3)
        if not req.candidates:
            return await self._fail(
                f"我还找不到「{req.target}」在哪，你换个名字，或以后告诉我路径。",
                f"teach 无候选：{req.target}",
                season=season,
                now=now,
            )
        if not confirmed:
            return self._confirm_gate_teach(req)

        idx = max(0, min(req.selected_index, len(req.candidates) - 1))
        chosen = req.candidates[idx]
        entries = await load_whitelist(self.db)
        # 同 alias 覆盖
        entries = [
            e
            for e in entries
            if str(e.get("alias", "")).lower() != req.target.lower()
        ]
        entries.append(
            {
                "alias": req.target,
                "path": chosen["path"],
                "label": chosen.get("label") or chosen["path"],
            }
        )
        await save_whitelist(self.db, entries)
        msg = f"好，以后「{req.target}」我可以帮你开——开前还是会问你。"
        await self.db.insert_action(
            "open",
            f"teach:{req.target}",
            target=chosen["path"],
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"intent": "teach", "alias": req.target}, ensure_ascii=False
            ),
        )
        return {
            "type": "open_result",
            "summary": f"已教会：{req.target}",
            "qi_line": msg,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "teach",
        }

    async def _execute_url(
        self,
        req: OpenRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
        relationship_stage: str,
    ) -> dict[str, Any]:
        url = req.target
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return await self._fail(
                "这种链接我不敢随便开。",
                f"非法协议：{url}",
                season=season,
                now=now,
            )
        if not confirmed:
            look_hint = (
                "开完我瞥一眼告诉你。"
                if req.intent == "open_and_look"
                else ""
            )
            msg = f"要我打开这个链接吗？{look_hint}".strip()
            return {
                "type": "assist_confirm_request",
                "kind": "open",
                "target_path": url,
                "summary": msg,
                "qi_line": msg,
                "speak": True,
                "outcome": "confirm_required",
                "needs_confirmation": True,
                "confirm_mark": "开？",
                "confirm_label": "开吧",
            }

        if await self._debounced(url, now):
            return {
                "type": "open_result",
                "summary": "debounce",
                "qi_line": "刚开过这个了。",
                "speak": True,
                "outcome": OUTCOME_SUCCESS,
            }

        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            logger.debug("webbrowser.open 失败", exc_info=True)
            return await self._fail(
                "链接没打开成。",
                f"open url 失败：{e}",
                season=season,
                now=now,
            )

        await self._mark_debounce(url, now)
        qi_line = "开了，你看看对不对。"
        if req.intent == "open_and_look":
            glance_line = await self._glance_after_open(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
            )
            if glance_line:
                qi_line = glance_line

        await self.db.insert_action(
            "open",
            f"url:{url[:120]}",
            target=url,
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"intent": req.intent, "target_type": "url"}, ensure_ascii=False
            ),
        )
        return {
            "type": "open_result",
            "summary": f"opened {url}",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": req.intent,
        }

    async def _execute_app(
        self,
        req: OpenRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
        relationship_stage: str,
    ) -> dict[str, Any]:
        entries = await load_whitelist(self.db)
        entry = find_whitelist_entry(entries, req.target)
        if entry is None:
            return await self._fail(
                f"「{req.target}」我还不会开——你要是愿意，可以教我一声。",
                f"不在白名单：{req.target}",
                season=season,
                now=now,
            )
        path = entry["path"]
        if not confirmed:
            msg = f"要我打开「{req.target}」吗？"
            return {
                "type": "assist_confirm_request",
                "kind": "open",
                "target_path": path,
                "summary": msg,
                "qi_line": msg,
                "speak": True,
                "outcome": "confirm_required",
                "needs_confirmation": True,
                "confirm_mark": "开？",
                "confirm_label": "开吧",
            }

        if await self._debounced(path, now):
            return {
                "type": "open_result",
                "summary": "debounce",
                "qi_line": "刚开过这个了。",
                "speak": True,
                "outcome": OUTCOME_SUCCESS,
            }

        try:
            self._launch_path(path)
        except Exception as e:
            logger.debug("launch 失败", exc_info=True)
            return await self._fail(
                "没打开成。",
                f"launch 失败：{e}",
                season=season,
                now=now,
            )

        await self._mark_debounce(path, now)
        qi_line = "开了，你看看对不对。"
        if req.intent == "open_and_look":
            glance_line = await self._glance_after_open(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
            )
            if glance_line:
                qi_line = glance_line

        await self.db.insert_action(
            "open",
            f"app:{req.target}",
            target=path,
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"intent": req.intent, "alias": req.target}, ensure_ascii=False
            ),
        )
        return {
            "type": "open_result",
            "summary": f"opened app {req.target}",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": req.intent,
        }

    def _confirm_gate_teach(self, req: OpenRequest) -> dict[str, Any]:
        lines = []
        for i, c in enumerate(req.candidates[:3], start=1):
            lines.append(f"{i}. {c.get('label') or c['path']}")
        body = "\n".join(lines)
        msg = (
            f"以后都可以帮你开「{req.target}」吗？我找到这些，回 1/{len(req.candidates)} 或说开吧（默认 1）：\n{body}"
        )
        display = req.candidates[0]["path"]
        return {
            "type": "assist_confirm_request",
            "kind": "open",
            "target_path": display,
            "summary": msg,
            "qi_line": msg,
            "speak": True,
            "outcome": "confirm_required",
            "needs_confirmation": True,
            "confirm_mark": "记？",
            "confirm_label": "好",
            "candidates": req.candidates[:3],
        }

    async def _glance_after_open(
        self,
        *,
        relationship_stage: str,
        season: str,
        now: datetime,
    ) -> str | None:
        if self.look is None:
            return None
        try:
            await asyncio.sleep(look_after_delay(self.config))
            result = await self.look.glance(
                relationship_stage=relationship_stage,
                season=season,
                now=datetime.now(),
                reactive=True,
                user_question="刚才帮你打开的页面/窗口",
                mode="ambient",
            )
            if result and result.get("outcome") == OUTCOME_SUCCESS:
                line = (result.get("qi_line") or "").strip()
                return line or None
        except Exception:
            logger.debug("open_and_look glance 失败", exc_info=True)
        return None

    def _launch_path(self, path: str) -> None:
        p = Path(path)
        if sys.platform == "win32":
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            subprocess.Popen([str(p)], start_new_session=True)

    async def _debounced(self, target: str, now: datetime) -> bool:
        raw = await self.db.get_body_memory(DEBOUNCE_KEY)
        if not isinstance(raw, dict):
            return False
        if str(raw.get("target")) != target:
            return False
        try:
            at = datetime.fromisoformat(str(raw.get("at")))
        except Exception:
            return False
        return (now - at).total_seconds() < debounce_seconds(self.config)

    async def _mark_debounce(self, target: str, now: datetime) -> None:
        await self.db.set_body_memory(
            DEBOUNCE_KEY,
            {"target": target, "at": now.isoformat(timespec="seconds")},
        )

    async def _fail(
        self,
        qi_line: str,
        summary: str,
        *,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        await self.db.insert_action(
            "open",
            summary,
            target="user",
            outcome=OUTCOME_FAILED_CAPABILITY,
            season=season,
            now=now,
        )
        return {
            "type": "open_result",
            "summary": summary,
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_FAILED_CAPABILITY,
        }
