"""L7 disk——确认后列 D: 下一层目录，或打开 D: 下本地文件。

契约：懂意思，不靠口令——白话能力问 / 弱说法须能进路径，再多轮引导。
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_disk,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.disk")

# 允许根：仅 D:\（测试可 monkeypatch DEFAULT_ALLOWED_ROOT）
DEFAULT_ALLOWED_ROOT = Path("D:/")
LIST_CAP = 40
DEBOUNCE_KEY = "disk_open_debounce"
LIST_DEBOUNCE_KEY = "disk_list_debounce"
DEBOUNCE_SECONDS = 8.0
LISTING_STICKY_MINUTES = 5.0

# 拒 https:// 等（scheme 的 ://）；只认盘符路径
_WIN_PATH_RE = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[\\/](?!/)[^\s'\"<>|]*",
    re.UNICODE,
)
_D_DRIVE_MENTION = re.compile(
    r"(?:[Dd]\s*盘|[Dd]:\\?|(?:^|[^\w])[Dd]:(?:\\|$))", re.I
)
_LIST_CUES = re.compile(
    r"(列(一下|出|目录)|看看?.{0,8}(有什么|有哪些|有啥|里面)|目录|文件夹里|有哪些文件|"
    r"里面有什么|有什么文件|有啥)",
    re.I,
)
_OPEN_FILE_CUES = re.compile(
    r"(打开|开一下|帮我开|启动).{0,40}"
    r"((?<![A-Za-z])[A-Za-z]:[\\/](?!/)[^\s'\"<>|]*|"
    r"(?<!://)[^\s:\\/]+\.[A-Za-z0-9]{1,8}\b)",
    re.I,
)
_CAPABILITY_ASK = re.compile(
    r"(能|可以|会).{0,12}(看(到|见)?|浏览|列).{0,16}([Dd]\s*盘|[Dd]:)|"
    r"([Dd]\s*盘|[Dd]:).{0,12}(能|可以).{0,8}(看|列)|"
    r"(看(得)?到|看得见).{0,8}([Dd]\s*盘|[Dd]:).{0,8}(文件|目录|东西)?|"
    r"([Dd]\s*盘|[Dd]:).{0,8}(下的)?(文件|目录).{0,8}(吗|么|？|\?)",
    re.I,
)


@dataclass
class DiskRequest:
    intent: str  # list_dir | open_file | offer_list
    path: str
    listed_entries: list[dict[str, Any]] = field(default_factory=list)


def allowed_root() -> Path:
    return Path(DEFAULT_ALLOWED_ROOT)


def normalize_under_root(raw: str, *, root: Path | None = None) -> Path | None:
    root = (root or allowed_root()).resolve()
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    if re.fullmatch(r"[Dd]\s*盘", text):
        return root
    try:
        p = Path(text).expanduser()
        if not p.is_absolute():
            p = root / p
        resolved = p.resolve()
    except Exception:
        return None
    try:
        resolved.relative_to(root)
    except ValueError:
        if resolved != root:
            return None
    return resolved


def extract_win_path(text: str) -> str | None:
    m = _WIN_PATH_RE.search(text or "")
    if not m:
        m2 = re.search(r"\b([Dd]):\\?\b", text or "")
        if m2:
            return f"{m2.group(1).upper()}:\\"
        if re.search(r"[Dd]\s*盘", text or ""):
            return str(allowed_root())
        return None
    return m.group(0).rstrip("，。、；;）)】]")


def mentions_d_drive(text: str) -> bool:
    return bool(_D_DRIVE_MENTION.search(text or ""))


def looks_like_disk_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _CAPABILITY_ASK.search(t) and mentions_d_drive(t):
        return True
    path = extract_win_path(t)
    if not path:
        if mentions_d_drive(t) and (
            _LIST_CUES.search(t)
            or re.search(r"(打开|开一下|帮我开)", t)
            or re.search(r"(看下|看看|瞧瞧).{0,8}(有啥|有什么|有哪些)", t)
        ):
            return True
        return False
    if _LIST_CUES.search(t) or _OPEN_FILE_CUES.search(t):
        return True
    if re.search(r"(打开|开一下|帮我开)", t, re.I) and re.search(
        r"\.[A-Za-z0-9]{1,8}\b", path
    ):
        return True
    if re.search(r"(列|目录|有什么|有哪些)", t) and mentions_d_drive(t):
        return True
    return False


def _weak_disk_candidate(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 160:
        return False
    if mentions_d_drive(t):
        return True
    p = extract_win_path(t)
    if p and re.match(r"^[Dd]:", p, re.I):
        return True
    return False


async def detect_disk_intent(
    text: str, *, llm: LLMGateway | None = None
) -> DiskRequest | None:
    """懂意思：强启发短路 + 弱候选 LLM；禁止只认固定口令。"""
    t = (text or "").strip()
    if not t:
        return None

    if _CAPABILITY_ASK.search(t) and mentions_d_drive(t):
        return DiskRequest(intent="offer_list", path=str(allowed_root()))

    if looks_like_disk_intent(t):
        path = extract_win_path(t) or str(allowed_root())
        norm = normalize_under_root(path)
        target = str(norm) if norm is not None else path

        if _LIST_CUES.search(t) or (
            re.search(r"(列|目录|有什么|有哪些)", t)
            and not re.search(r"\.[A-Za-z0-9]{1,8}\b", path)
        ):
            return DiskRequest(intent="list_dir", path=target)

        if _OPEN_FILE_CUES.search(t) or (
            re.search(r"(打开|开一下|帮我开)", t, re.I)
            and re.search(r"\.[A-Za-z0-9]{1,8}\b", path)
        ):
            return DiskRequest(intent="open_file", path=target)

        if llm is not None:
            got = await _llm_disk_intent(t, llm)
            if got is not None:
                return got
        if mentions_d_drive(t):
            return DiskRequest(intent="offer_list", path=str(allowed_root()))
        return None

    if llm is not None and _weak_disk_candidate(t):
        return await _llm_disk_intent(t, llm)
    return None


async def _llm_disk_intent(text: str, llm: LLMGateway) -> DiskRequest | None:
    root = str(allowed_root())
    prompt = (
        "判断用户关于本机 D 盘的意图。只输出一行 JSON，不要其它文字：\n"
        '{"intent":"offer_list"|"list_dir"|"open_file"|"neither","path":"..."}\n'
        "含义：\n"
        "- offer_list：在问能不能看/有没有权限/会不会列 D 盘（尚未点名具体目录去列）\n"
        "- list_dir：要列出某目录内容\n"
        "- open_file：要打开某文件\n"
        "- neither：无关\n"
        f'path：Windows 路径且须在 D: 下；offer_list 可用 "{root}"；'
        "拿不准 path 时用根路径。不确定则 neither。\n"
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
    intent = str(data.get("intent") or "").strip()
    if intent not in ("offer_list", "list_dir", "open_file"):
        return None
    path = str(data.get("path") or "").strip() or root
    return DiskRequest(intent=intent, path=path)


def resolve_listing_followup(
    text: str, listing: dict[str, Any] | None
) -> DiskRequest | None:
    """列目录后的白话指认：打开第 N 个 / 打开某某 / 进某某目录。"""
    if not listing:
        return None
    entries = listing.get("entries") or []
    if not entries:
        return None
    t = (text or "").strip()
    if not t:
        return None

    m = re.search(r"第\s*([0-9一二三四五六七八九十]+)\s*个", t)
    idx = None
    if m:
        idx = _parse_zh_or_int(m.group(1))
    elif re.fullmatch(r"[1-9][0-9]?", t):
        idx = int(t)
    if idx is not None and 1 <= idx <= len(entries):
        e = entries[idx - 1]
        path = str(e.get("path") or "")
        if e.get("is_dir"):
            return DiskRequest(intent="list_dir", path=path)
        return DiskRequest(intent="open_file", path=path)

    m2 = re.search(
        r"(?:打开|开一下|帮我开|进入|进|看)\s*[「『\"]?([^」』\"\s]+)[」』\"]?",
        t,
    )
    name = (m2.group(1) if m2 else "").strip()
    if not name and len(t) <= 40:
        name = re.sub(r"^(打开|开一下|帮我开|进入|进)\s*", "", t).strip()
    if not name:
        return None
    name_l = name.lower()
    for e in entries:
        en = str(e.get("name") or "")
        if en.lower() == name_l or name_l in en.lower() or en.lower() in name_l:
            path = str(e.get("path") or "")
            if e.get("is_dir"):
                return DiskRequest(intent="list_dir", path=path)
            return DiskRequest(intent="open_file", path=path)
    return None


def _parse_zh_or_int(s: str) -> int | None:
    s = (s or "").strip()
    if s.isdigit():
        return int(s)
    table = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    return table.get(s)


class DiskAction:
    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    async def execute(
        self,
        req: DiskRequest,
        *,
        relationship_stage: str,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
        motive: dict | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        self._trace_motive = motive
        if not can_disk(relationship_stage):
            return await self._fail(
                "我们再熟一点，我再帮你看盘上的东西。",
                f"关系不够：{relationship_stage}",
                season=season,
                now=now,
                action_kind="list_dir",
            )

        if req.intent == "offer_list":
            return await self._offer_list(req, season=season, now=now)

        path = normalize_under_root(req.path)
        if path is None:
            return await self._fail(
                "这个路径不在我能碰的 D 盘范围内。",
                f"越界或非法路径：{req.path}",
                season=season,
                now=now,
                action_kind="list_dir"
                if req.intent == "list_dir"
                else "open",
            )

        if req.intent == "list_dir":
            return await self._list_dir(
                path, confirmed=confirmed, season=season, now=now
            )
        if req.intent == "open_file":
            return await self._open_file(
                path, confirmed=confirmed, season=season, now=now
            )
        return await self._fail(
            "我不太确定你要我列目录还是打开文件。",
            f"未知 intent：{req.intent}",
            season=season,
            now=now,
            action_kind="list_dir",
        )

    async def _offer_list(
        self,
        req: DiskRequest,
        *,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        """白话能力问：说明能看 D 盘，直接列根目录一层。"""
        root = normalize_under_root(req.path) or allowed_root().resolve()
        list_req = DiskRequest(intent="list_dir", path=str(root))
        return await self._list_dir(
            root, confirmed=True, season=season, now=now
        )

    async def _list_dir(
        self,
        path: Path,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        if await self._list_debounced(str(path), now):
            qi_line = (
                "刚列过这一层了，上面那些还在。"
                "要说哪个我再帮你开，或者说进哪个文件夹。"
            )
            return {
                "type": "disk_result",
                "summary": "list_debounce",
                "qi_line": qi_line,
                "speak": True,
                "outcome": OUTCOME_SUCCESS,
                "intent": "list_dir",
                "listing_dir": str(path),
            }
        if not path.exists():
            return await self._fail(
                f"「{path}」好像不存在。",
                f"list_dir 不存在：{path}",
                season=season,
                now=now,
                action_kind="list_dir",
            )
        if not path.is_dir():
            return await self._fail(
                f"「{path}」不是文件夹，我没法按目录列。",
                f"list_dir 非目录：{path}",
                season=season,
                now=now,
                action_kind="list_dir",
            )

        try:
            entries = sorted(
                path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError as e:
            return await self._fail(
                "这个目录我进不去。",
                f"list_dir 权限：{e}",
                season=season,
                now=now,
                action_kind="list_dir",
            )
        except Exception as e:
            return await self._fail(
                "列目录时出了点问题。",
                f"list_dir 失败：{e}",
                season=season,
                now=now,
                action_kind="list_dir",
            )

        total = len(entries)
        shown = entries[:LIST_CAP]
        listing: list[dict[str, Any]] = []
        lines: list[str] = []
        for i, p in enumerate(shown, start=1):
            tag = "目录" if p.is_dir() else "文件"
            lines.append(f"{i}. [{tag}] {p.name}")
            listing.append(
                {
                    "name": p.name,
                    "path": str(p.resolve()),
                    "is_dir": p.is_dir(),
                }
            )
        body = "\n".join(lines) if lines else "（空的）"
        extra = ""
        if total > LIST_CAP:
            extra = f"\n……还有 {total - LIST_CAP} 项没列完。"
        qi_line = (
            f"「{path}」这一层我看到这些：\n{body}{extra}\n"
            "想打开哪个，直接说名字或序号就行。"
        )

        await self.db.insert_action(
            "list_dir",
            f"list:{path}",
            target=str(path),
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"count": total, "shown": len(shown), "motive": self._trace_motive or {}},
                ensure_ascii=False,
            ),
        )
        await self._mark_list_debounce(str(path), now)
        return {
            "type": "disk_result",
            "summary": f"listed {path} ({total})",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "list_dir",
            "listing_dir": str(path),
            "listing_entries": listing,
            "listing_sticky": True,
        }

    async def _open_file(
        self,
        path: Path,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        if not path.exists():
            return await self._fail(
                f"「{path}」好像不存在。",
                f"open_file 不存在：{path}",
                season=season,
                now=now,
                action_kind="open",
            )
        if not path.is_file():
            return await self._fail(
                f"「{path}」不是文件。要列目录的话跟我说一声。",
                f"open_file 非文件：{path}",
                season=season,
                now=now,
                action_kind="open",
            )

        if await self._debounced(str(path), now):
            return {
                "type": "disk_result",
                "summary": "debounce",
                "qi_line": "刚开过这个了。",
                "speak": True,
                "outcome": OUTCOME_SUCCESS,
            }

        try:
            self._launch_path(path)
        except Exception as e:
            logger.debug("disk open_file 失败", exc_info=True)
            return await self._fail(
                "没打开成。",
                f"open_file 启动失败：{e}",
                season=season,
                now=now,
                action_kind="open",
            )

        await self._mark_debounce(str(path), now)
        qi_line = "开了——窗口起来可能稍慢，你稍等一下看看。"
        await self.db.insert_action(
            "open",
            f"file:{path.name}",
            target=str(path),
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"intent": "open_file", "target_type": "file"},
                ensure_ascii=False,
            ),
        )
        return {
            "type": "disk_result",
            "summary": f"opened file {path}",
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "open_file",
        }

    def _launch_path(self, path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], start_new_session=True)

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
        return (now - at).total_seconds() < DEBOUNCE_SECONDS

    async def _list_debounced(self, target: str, now: datetime) -> bool:
        raw = await self.db.get_body_memory(LIST_DEBOUNCE_KEY)
        if not isinstance(raw, dict):
            return False
        if str(raw.get("target")) != target:
            return False
        try:
            at = datetime.fromisoformat(str(raw.get("at")))
        except Exception:
            return False
        return (now - at).total_seconds() < DEBOUNCE_SECONDS

    async def _mark_debounce(self, target: str, now: datetime) -> None:
        await self.db.set_body_memory(
            DEBOUNCE_KEY,
            {"target": target, "at": now.isoformat(timespec="seconds")},
        )

    async def _mark_list_debounce(self, target: str, now: datetime) -> None:
        await self.db.set_body_memory(
            LIST_DEBOUNCE_KEY,
            {"target": target, "at": now.isoformat(timespec="seconds")},
        )

    async def _fail(
        self,
        qi_line: str,
        summary: str,
        *,
        season: str,
        now: datetime,
        action_kind: str = "list_dir",
    ) -> dict[str, Any]:
        await self.db.insert_action(
            action_kind,
            summary,
            outcome=OUTCOME_FAILED_CAPABILITY,
            season=season,
            now=now,
        )
        return {
            "type": "disk_result",
            "summary": summary,
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_FAILED_CAPABILITY,
        }
