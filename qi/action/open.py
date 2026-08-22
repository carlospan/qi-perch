"""L7 open——确认后打开 URL / 白名单应用；可对话授权写入白名单。"""

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

from qi.action.judgment import OUTCOME_RECAP
from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_allow_app,
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

# 不像应用名的对话碎片（防「我还不睡，你现在」当别名）
_ALIAS_REJECT = re.compile(
    r"(还不|现在|睡觉|不睡|谢谢|对的|哈哈|怎么|什么|吗|呢|吧|啊|"
    r"你先|我先|明天|今天|陪你|记着|继续|复盘|代码|对话)",
)

# 打开动词（长匹配优先，避免「打开一下」吃成「一下…」）
_OPEN_VERB = re.compile(r"(?:打开一下|开一下|帮我打开|帮我开|打开|启动)\s*")


def _strip_alias_noise(alias: str) -> str:
    a = (alias or "").strip().strip("「」『』\"'的了吗呢吧啊呀")
    a = re.sub(r"^(一下)+", "", a)
    return a.strip()


def is_plausible_app_alias(alias: str | None) -> bool:
    """应用别名须短、像名字，不能是整句闲聊。"""
    a = _strip_alias_noise(alias or "")
    if not a or len(a) < 2 or len(a) > 16:
        return False
    if re.search(r"[，。、？?！!\s]", a):
        return False
    if _ALIAS_REJECT.search(a):
        return False
    # 拒代词开头的短句感
    if re.match(r"^(我|你|他|她|它|这|那)", a) and len(a) > 6:
        return False
    return True


def normalize_open_intent(intent: str | None) -> str | None:
    """open | open_and_look | allow；旧名 teach → allow。"""
    raw = (intent or "").strip()
    if raw == "teach":
        return "allow"
    if raw in ("open", "open_and_look", "allow"):
        return raw
    return None


@dataclass
class OpenRequest:
    """对话拍解析出的打开 / 授权白名单请求。"""

    intent: str  # open | open_and_look | allow
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
    if re.search(
        r"(打开|开一下|帮我开|启动|以后.*开|你可以帮我开|加入白名单|"
        r"教会你开|教你开)",
        text,
    ):
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

    # 授权进白名单（懂意思：用户说「教会」也认，意图名是 allow）
    allow_m = re.search(
        r"(以后|下次)?(.{0,12}?)(你可以帮我开|你帮我开|能帮我开|记住.*开|"
        r"教会你开|教你开)",
        text,
    )
    if allow_m or re.search(r"加入白名单|你可以开|以后.*帮我开", text):
        alias = _guess_app_alias(text)
        if alias:
            return OpenRequest(intent="allow", target_type="app", target=alias)
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
    m = _OPEN_VERB.search(text)
    if m:
        rest = text[m.end() :]
        m2 = re.match(r"([A-Za-z0-9\u4e00-\u9fff]{2,16})", rest)
        if m2:
            cand = _strip_alias_noise(m2.group(1))
            if is_plausible_app_alias(cand):
                return cand
    # 去掉常见动词壳后再取短片段
    t2 = re.sub(
        r"(帮我|请|以后|下次|你可以|能|把|将|一下|开一下|打开一下|打开|启动|"
        r"教会|教你|记住|白名单)",
        " ",
        t,
    )
    t2 = re.sub(r"[？?！!。.…\s]+", " ", t2).strip()
    parts = [p for p in t2.split() if 2 <= len(p) <= 16]
    parts.sort(key=len, reverse=True)
    for p in parts:
        cand = _strip_alias_noise(p)
        if is_plausible_app_alias(cand):
            return cand
    return None


async def _llm_intent(llm: Any, text: str) -> OpenRequest | None:
    prompt = (
        "判断用户意图，只输出一行 JSON，不要其它字：\n"
        '{"intent":"open"|"open_and_look"|"allow"|"neither","target_type":"url"|"app"|null,'
        '"target":"url或应用名或null"}\n'
        "规则：\n"
        "- open：只要打开链接或应用，不要求看内容\n"
        "- open_and_look：想打开并看看链接/页面上是什么\n"
        "- allow：以后允许帮开某应用（授权进名单；不是上课/施教）\n"
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
    intent = normalize_open_intent(str(data.get("intent") or "neither"))
    if intent is None:
        return None
    target = (data.get("target") or "").strip() or None
    if target:
        target = _strip_alias_noise(target) or target
    url = extract_http_url(text) or (
        extract_http_url(target) if target else None
    )
    if intent in ("open", "open_and_look"):
        if url:
            return OpenRequest(
                intent=intent, target_type="url", target=url
            )
        alias = target or _guess_app_alias(text)
        if not is_plausible_app_alias(alias):
            return None
        return OpenRequest(
            intent=intent, target_type="app", target=_strip_alias_noise(alias)
        )
    # allow
    alias = target or _guess_app_alias(text)
    if not is_plausible_app_alias(alias):
        return None
    return OpenRequest(
        intent="allow", target_type="app", target=_strip_alias_noise(alias)
    )


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


# 常见口头名 ↔ 安装目录 / 快捷方式名（小表；懂意思用，非口令唯一路径）
_APP_ALIAS_SYNONYMS: dict[str, tuple[str, ...]] = {
    "企微": ("企业微信", "wxwork", "wecom"),
    "企业微信": ("企微", "wxwork", "wecom"),
    "微信": ("wechat", "weixin"),
    "网易云": ("cloudmusic", "netease"),
    "chrome": ("google chrome", "谷歌浏览器"),
    "谷歌浏览器": ("chrome", "google chrome"),
    "edge": ("msedge", "microsoft edge"),
    "vscode": ("code", "visual studio code"),
    "vs code": ("code", "vscode", "visual studio code"),
}

_START_MENU_SCAN_CAP = 2500
_KNOWN_DIR_SCAN_CAP = 400


_NOISE_NAME = re.compile(
    r"(uninstall|uninst|卸载|upgrader|upgrade|update|setup|installer|安装|修复)",
    re.I,
)


def _is_noise_app_name(name: str) -> bool:
    return bool(_NOISE_NAME.search(name or ""))


def _alias_needles(alias: str) -> list[str]:
    a = (alias or "").strip().lower()
    if not a:
        return []
    needles: set[str] = {a}
    for key, syns in _APP_ALIAS_SYNONYMS.items():
        bucket = {key.lower(), *(s.lower() for s in syns)}
        if a in bucket:
            needles |= bucket
    return sorted(needles, key=len, reverse=True)


def _name_matches(name: str, needles: list[str]) -> bool:
    n = (name or "").lower()
    stem = Path(n).stem
    return any(needle in stem or needle in n for needle in needles)


def _match_score(name: str, needles: list[str]) -> int:
    """越大越优先：整段 stem 命中 > 包含。"""
    stem = Path(name or "").stem.lower()
    best = 0
    for needle in needles:
        if stem == needle:
            best = max(best, 100)
        elif stem.startswith(needle) or stem.endswith(needle):
            best = max(best, 80)
        elif needle in stem:
            best = max(best, 60)
    return best


def _start_menu_roots() -> list[Path]:
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA") or ""
    programdata = os.environ.get("PROGRAMDATA") or ""
    if appdata:
        roots.append(
            Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )
    if programdata:
        roots.append(
            Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )
    return roots


def _known_install_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        raw = os.environ.get(key)
        if raw:
            roots.append(Path(raw))
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        roots.append(Path(local) / "Programs")
    # 去重保序
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        k = str(r).lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _resolve_shortcut(lnk: Path) -> Path | None:
    """解析 .lnk 目标；失败则返回 None（调用方可退回用快捷方式本身）。"""
    if sys.platform != "win32":
        return None
    try:
        escaped = str(lnk).replace("'", "''")
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(New-Object -ComObject WScript.Shell).CreateShortcut('{escaped}').TargetPath",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        target = (r.stdout or "").strip().strip('"')
        if target:
            p = Path(target)
            if p.is_file():
                return p
    except Exception:
        logger.debug("解析快捷方式失败：%s", lnk, exc_info=True)
    return None


def find_app_candidates(alias: str, *, limit: int = 3) -> list[dict[str, str]]:
    """找应用候选：路径直给 → where → 开始菜单 .lnk → 常见安装目录浅搜。

    不做全盘 rglob。Windows 先行；其它平台仅 which。
    """
    alias = _strip_alias_noise(alias or "") or (alias or "").strip()
    if not alias:
        return []
    needles = _alias_needles(alias)
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    scored: list[tuple[int, dict[str, str]]] = []

    def _add(path: Path, label: str | None = None, *, score: int = 50) -> None:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        key = resolved.lower()
        if key in seen:
            return
        if not path.is_file():
            return
        seen.add(key)
        item = {
            "alias": alias,
            "path": resolved,
            "label": label or path.name,
        }
        scored.append((score, item))
        found.append(item)

    # 用户直接给了路径
    as_path = Path(alias.strip('"'))
    if as_path.is_file():
        _add(as_path, score=100)
        return [x for _, x in sorted(scored, key=lambda t: -t[0])[:limit]]

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
                    _add(Path(line), score=90)
                    if len(found) >= limit:
                        return [x for _, x in sorted(scored, key=lambda t: -t[0])[:limit]]
        except Exception:
            logger.debug("where 查询失败", exc_info=True)
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
                        _add(Path(line), score=90)
                        if len(found) >= limit:
                            return [
                                x
                                for _, x in sorted(scored, key=lambda t: -t[0])[:limit]
                            ]
            except Exception:
                pass

        # 开始菜单快捷方式（深度有限的 rglob，有扫描上限）
        scanned = 0
        for root in _start_menu_roots():
            if len(found) >= limit * 2:
                break
            if not root.is_dir():
                continue
            try:
                for lnk in root.rglob("*.lnk"):
                    scanned += 1
                    if scanned > _START_MENU_SCAN_CAP:
                        break
                    if not _name_matches(lnk.name, needles):
                        continue
                    if _is_noise_app_name(lnk.name):
                        continue
                    score = _match_score(lnk.name, needles)
                    target = _resolve_shortcut(lnk)
                    if target is not None:
                        if _is_noise_app_name(target.name):
                            continue
                        _add(
                            target,
                            label=f"{lnk.stem}（{target.name}）",
                            score=score + 10,
                        )
                    else:
                        # 快捷方式本身也能 startfile
                        _add(lnk, label=lnk.stem, score=score)
                    if len(found) >= limit * 2:
                        break
            except Exception:
                logger.debug("开始菜单扫描失败：%s", root, exc_info=True)

        # 常见安装目录：只扫名称像别名的子目录，再浅取 exe（最多两层）
        scanned = 0
        for root in _known_install_roots():
            if len(found) >= limit * 2:
                break
            if not root.is_dir():
                continue
            try:
                for child in root.iterdir():
                    scanned += 1
                    if scanned > _KNOWN_DIR_SCAN_CAP:
                        break
                    if not child.is_dir() or not _name_matches(child.name, needles):
                        continue
                    score = _match_score(child.name, needles)
                    exes: list[Path] = []
                    try:
                        exes.extend(
                            p
                            for p in child.glob("*.exe")
                            if p.is_file() and not _is_noise_app_name(p.name)
                        )
                        for sub in child.iterdir():
                            if not sub.is_dir():
                                continue
                            if _is_noise_app_name(sub.name):
                                continue
                            exes.extend(
                                p
                                for p in sub.glob("*.exe")
                                if p.is_file() and not _is_noise_app_name(p.name)
                            )
                    except Exception:
                        continue
                    # 优先文件名也像别名的 exe
                    exes.sort(
                        key=lambda p: (-_match_score(p.name, needles), len(p.name))
                    )
                    for exe in exes[:2]:
                        _add(
                            exe,
                            label=f"{child.name}/{exe.name}",
                            score=score + _match_score(exe.name, needles) // 5,
                        )
            except Exception:
                logger.debug("安装目录扫描失败：%s", root, exc_info=True)
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
                _add(Path(line[0]), score=90)
        except Exception:
            pass

    scored.sort(key=lambda t: -t[0])
    return [item for _, item in scored[:limit]]


class OpenAction:
    """响应式打开：确认后开 URL / 白名单应用；allow 写入白名单。"""

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

    def _detail_json(self, data: dict) -> str:
        motive = getattr(self, "_trace_motive", None)
        if motive:
            data = {**data, "motive": motive}
        return json.dumps(data, ensure_ascii=False)

    async def execute(
        self,
        req: OpenRequest,
        *,
        relationship_stage: str,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
        selected_index: int | None = None,
        motive: dict | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        self._trace_motive = motive
        if selected_index is not None:
            req.selected_index = selected_index
        if req.target_type == "app":
            req.target = _strip_alias_noise(req.target) or req.target
        norm = normalize_open_intent(req.intent)
        if norm:
            req.intent = norm

        if not can_open(relationship_stage):
            return await self._fail(
                "我们再熟一点，我再帮你开这类东西。",
                f"关系不够：{relationship_stage}",
                season=season,
                now=now,
            )

        if req.intent in ("allow", "teach"):
            req.intent = "allow"
            return await self._execute_allow(
                req,
                confirmed=confirmed,
                season=season,
                now=now,
                relationship_stage=relationship_stage,
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

    async def _execute_allow(
        self,
        req: OpenRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
        relationship_stage: str = "stranger",
        scars: list[dict] | None = None,
    ) -> dict[str, Any]:
        if not can_allow_app(relationship_stage, scars):
            return await self._fail(
                "记应用白名单这事，我们得再熟一点再说。",
                f"allow 关系不够：{relationship_stage}",
                season=season,
                now=now,
            )
        if not req.candidates:
            req.candidates = find_app_candidates(req.target, limit=3)
        if not req.candidates:
            return await self._fail(
                f"我还找不到「{req.target}」在哪，你换个名字，或以后告诉我路径。",
                f"allow 无候选：{req.target}",
                season=season,
                now=now,
            )
        if not confirmed:
            return self._recap_gate_allow(req)

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
        # 方案 A：只记不写开；口吻要说清「没开」，并问要不要现在开（brain 挂 open pending）
        msg = f"记下了「{req.target}」。这次我没开，现在开吗？"
        await self.db.insert_action(
            "open",
            f"allow:{req.target}",
            target=chosen["path"],
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=self._detail_json(
                {"intent": "allow", "alias": req.target},
            ),
        )
        return {
            "type": "open_result",
            "summary": f"白名单已记：{req.target}",
            "qi_line": msg,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "allow",
            "offer_open_now": True,
            "allow_alias": req.target,
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
        qi_line = "好，我打开看看。"
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
            detail_json=self._detail_json(
                {"intent": req.intent, "target_type": "url"},
            ),
        )
        return {
            "type": "open_result",
            "summary": f"opened {url}",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": req.intent,
            "opened_target": url,
            "target_type": "url",
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
            if not is_plausible_app_alias(req.target):
                return await self._fail(
                    "这个名字不太像应用，换个短称呼再说？",
                    f"别名不像应用：{req.target}",
                    season=season,
                    now=now,
                )
            # 不在白名单：口头复述后走 allow（判断制已接活意图）
            req.candidates = find_app_candidates(req.target, limit=3)
            if not req.candidates:
                return await self._fail(
                    f"我还找不到「{req.target}」在哪。",
                    f"无候选：{req.target}",
                    season=season,
                    now=now,
                )
            return self._recap_gate_allow(
                OpenRequest(
                    intent="allow",
                    target_type="app",
                    target=req.target,
                    candidates=req.candidates,
                )
            )
        path = entry["path"]

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
        qi_line = "好，我打开看看。"
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
            detail_json=self._detail_json(
                {"intent": req.intent, "alias": req.target},
            ),
        )
        return {
            "type": "open_result",
            "summary": f"opened app {req.target}",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": req.intent,
            "opened_target": path,
            "target_type": "app",
            "allow_alias": req.target,
        }

    def _recap_gate_allow(self, req: OpenRequest) -> dict[str, Any]:
        lines = []
        for i, c in enumerate(req.candidates[:3], start=1):
            lines.append(f"{i}. {c.get('label') or c['path']}")
        body = "\n".join(lines)
        msg = (
            f"你是说以后可以帮你开「{req.target}」吗？我找到这些，"
            f"回 1/{len(req.candidates[:3])} 或说「对」：\n{body}"
        )
        display = req.candidates[0]["path"]
        return {
            "type": "open_recap",
            "kind": "open",
            "intent": "allow",
            "target_path": display,
            "summary": msg,
            "qi_line": msg,
            "speak": True,
            "outcome": OUTCOME_RECAP,
            "candidates": req.candidates[:3],
            "allow_alias": req.target,
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
