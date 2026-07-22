"""具身 WebSocket 服务——栖的身体与前端对话的通道。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("qi.embodiment")

WS_HOST = "127.0.0.1"
WS_PORT = 9527

if TYPE_CHECKING:
    from qi.core.brain import Brain


class EmbodimentServer:
    """后端推送状态，前端推送话语。"""

    def __init__(self, brain: Brain, host: str = WS_HOST, port: int = WS_PORT):
        self.brain = brain
        self.host = host
        self.port = port
        self.clients: set[Any] = set()
        self.running = False
        self._server = None
        self._ping_task: asyncio.Task | None = None

    async def start(self) -> None:
        import websockets

        self.running = True
        self._server = await websockets.serve(self._handler, self.host, self.port)
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("具身通道已打开 ws://%s:%s", self.host, self.port)
        await asyncio.Future()  # run forever until cancelled

    async def stop(self) -> None:
        self.running = False
        if self._ping_task:
            self._ping_task.cancel()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _ping_loop(self) -> None:
        while self.running:
            await asyncio.sleep(30)
            await self.broadcast({"type": "ping", "payload": {"ts": int(time.time() * 1000)}})

    async def _handler(self, websocket) -> None:
        self.clients.add(websocket)
        try:
            avatar = (
                self.brain.avatar.current_state.to_dict()
                if getattr(self.brain, "avatar", None)
                else {"posture": "idle", "expression": "neutral", "effect": "none"}
            )
            season = "spring"
            mode = "awake"
            if getattr(self.brain, "relationship", None) is not None:
                season = self.brain.relationship.state.season
            if getattr(self.brain, "emotion", None) is not None:
                mode = self.brain.emotion.mode.value
            await self.broadcast(
                {
                    "type": "state",
                    "payload": {
                        "avatar_state": avatar,
                        "season": season,
                        "mode": mode,
                    },
                }
            )
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle_client_message(msg)
        except Exception:
            logger.debug("前端连接关闭", exc_info=True)
        finally:
            self.clients.discard(websocket)

    async def _handle_client_message(self, msg: dict) -> None:
        msg_type = msg.get("type")
        payload = msg.get("payload") or {}
        if msg_type == "user_message":
            text = (payload.get("text") or "").strip()
            if not text:
                return
            await self.send_typing()
            response = await self.brain.receive_user_message(text)
            # speech 由 brain 表达路径推送；若空则提示
            if not response:
                await self.broadcast(
                    {
                        "type": "speech",
                        "payload": {
                            "text": "……",
                            "emotion": self.brain.emotion.description(),
                            "tone": "quiet",
                        },
                    }
                )
        elif msg_type == "presence":
            online = bool(payload.get("online", True))
            self.brain.user_online = online
            self.brain.perception.set_user_presence(online)
        elif msg_type == "pong":
            pass
        elif msg_type == "command":
            cmd = (payload.get("text") or "").strip()
            if cmd == "/state":
                e = self.brain.emotion
                await self.broadcast(
                    {
                        "type": "emotion_update",
                        "payload": {
                            "energy": e.energy,
                            "valence": e.valence,
                            "arousal": e.arousal,
                            "security": e.security,
                            "curiosity": e.curiosity,
                            "attachment": e.attachment,
                            "mode": e.mode.value,
                            "description": e.description(),
                            "stage": self.brain.relationship_stage,
                        },
                    }
                )

    async def broadcast(self, message: dict) -> None:
        if not self.clients:
            return
        raw = json.dumps(message, ensure_ascii=False)
        await asyncio.gather(
            *[client.send(raw) for client in list(self.clients)],
            return_exceptions=True,
        )

    async def send_speech(self, text: str, emotion: str, tone: str = "") -> None:
        await self.broadcast(
            {"type": "speech", "payload": {"text": text, "emotion": emotion, "tone": tone}}
        )

    async def send_state_change(self, avatar_state: dict) -> None:
        await self.broadcast({"type": "state", "payload": {"avatar_state": avatar_state}})

    async def send_typing(self) -> None:
        await self.broadcast({"type": "typing", "payload": {}})

    async def send_emotion_update(self, snapshot: dict) -> None:
        await self.broadcast({"type": "emotion_update", "payload": snapshot})

    async def send_audio(self, audio_b64: str, mime: str = "audio/mpeg") -> None:
        await self.broadcast(
            {"type": "audio", "payload": {"data": audio_b64, "mime": mime}}
        )
