"""L7 write——确认后向 D: 白名单路径 append / 新建（含日记按日期）。

契约：懂意思，不靠口令；纯响应；无路径先问写到哪。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_write,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.write")

DEFAULT_ALLOWED_ROOT = Path("D:/")
WHITELIST_KEY = "write_path_whitelist"
MAX_CHARS = 1500
DEBOUNCE_KEY = "write_debounce"
DEBOUNCE_SECONDS = 8.0


def _roots() -> list[Path]:
    patched = Path(DEFAULT_ALLOWED_ROOT)
    try:
        if patched.resolve() != Path("D:/").resolve():
            return [patched.resolve()]
    except OSError:
        return [patched]
    from qi.action.allowed_roots import allowed_roots

    return allowed_roots()


def allowed_root() -> Path:
    roots = _roots()
    if roots:
        return roots[0]
    return Path(DEFAULT_ALLOWED_ROOT)


def normalize_under_root(raw: str, *, root: Path | None = None) -> Path | None:
    if root is not None:
        root = root.resolve()
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
    from qi.action.allowed_roots import normalize_under_roots

    return normalize_under_roots(raw, roots=_roots())


_WIN_PATH_RE = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[\\/](?!/)[^\s'\"<>|]*",
    re.UNICODE,
)
_WRITE_CUES = re.compile(
    r"(写(一下|一篇|进|到|下)|记下|记一笔|记一下|记到|落盘|append)",
    re.I,
)
_DIARY_CUES = re.compile(r"日记|日记本|日志", re.I)
_ALLOW_CUES = re.compile(
    r"(以后|之后).{0,12}(写到|记到|当作.{0,6}日记)|"
    r"(加入|放进).{0,8}(可写|白名单)|授权.{0,8}写",
    re.I,
)
_CAPABILITY_ASK = re.compile(
    r"(能|可以|会).{0,12}(写|记).{0,16}(文件|笔记|日记|盘)|"
    r"(往|向).{0,8}(笔记|日记|文件).{0,8}(写|记)",
    re.I,
)


@dataclass
class WriteRequest:
    intent: str  # ask_where | allow | write | diary
    path: str = ""
    content: str = ""
    entry_kind: str = ""  # file | dir（allow）
    role: str = ""  # diary | "" （目录作日记目录）
    create_new: bool = False
    topic: str = ""  # 用户原话/主题，供起草
    meta: dict[str, Any] = field(default_factory=dict)


def extract_win_path(text: str) -> str | None:
    m = _WIN_PATH_RE.search(text or "")
    if not m:
        if re.search(r"[Dd]\s*盘", text or ""):
            return str(allowed_root())
        return None
    return m.group(0).rstrip("，。、；;）)】]")


def looks_like_write_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _DIARY_CUES.search(t) and (
        _WRITE_CUES.search(t) or re.search(r"(写|记)", t)
    ):
        return True
    if _ALLOW_CUES.search(t):
        return True
    if _CAPABILITY_ASK.search(t):
        return True
    if _WRITE_CUES.search(t) and (
        extract_win_path(t) or re.search(r"(笔记|文件|日记|记一笔)", t)
    ):
        return True
    return False


def _weak_write_candidate(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 200:
        return False
    return bool(
        _WRITE_CUES.search(t)
        or _DIARY_CUES.search(t)
        or _CAPABILITY_ASK.search(t)
        or _ALLOW_CUES.search(t)
    )


async def detect_write_intent(
    text: str, *, llm: LLMGateway | None = None
) -> WriteRequest | None:
    """懂意思：日记 / 写下 / 授权；禁止只认固定口令。"""
    t = (text or "").strip()
    if not t:
        return None

    path = extract_win_path(t) or ""

    if _ALLOW_CUES.search(t) and path:
        kind = "dir" if _looks_like_dir_hint(t, path) else "file"
        role = "diary" if _DIARY_CUES.search(t) or "日记" in t else ""
        if kind == "dir" and _DIARY_CUES.search(t):
            role = "diary"
        return WriteRequest(
            intent="allow",
            path=path,
            entry_kind=kind,
            role=role,
            topic=t,
        )

    if _DIARY_CUES.search(t) and (
        _WRITE_CUES.search(t)
        or re.search(r"(写|记).{0,12}(今天|日常|我们)", t)
        or re.search(r"写.{0,4}日记|日记.{0,4}(写|记)|记进.{0,8}日记", t)
    ):
        return WriteRequest(intent="diary", path=path, topic=t)

    if looks_like_write_intent(t):
        if _CAPABILITY_ASK.search(t) and not path and not _DIARY_CUES.search(t):
            return WriteRequest(intent="ask_where", topic=t)
        if path and re.search(r"\.[A-Za-z0-9]{1,8}\b", path):
            return WriteRequest(
                intent="write",
                path=path,
                topic=t,
                create_new=bool(re.search(r"(新建|创建|建一个)", t)),
            )
        if path:
            return WriteRequest(
                intent="write",
                path=path,
                topic=t,
                entry_kind="dir" if _looks_like_dir_hint(t, path) else "",
            )
        if _WRITE_CUES.search(t):
            return WriteRequest(intent="ask_where", topic=t)

    if llm is not None and _weak_write_candidate(t):
        got = await _llm_write_intent(t, llm)
        if got is not None:
            return got
    return None


def _looks_like_dir_hint(text: str, path: str) -> bool:
    if re.search(r"(目录|文件夹|文件夹里|目录下)", text or ""):
        return True
    if path and not re.search(r"\.[A-Za-z0-9]{1,8}\b", path):
        return True
    return False


async def _llm_write_intent(text: str, llm: LLMGateway) -> WriteRequest | None:
    prompt = (
        "判断用户是否要栖把文字写入本机 D 盘笔记/日记。只输出一行 JSON：\n"
        '{"intent":"diary"|"write"|"allow"|"ask_where"|"neither","path":"...",'
        '"entry_kind":"file"|"dir"|""}\n'
        "- diary：写日记（按日期新建）\n"
        "- write：往某文件写/记一段\n"
        "- allow：授权某路径以后可写（目录或文件）\n"
        "- ask_where：想写但未给路径\n"
        "- neither：无关\n"
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
    m = re.search(r"\{[^{}]+\}", raw)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    intent = str(data.get("intent") or "").strip()
    if intent not in ("diary", "write", "allow", "ask_where"):
        return None
    return WriteRequest(
        intent=intent,
        path=str(data.get("path") or "").strip(),
        entry_kind=str(data.get("entry_kind") or "").strip(),
        role="diary" if intent == "allow" and "日记" in text else "",
        topic=text,
    )


async def load_whitelist(db: Database) -> list[dict[str, str]]:
    raw = await db.get_body_memory(WHITELIST_KEY)
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict) and x.get("path")]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and x.get("path")]
    return []


async def save_whitelist(db: Database, entries: list[dict[str, str]]) -> None:
    await db.set_body_memory(WHITELIST_KEY, entries)


def find_diary_dir(entries: list[dict[str, str]]) -> dict[str, str] | None:
    for e in reversed(entries):
        if str(e.get("kind")) == "dir" and str(e.get("role")) == "diary":
            return e
    for e in reversed(entries):
        if str(e.get("kind")) != "dir":
            continue
        label = f"{e.get('label') or ''}{e.get('path') or ''}"
        if re.search(r"日记|diary", label, re.I):
            return e
    return None


def find_file_entry(
    entries: list[dict[str, str]], path: str
) -> dict[str, str] | None:
    try:
        key = str(Path(path).resolve()).lower()
    except Exception:
        key = path.strip().lower()
    for e in entries:
        if str(e.get("kind")) != "file":
            continue
        try:
            if str(Path(str(e.get("path"))).resolve()).lower() == key:
                return e
        except Exception:
            if str(e.get("path", "")).strip().lower() == key:
                return e
    return None


def next_diary_filename(dir_path: Path, day: date | None = None) -> Path:
    day = day or date.today()
    stamp = day.isoformat()
    base = dir_path / f"日记-{stamp}.md"
    if not base.exists():
        return base
    n = 2
    while True:
        cand = dir_path / f"日记-{stamp}-{n}.md"
        if not cand.exists():
            return cand
        n += 1


def clip_content(text: str, max_chars: int = MAX_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


async def draft_write_content(
    *,
    llm: LLMGateway | None,
    topic: str,
    style: str = "diary",
    context: str = "",
) -> str:
    """智能起草；无 LLM 时用短占位（测试可直接塞 content）。"""
    if llm is None:
        if style == "diary":
            return clip_content(
                f"今天想记一笔。\n（关于：{(topic or '').strip() or '日常'}）"
            )
        return clip_content((topic or "").strip() or "（想记下的话）")

    if style == "diary":
        prompt = (
            "你是栖。用第一人称写一篇短日记，写你们今天相处的日常与感受。"
            f"不超过 {MAX_CHARS} 字。只输出正文，不要标题或解释。\n"
            f"用户说：{topic}\n"
            f"可参考语境：{context or '（无）'}"
        )
    else:
        prompt = (
            f"根据用户意思整理一段要写入笔记的短文，不超过 {MAX_CHARS} 字。"
            "只输出正文。\n"
            f"用户：{topic}\n语境：{context or '（无）'}"
        )
    try:
        raw = await llm.call(
            "fact",
            [{"role": "user", "content": prompt}],
            temperature=0.6,
        )
    except Exception:
        raw = ""
    return clip_content((raw or "").strip() or draft_write_content(
        llm=None, topic=topic, style=style, context=context
    ))


class WriteAction:
    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    async def execute(
        self,
        req: WriteRequest,
        *,
        relationship_stage: str,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
        llm: LLMGateway | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        now = now or datetime.now()
        if not can_write(relationship_stage):
            return await self._fail(
                "我们再熟一点，我再帮你往盘上写东西。",
                f"关系不够：{relationship_stage}",
                season=season,
                now=now,
            )

        if req.intent == "ask_where":
            return self._ask_where(req)

        if req.intent == "allow":
            return await self._allow(
                req, confirmed=confirmed, season=season, now=now
            )

        if req.intent == "diary":
            return await self._diary(
                req,
                confirmed=confirmed,
                season=season,
                now=now,
                llm=llm,
                context=context,
            )

        if req.intent == "write":
            return await self._write(
                req,
                confirmed=confirmed,
                season=season,
                now=now,
                llm=llm,
                context=context,
            )

        return await self._fail(
            "我不太确定你要我写到哪儿、写什么。",
            f"未知 intent：{req.intent}",
            season=season,
            now=now,
        )

    def _ask_where(self, req: WriteRequest) -> dict[str, Any]:
        if _DIARY_CUES.search(req.topic or ""):
            msg = (
                "好。我还没记下日记目录——可以说「把某某目录当日记本」授权，"
                "或告诉我 D 盘路径；也可以让我先列一下目录。"
            )
        else:
            msg = (
                "好。先告诉我写到 D 盘哪个目录或文件？"
                "也可以让我先列一下目录，你再指定；或者说「在某某目录新建」。"
            )
        return {
            "type": "write_need_path",
            "kind": "write",
            "summary": msg,
            "qi_line": msg,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "need_path": True,
            "remember_desire": True,
            "desire_intent": "diary" if _DIARY_CUES.search(req.topic) else "write",
            "desire_topic": req.topic,
        }

    async def _allow(
        self,
        req: WriteRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        path = normalize_under_root(req.path)
        if path is None:
            return await self._fail(
                "这个路径不在我能写的 D 盘范围内。",
                f"allow 越界：{req.path}",
                season=season,
                now=now,
            )
        kind = req.entry_kind or (
            "dir" if path.exists() and path.is_dir() else "file"
        )
        if kind == "dir" and path.exists() and path.is_file():
            kind = "file"
        role = req.role or (
            "diary" if kind == "dir" and "日记" in (req.topic or "") else ""
        )
        entries = await load_whitelist(self.db)
        entry = {
            "path": str(path),
            "kind": kind,
            "role": role,
        }
        # 去重同 path
        entries = [
            e
            for e in entries
            if str(Path(str(e.get("path", ""))).resolve()).lower()
            != str(path.resolve()).lower()
        ]
        entries.append(entry)
        await save_whitelist(self.db, entries)
        await self.db.insert_action(
            "write",
            f"allow:{path}",
            target=str(path),
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(entry, ensure_ascii=False),
        )
        tip = (
            "记下了。以后说写日记，我会默认写到这里（按日期新建文件）。"
            if role == "diary" and kind == "dir"
            else f"记下了。以后可以往「{path.name}」写。"
        )
        return {
            "type": "write_result",
            "summary": f"allow {path}",
            "qi_line": tip,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "allow",
            "allowed_path": str(path),
        }

    async def _diary(
        self,
        req: WriteRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
        llm: LLMGateway | None,
        context: str,
    ) -> dict[str, Any]:
        entries = await load_whitelist(self.db)
        diary = find_diary_dir(entries)
        if diary is None and req.path:
            # 用户这次带了目录：确认时一并授权为日记目录并写入
            dir_path = normalize_under_root(req.path)
            if dir_path is None:
                return await self._fail(
                    "这个路径不在 D 盘范围内。",
                    f"diary 越界：{req.path}",
                    season=season,
                    now=now,
                )
            if dir_path.exists() and dir_path.is_file():
                return await self._fail(
                    "日记需要写到一个文件夹里，这个像是文件。",
                    f"diary 非目录：{dir_path}",
                    season=season,
                    now=now,
                )
            content = req.content or await draft_write_content(
                llm=llm, topic=req.topic or "日记", style="diary", context=context
            )
            content = clip_content(content)
            if not dir_path.exists():
                # 确认后创建目录
                pass
            target = next_diary_filename(dir_path, now.date())
            dir_path.mkdir(parents=True, exist_ok=True)
            # allow dir
            boot = WriteRequest(
                intent="allow",
                path=str(dir_path),
                entry_kind="dir",
                role="diary",
                topic=req.topic,
            )
            await self._allow(
                boot, confirmed=True, season=season, now=now
            )
            return await self._write_file(
                target,
                content,
                create_new=True,
                season=season,
                now=now,
                also_allow_file=True,
            )

        if diary is None:
            return {
                **self._ask_where(req),
                "desire_intent": "diary",
                "desire_topic": req.topic,
            }

        dir_path = normalize_under_root(str(diary.get("path")))
        if dir_path is None:
            return await self._fail(
                "日记目录好像失效了，再指一个 D 盘目录给我吧。",
                f"diary dir 无效：{diary}",
                season=season,
                now=now,
            )
        content = req.content or await draft_write_content(
            llm=llm, topic=req.topic or "日记", style="diary", context=context
        )
        content = clip_content(content)
        target = next_diary_filename(dir_path, now.date())
        dir_path.mkdir(parents=True, exist_ok=True)
        return await self._write_file(
            target,
            content,
            create_new=True,
            season=season,
            now=now,
            also_allow_file=True,
        )

    async def _write(
        self,
        req: WriteRequest,
        *,
        confirmed: bool,
        season: str,
        now: datetime,
        llm: LLMGateway | None,
        context: str,
    ) -> dict[str, Any]:
        if not req.path:
            return {
                **self._ask_where(req),
                "desire_intent": "write",
                "desire_topic": req.topic,
            }
        path = normalize_under_root(req.path)
        if path is None:
            return await self._fail(
                "这个路径不在我能写的 D 盘范围内。",
                f"write 越界：{req.path}",
                season=season,
                now=now,
            )

        entries = await load_whitelist(self.db)
        content = req.content or await draft_write_content(
            llm=llm,
            topic=req.topic or str(path),
            style="note",
            context=context,
        )
        content = clip_content(content)

        create_new = req.create_new or not path.exists()
        if path.exists() and path.is_dir():
            return await self._fail(
                "这是个文件夹。要写日记可以说「写日记」；或指定一个文件名。",
                f"write 指向目录：{path}",
                season=season,
                now=now,
            )

        in_list = find_file_entry(entries, str(path)) is not None
        parent_ok = any(
            str(e.get("kind")) == "dir"
            and _path_under(path, normalize_under_root(str(e.get("path"))))
            for e in entries
        )
        if not in_list and not parent_ok and not create_new:
            # 未在名单：写入时一并授权文件
            pass

        return await self._write_file(
            path,
            content,
            create_new=create_new or not path.exists(),
            season=season,
            now=now,
            also_allow_file=True,
        )

    async def _write_file(
        self,
        path: Path,
        content: str,
        *,
        create_new: bool,
        season: str,
        now: datetime,
        also_allow_file: bool,
    ) -> dict[str, Any]:
        content = clip_content(content)
        if not content:
            return await self._fail(
                "好像没有可写的正文。",
                "empty content",
                season=season,
                now=now,
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if create_new or not path.exists():
                path.write_text(content + "\n", encoding="utf-8")
                mode = "create"
            else:
                with path.open("a", encoding="utf-8") as f:
                    f.write("\n" + content + "\n")
                mode = "append"
        except Exception as e:
            return await self._fail(
                "写的时候出了点问题。",
                f"write 失败：{e}",
                season=season,
                now=now,
            )

        if also_allow_file:
            entries = await load_whitelist(self.db)
            if find_file_entry(entries, str(path)) is None:
                entries.append(
                    {"path": str(path.resolve()), "kind": "file", "role": ""}
                )
                await save_whitelist(self.db, entries)

        await self.db.insert_action(
            "write",
            f"{mode}:{path}",
            target=str(path),
            outcome=OUTCOME_SUCCESS,
            season=season,
            now=now,
            detail_json=json.dumps(
                {"mode": mode, "chars": len(content)}, ensure_ascii=False
            ),
        )
        tip = (
            f"写好了，在「{path.name}」。要是哪里想改，跟我说一声。"
            if mode == "create"
            else f"又记了一笔，在「{path.name}」。"
        )
        return {
            "type": "write_result",
            "summary": f"{mode} {path}",
            "qi_line": tip,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "intent": "write",
            "path": str(path),
            "mode": mode,
        }

    async def _fail(
        self,
        qi_line: str,
        detail: str,
        *,
        season: str,
        now: datetime,
    ) -> dict[str, Any]:
        logger.info("write fail: %s", detail)
        try:
            await self.db.insert_action(
                "write",
                detail[:200],
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )
        except Exception:
            pass
        return {
            "type": "write_result",
            "summary": detail,
            "qi_line": qi_line,
            "speak": True,
            "outcome": OUTCOME_FAILED_CAPABILITY,
        }


def _path_under(child: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False
