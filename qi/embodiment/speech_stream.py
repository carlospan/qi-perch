"""对话 speech 流式会话——chunk 推前端；打断/失败可收回。"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol

logger = logging.getLogger("qi.embodiment")


class _Broadcaster(Protocol):
    async def broadcast(self, message: dict) -> None: ...


class SpeechStreamSession:
    """一次对话流式出字。idempotent retract；仅 started 后才发 retract/done。"""

    def __init__(self, embodiment: _Broadcaster | None) -> None:
        self.embodiment = embodiment
        self.stream_id = uuid.uuid4().hex[:12]
        self.started = False
        self.retracted = False

    @property
    def live(self) -> bool:
        return self.started and not self.retracted

    async def delta(self, chunk: str) -> None:
        if self.retracted or self.embodiment is None:
            return
        piece = str(chunk or "")
        if not piece:
            return
        self.started = True
        await self.embodiment.broadcast(
            {
                "type": "speech_delta",
                "payload": {"id": self.stream_id, "delta": piece},
            }
        )

    async def retract(self) -> None:
        if self.retracted:
            return
        was_started = self.started
        self.retracted = True
        if not was_started or self.embodiment is None:
            return
        try:
            await self.embodiment.broadcast(
                {
                    "type": "speech_retract",
                    "payload": {"id": self.stream_id},
                }
            )
        except Exception:
            logger.debug("speech_retract 广播失败", exc_info=True)

    async def finish(self, text: str, emotion: str, tone: str = "") -> None:
        if self.retracted or not self.started or self.embodiment is None:
            return
        await self.embodiment.broadcast(
            {
                "type": "speech_done",
                "payload": {
                    "id": self.stream_id,
                    "text": text,
                    "emotion": emotion,
                    "tone": tone,
                },
            }
        )
