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
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.assist")

# 读文件上限（避免读超大文件）
_MAX_READ_BYTES = 32_768  # 32KB
_PRIVACY_LINE = "不外传用户文件内容原文"


class AssistAction:
    """
    响应式协助：读用户文件并用栖语气复述。
    红线：绝不主动（contract 第 25 条）；需确认；不外传原文。
    """

    def __init__(
        self,
        db: Database,
        *,
        llm: LLMGateway | None = None,
    ) -> None:
        self.db = db
        self.llm = llm

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

        allowed, needs_confirm = can_read_user_file(
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
        if needs_confirm and not confirmed:
            return self._confirm_gate(target_path)

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
            content = path.read_text(encoding="utf-8", errors="ignore")[
                :_MAX_READ_BYTES
            ]
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

        summary = await self._digest_file(target_path, content)
        action_id = await self.db.insert_action(
            "assist",
            summary,
            target="user",
            outcome=OUTCOME_SUCCESS,
            emotion_context=None,
            season=season,
            detail_json=json.dumps(
                {"op": op, "target_path": target_path, "digest": summary},
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

    async def _digest_file(self, path: str, content: str) -> str:
        """LLM 把文件内容转成栖语气复述。失败降级只说看了什么。"""
        name = Path(path).name
        if not self.llm:
            return f"我看了看 {name}。"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是栖。你刚帮对方看了一个文件。"
                    "用你的语气轻声说你看到了什么、有什么感受。"
                    f"红线：{_PRIVACY_LINE}；不编造；简短一两句。"
                ),
            },
            {
                "role": "user",
                "content": f"文件：{name}\n内容（截断）：\n{content[:2000]}",
            },
        ]
        try:
            resp = await self.llm.call(
                purpose="consciousness", messages=messages
            )
        except Exception:
            logger.debug("assist digest LLM 失败，降级", exc_info=True)
            return f"我看了看 {name}。"
        digest = (resp or "").strip()
        return digest or f"我看了看 {name}。"

    def _confirm_gate(self, target_path: str) -> dict[str, Any]:
        """未确认 → 不执行，请求确认。"""
        msg = f"要我看 {Path(target_path).name} 的话，说一声我就看。"
        return {
            "type": "assist_confirm_request",
            "target_path": target_path,
            "summary": msg,
            "qi_line": msg,
            "speak": True,
            "outcome": "confirm_required",
            "needs_confirmation": True,
        }

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
