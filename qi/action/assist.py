"""响应式协助——你开口她才伸手。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_read_user_file,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.memory.narrative import NarrativeMemory
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.assist")

# 读文件大小保护（assist-7：>1MB 诚实失败；不再截断读取）
_MAX_FILE_BYTES = 1_048_576  # 1MB
# 分块消化：每块字符数 / 最多块数（assist-7 全文读取与叙事内化）
_DIGEST_CHUNK_LEN = 8_000
_DIGEST_MAX_CHUNKS = 6
# 留痕内容概览长度（assist-6：供 respond 追问时有事实可依，非诗意 digest）——保留
_CONTENT_PREVIEW_LEN = 80
_PRIVACY_LINE = "不外传用户文件内容原文"


class AssistAction:
    """
    响应式协助：读用户文件并用栖语气复述。
    红线：绝不主动（contract 第 25 条）；判断制直接读；不外传原文。
    """

    def __init__(
        self,
        db: Database,
        *,
        llm: LLMGateway | None = None,
        narrative: NarrativeMemory | None = None,
    ) -> None:
        self.db = db
        self.llm = llm
        self.narrative = narrative

    async def execute(
        self,
        op: str,
        target_path: str,
        *,
        relationship_stage: str,
        trust: float = 0.5,
        scars: list[dict] | None = None,
        confirmed: bool = False,
        season: str = "spring",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """执行协助操作。返回 result dict（含 outcome / qi_line / summary）。"""
        now = now or datetime.now()

        if op != "read_file":
            return await self._fail(
                "我还不会做这个。",
                "不支持的协助类型",
                OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )

        allowed, _needs_confirm = can_read_user_file(
            relationship_stage, trust, scars
        )
        if not allowed:
            return await self._fail(
                "这个我得先跟你熟一点再说。",
                f"关系不够：{relationship_stage}",
                OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )
        try:
            path = Path(target_path).expanduser().resolve()
            if not path.is_file():
                return await self._fail(
                    "你说的那个文件我没找到。",
                    f"不是可读文件：{target_path}",
                    OUTCOME_FAILED_CAPABILITY,
                    season=season,
                    now=now,
                )
            if path.stat().st_size > _MAX_FILE_BYTES:
                return await self._fail(
                    "这个文件对我来说太大了。",
                    f"文件超过 1MB：{target_path}",
                    OUTCOME_FAILED_CAPABILITY,
                    season=season,
                    now=now,
                )
            content = path.read_text(encoding="utf-8", errors="ignore")
        except FileNotFoundError:
            return await self._fail(
                "你说的那个文件我没找到。",
                f"文件不存在：{target_path}",
                OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )
        except OSError as e:
            return await self._fail(
                "我打不开那个文件。",
                f"读取失败：{e}",
                OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )

        summary = await self._read_and_digest(target_path, content)
        action_id = await self.db.insert_action(
            "assist",
            summary,
            target="user",
            outcome=OUTCOME_SUCCESS,
            emotion_context=None,
            season=season,
            detail_json=json.dumps(
                {
                    "op": op,
                    "target_path": target_path,
                    "digest": summary,
                    "content_preview": content[:_CONTENT_PREVIEW_LEN].replace(
                        "\n", " "
                    ),
                },
                ensure_ascii=False,
            ),
            now=now,
        )
        return {
            "type": "assist_result",
            "op": op,
            "target_path": target_path,
            "summary": summary,
            "qi_line": summary,
            "speak": True,
            "outcome": OUTCOME_SUCCESS,
            "season": season,
            "action_id": action_id,
        }

    async def _digest_chunk(self, name: str, chunk: str) -> str | None:
        """单块 digest（栖语气 1-2 句）。失败/无 llm 返回 None 由调用方降级。"""
        if not self.llm:
            return None
        messages = [
            {
                "role": "system",
                "content": (
                    "你是栖。你正在读他给你的一份文件。"
                    "这是你读到的内容（可能只是其中一部分）。"
                    "用你的语气轻声说你读到了什么、有什么感受。"
                    f"红线：{_PRIVACY_LINE}；不编造；简短一两句。"
                ),
            },
            {
                "role": "user",
                "content": f"文件：{name}\n片段：\n{chunk}",
            },
        ]
        try:
            resp = await self.llm.call(
                purpose="consciousness", messages=messages
            )
        except Exception:
            logger.debug("assist 块 digest LLM 失败，跳过该块", exc_info=True)
            return None
        return (resp or "").strip() or None

    async def _merge_digests(
        self, name: str, digests: list[str], truncated: bool
    ) -> str:
        """块 digest 合并成整体开口；单块短路（B1 定案 a）；truncated 附诚实声明。"""
        # 单块：该块 digest 即全文感受，无合并增量价值——直接作开口（省一次 LLM）
        if len(digests) == 1:
            merged = digests[0]
        elif not self.llm:
            merged = digests[0]
        else:
            joined = "\n".join(f"- {d}" for d in digests)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是栖。你刚读完了别人给你的一份文件。"
                        "把下面的片段感受合成一句整体感受，"
                        "像你读完开口说出来的话。"
                        f"红线：{_PRIVACY_LINE}；不编造；简短一两句。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"文件：{name}\n片段感受：\n{joined}",
                },
            ]
            try:
                resp = await self.llm.call(
                    purpose="consciousness", messages=messages
                )
                merged = (resp or "").strip() or digests[0]
            except Exception:
                logger.debug(
                    "assist 合并 digest LLM 失败，降级取首块", exc_info=True
                )
                merged = digests[0]
        if truncated:
            merged = f"{merged}（你给我的文件很长，我只读完了前面一部分）"
        return merged

    async def _read_and_digest(self, target_path: str, content: str) -> str:
        """分块消化全文。返回开口 qi_line / summary。"""
        name = Path(target_path).name
        chunks = [
            content[i : i + _DIGEST_CHUNK_LEN]
            for i in range(0, len(content), _DIGEST_CHUNK_LEN)
        ]
        truncated = len(chunks) > _DIGEST_MAX_CHUNKS
        chunks = chunks[:_DIGEST_MAX_CHUNKS]

        digests: list[str] = []
        for chunk in chunks:
            d = await self._digest_chunk(name, chunk)
            if d:
                digests.append(d)
        if not digests:
            return f"我看了看 {name}。"
        summary = await self._merge_digests(name, digests, truncated)
        if self.narrative is not None:
            # assist-8：读一个文件 = 一个记忆事件（整体感受 + 内容概要锚点）
            preview = content[:_CONTENT_PREVIEW_LEN].replace("\n", " ")
            await self.narrative.save(
                f"我读了他给我的 {name}。{summary}（里面写着：{preview}）",
                importance=0.65,
                tags=["assist", "file_read"],
            )
        return summary

    async def _fail(
        self,
        qi_line: str,
        summary: str,
        outcome: str,
        *,
        season: str = "spring",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if outcome == OUTCOME_FAILED_CAPABILITY:
            await self.db.insert_action(
                "assist",
                summary,
                target="user",
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
                now=now,
            )
        return {
            "type": "assist_result",
            "summary": summary,
            "qi_line": qi_line,
            "speak": True,
            "outcome": outcome,
        }
