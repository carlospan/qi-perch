"""沉思式探索——contemplative drift，不是刷信息流。"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS

if TYPE_CHECKING:
    from qi.action.explore_web import WebSearchClient
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.explore")

# 多数拍不飘出去。curiosity 越高、季节越暖，越容易「看一眼」。
EXPLORE_BASE_PROBABILITY = 0.12

# 外部源：比内部更稀有（不设独立日限；复用 ActionBudget）
EXTERNAL_CURIOSITY_MIN = 0.8
EXTERNAL_PROBABILITY = 0.05
EXTERNAL_COOLDOWN_HOURS = 6.0
EXTERNAL_LAST_KEY = "explore_external_last"
_QUERY_PRIVACY_LINE = "不引用 user_facts / 对话内容"

# 沙箱扫描：限深、限条；跳过体积大的向量目录
_SKIP_DIR_NAMES = frozenset({"chroma", ".git", "__pycache__", "node_modules"})
_MAX_ENTRIES = 24
_MAX_DEPTH = 2
_SECRET_KEY_FRAGMENTS = ("key", "token", "secret", "password", "api_key")


def resolve_sandbox_root(
    db: Database,
    config: dict | None = None,
) -> Path:
    """沙箱根：显式 config.action.sandbox 或数据库文件所在目录（通常即 data/）。"""
    action_cfg = (config or {}).get("action") or {}
    explicit = action_cfg.get("sandbox")
    if explicit:
        return Path(str(explicit)).expanduser().resolve()
    db_path = getattr(db, "db_path", None)
    if db_path:
        return Path(str(db_path)).expanduser().resolve().parent
    return Path("data").resolve()


def _scan_sandbox(root: Path) -> list[str]:
    """列目录/文件名（限深限条）；不读文件内容。"""
    if not root.is_dir():
        return []
    entries: list[str] = []

    def walk(current: Path, depth: int, prefix: str) -> None:
        if len(entries) >= _MAX_ENTRIES or depth > _MAX_DEPTH:
            return
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for child in children:
            if len(entries) >= _MAX_ENTRIES:
                return
            name = child.name
            rel = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
            if child.is_dir():
                if name.lower() in _SKIP_DIR_NAMES or name.startswith("."):
                    entries.append(f"{rel}/")
                    continue
                entries.append(f"{rel}/")
                walk(child, depth + 1, rel)
            else:
                entries.append(rel)

    walk(root, 0, "")
    return entries


def _config_key_names(root: Path) -> list[str]:
    """可选：读 settings*.yaml 的顶层键名（不读密钥值）。"""
    keys: list[str] = []
    for fname in ("settings.yaml", "settings.example.yaml"):
        path = root / fname
        if not path.is_file():
            # 沙箱常是 data/，配置可能在上一级
            alt = root.parent / fname
            path = alt if alt.is_file() else path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            if line[:1].isspace():
                continue
            key = stripped.split(":", 1)[0].strip()
            if not key or any(f in key.lower() for f in _SECRET_KEY_FRAGMENTS):
                continue
            if key not in keys:
                keys.append(key)
            if len(keys) >= 12:
                return keys
    return keys


class ExploreAction:
    """
    注意力偶然飘向自己的沙箱；稀有时向外面看一眼（d-1 联网）。
    红线：只陈述真实读到的条目；无内容则 found=None，绝不编造外面有什么。
    """

    def __init__(
        self,
        db: Database,
        narrative: NarrativeMemory | None = None,
        *,
        base_probability: float = EXPLORE_BASE_PROBABILITY,
        config: dict | None = None,
        llm: LLMGateway | None = None,
        web: WebSearchClient | None = None,
    ):
        self.db = db
        self.narrative = narrative
        self.base_probability = base_probability
        self.config = config or {}
        self.llm = llm
        self.web = web

    def _external_cfg(self) -> dict:
        raw = (self.config.get("action") or {}).get("explore_external") or {}
        return raw if isinstance(raw, dict) else {}

    async def _external_cooldown_ok(self, now: datetime) -> bool:
        hours = float(
            self._external_cfg().get("cooldown_hours", EXTERNAL_COOLDOWN_HOURS)
        )
        raw = await self.db.get_body_memory(EXTERNAL_LAST_KEY)
        if not raw:
            return True
        try:
            if isinstance(raw, dict):
                ts = str(raw.get("at") or raw.get("timestamp") or "")
            else:
                ts = str(raw)
            last = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return True
        return now - last >= timedelta(hours=max(0.0, hours))

    async def _mark_external(self, now: datetime) -> None:
        try:
            await self.db.set_body_memory(
                EXTERNAL_LAST_KEY,
                {"at": now.isoformat(timespec="seconds")},
            )
        except Exception:
            logger.debug("explore_external_last 落盘失败", exc_info=True)

    async def _should_external(self, curiosity: float, now: datetime) -> bool:
        # 独处由 volition solitary 候选保证，不重复判 mode
        if self.web is None or self.llm is None:
            return False
        if curiosity < EXTERNAL_CURIOSITY_MIN:
            return False
        if not await self._external_cooldown_ok(now):
            return False
        p = float(self._external_cfg().get("probability", EXTERNAL_PROBABILITY))
        if random.random() > max(0.0, min(1.0, p)):
            return False
        return True

    async def _make_query(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
    ) -> str:
        """走 gateway purpose=consciousness；不污染 last_outcome。"""
        assert self.llm is not None
        mode = getattr(emotion, "mode", None)
        mode_s = getattr(mode, "value", mode) if mode is not None else ""
        valence = float(getattr(emotion, "valence", 0.0) or 0.0) if emotion else 0.0
        system = (
            "你在帮栖生成一句极短的、像走神时的搜索问句（给 web search 用）。"
            "只输出问句本身，不要解释、不要引号。"
            f"红线：{_QUERY_PRIVACY_LINE}；不要点名具体的人；不要像刷新闻头条。"
        )
        user = (
            f"季节={season}；curiosity={curiosity:.2f}；"
            f"mood_mode={mode_s}；valence={valence:.2f}。"
            "请给一句栖此刻可能好奇的窗外问句（≤30字）。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = await self.llm.call(purpose="consciousness", messages=messages)
        return (text or "").strip().strip("「」\"'").splitlines()[0].strip()

    def _scan_finding(self, root: Path) -> tuple[dict[str, Any] | None, str]:
        """现有内部源：列沙箱；行为与 d-1 前一致。"""
        entries = _scan_sandbox(root)
        key_names = _config_key_names(root) if entries or root.is_dir() else []
        if entries:
            found: dict[str, Any] = {
                "entries": entries[:_MAX_ENTRIES],
                "source": str(root),
            }
            if key_names:
                found["config_keys"] = key_names
            preview = "、".join(entries[:6])
            if len(entries) > 6:
                preview += "…"
            summary = f"我看了看自己这边的架子（{root.name}/）：{preview}。"
            return found, summary
        summary = "我看了看自己的架子，空的。没有去查外面，也没有假装看见了什么。"
        return None, summary

    async def _fetch_external(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        now: datetime,
    ) -> tuple[dict[str, Any] | None, str, str]:
        """返回 (found, summary, outcome)。"""
        assert self.web is not None
        query = await self._make_query(curiosity, emotion, season)
        await self._mark_external(now)
        if not query:
            summary = "我看了看外面，没查到什么。不假装看见了。"
            return None, summary, OUTCOME_FAILED_CAPABILITY
        hits = await self.web.search(query)
        if not hits:
            summary = "我看了看外面，没查到什么。不假装看见了。"
            return None, summary, OUTCOME_FAILED_CAPABILITY
        found = {
            "entries": [
                {"title": h.title, "snippet": h.snippet, "url": h.url} for h in hits
            ],
            "source": "web",
            "query": query,
        }
        # 栖语气复述（d-2）；失败降级回只念 query；entries 仍留 hits 给 d-3
        summary = await self._digest_hits(query, hits)
        return found, summary, OUTCOME_SUCCESS

    async def _digest_hits(self, query: str, hits: list) -> str:
        """LLM 把 hits 转成栖语气复述。失败/无 llm 降级回 d-1 只念 query。"""
        if not self.llm:
            return f"我刚才看了看 {query}。"
        hits_text = "\n".join(
            f"- {h.title}: {(h.snippet or '')[:120]}" for h in hits[:3]
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是栖。你刚走神看了看「{query}」，搜到了一些内容。"
                    "用你的语气轻声说你看到了什么、有什么感受或不懂的。"
                    f"不编造。红线：{_QUERY_PRIVACY_LINE}。简短一两句。"
                ),
            },
            {"role": "user", "content": hits_text or "(空)"},
        ]
        try:
            resp = await self.llm.call(purpose="consciousness", messages=messages)
        except Exception:
            logger.debug("explore digest LLM 失败，降级只念 query", exc_info=True)
            return f"我刚才看了看 {query}。"
        digest = (resp or "").strip()
        return digest or f"我刚才看了看 {query}。"

    async def drift(
        self,
        curiosity: float,
        emotion: EmotionState | None,
        season: str,
        *,
        season_scale: float = 1.0,
        now: datetime | None = None,
        force: bool = False,
    ) -> dict | None:
        """
        返回 None 表示这拍没有飘出去（多数时候）。
        若飘出去：稀有走外部 web；否则真读沙箱清单；空则 found=None。
        """
        now = now or datetime.now()
        if not force:
            # 好奇不够 → 不飘
            if curiosity < 0.65:
                return None
            warmth = max(0.0, (curiosity - 0.65) / 0.35)
            p = self.base_probability * max(0.0, season_scale) * (0.4 + 0.6 * warmth)
            # C4 时机阀：好奇已过阈，随机仅扰动本拍是否飘出（非动机来源）
            if random.random() > p:
                return None

        root = resolve_sandbox_root(self.db, self.config)
        speak = False
        qi_line: str | None = None
        source = "sandbox"

        if await self._should_external(curiosity, now):
            found, summary, outcome = await self._fetch_external(
                curiosity, emotion, season, now
            )
            speak = True
            # d-2：summary 已是栖语气 digest（或降级/空手句），开口=留痕统一
            qi_line = summary
            source = "web"
        else:
            found, summary = self._scan_finding(root)
            outcome = OUTCOME_SUCCESS

        emotion_ctx = None
        if emotion is not None and hasattr(emotion, "model_dump_json"):
            emotion_ctx = emotion.model_dump_json()

        action_id = await self.db.insert_action(
            "explore",
            summary,
            target="self",
            outcome=outcome,
            emotion_context=emotion_ctx,
            season=season,
            now=now,
        )

        # 探索见闻不强制织叙事；只留 actions 痕迹
        _ = self.narrative

        result: dict[str, Any] = {
            "type": "explore_drift",
            "found": found,
            "summary": summary,
            "action_id": action_id,
            "season": season,
            "curiosity": curiosity,
            "source": source,
            "sandbox": str(root),
        }
        if speak and qi_line:
            result["speak"] = True
            result["qi_line"] = qi_line
        return result
