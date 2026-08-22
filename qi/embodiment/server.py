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
# 桌面 /history 默认窗口（旧→新中的最近 N 条）；避免库长大后全表推送
HISTORY_WINDOW = 200
# 与 history 同窗回灌的创作卡片上限（按 shared_at 新→旧再裁到窗口）
HISTORY_CARD_LIMIT = 40


def _iso_to_ms(ts_raw: str) -> int | None:
    from datetime import datetime

    try:
        return int(datetime.fromisoformat(ts_raw).timestamp() * 1000)
    except ValueError:
        return None


def _parse_emotion_context(raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return raw


async def build_history_creation_cards(
    db: Any,
    *,
    oldest_at_ms: int | None = None,
    limit: int = HISTORY_CARD_LIMIT,
) -> list[dict]:
    """从已递出 creations 拼 creation_card 列表（旧→新），供 /history 回灌谈区。"""
    try:
        rows = await db.list_recent_shared_creations(limit=limit)
    except Exception:
        logger.exception("拉取已分享创作失败")
        return []

    season_by_ts: dict[str, str] = {}
    action_id_by_ts: dict[str, int] = {}
    try:
        for a in await db.list_recent_actions(limit=max(limit * 2, 80)):
            if a.get("kind") != "share":
                continue
            ts = str(a.get("timestamp") or "")
            if not ts:
                continue
            if a.get("season"):
                season_by_ts[ts] = str(a["season"])
            if a.get("id") is not None:
                action_id_by_ts[ts] = int(a["id"])
    except Exception:
        logger.debug("拉取 share actions 供卡片季节对齐失败", exc_info=True)

    cards: list[dict] = []
    for r in rows:
        content = (r.get("content") or "").strip()
        if not content:
            continue
        ts_raw = str(r.get("shared_at") or "")
        at_ms = _iso_to_ms(ts_raw)
        if at_ms is None:
            continue
        if oldest_at_ms is not None and at_ms < oldest_at_ms:
            continue
        card = {
            "type": "creation_card",
            "creation_id": int(r["id"]),
            "creation_type": str(r.get("type") or "note"),
            "content": content,
            "emotion_context": _parse_emotion_context(r.get("emotion_context")),
            "action_id": action_id_by_ts.get(ts_raw, 0),
            "at": at_ms,
        }
        season = season_by_ts.get(ts_raw)
        if season:
            card["season"] = season
        cards.append(card)
    cards.reverse()  # 库查新→旧；谈区时间轴要旧→新
    return cards


async def build_history_explore_cards(
    db: Any,
    *,
    oldest_at_ms: int | None = None,
    limit: int = HISTORY_CARD_LIMIT,
) -> list[dict]:
    """从 actions.detail_json 拼 explore_drift 列表（旧→新），供 /history 回灌。"""
    try:
        rows = await db.list_recent_explore_card_actions(limit=limit)
    except Exception:
        logger.exception("拉取 explore 见闻卡失败")
        return []

    cards: list[dict] = []
    for r in rows:
        ts_raw = str(r.get("timestamp") or "")
        at_ms = _iso_to_ms(ts_raw)
        if at_ms is None:
            continue
        if oldest_at_ms is not None and at_ms < oldest_at_ms:
            continue
        detail = _parse_emotion_context(r.get("detail_json"))
        if not isinstance(detail, dict):
            continue
        found = detail.get("found")
        if not isinstance(found, dict):
            continue
        entries = found.get("entries")
        source = str(detail.get("source") or found.get("source") or "")
        if source not in ("web", "journal", "web_delegate"):
            continue
        if not isinstance(entries, list) or not entries:
            continue
        try:
            curiosity = float(detail.get("curiosity") or 0.0)
        except (TypeError, ValueError):
            curiosity = 0.0
        summary = str(r.get("summary") or "").strip()
        qi_line = detail.get("qi_line")
        if qi_line is not None:
            qi_line = str(qi_line)
        card = {
            "type": "explore_drift",
            "found": found,
            "summary": summary,
            "qi_line": qi_line if qi_line else summary,
            "action_id": int(r["id"]),
            "curiosity": curiosity,
            "source": source,
            "sandbox": str(detail.get("sandbox") or ""),
            "at": at_ms,
        }
        if r.get("season"):
            card["season"] = str(r["season"])
        cards.append(card)
    cards.reverse()
    return cards


# 仅允许 loopback 绑定；配置里写 0.0.0.0 等会强制回退
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# 浏览器 / Tauri / Vite 常见 Origin；None = 无 Origin 头（本机非浏览器客户端）
WS_ALLOWED_ORIGINS: tuple[str | None, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
    "https://localhost",
    "https://127.0.0.1",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
    None,
)


def resolve_bind(
    host: str | None = None,
    port: int | str | None = None,
) -> tuple[str, int]:
    """解析 embodiment 绑定；非 loopback host 强制回退 127.0.0.1。"""
    h = (host if host is not None else WS_HOST)
    h = str(h).strip() or WS_HOST
    try:
        p = int(port if port is not None else WS_PORT)
    except (TypeError, ValueError):
        p = WS_PORT
    if h not in LOOPBACK_HOSTS:
        logger.warning(
            "embodiment.host=%s 非 loopback，已强制回退 %s（禁止外网暴露）",
            h,
            WS_HOST,
        )
        h = WS_HOST
    if not (1 <= p <= 65535):
        logger.warning("embodiment.port=%s 非法，已回退 %s", port, WS_PORT)
        p = WS_PORT
    return h, p


if TYPE_CHECKING:
    from qi.core.brain import Brain


class EmbodimentServer:
    """后端推送状态，前端推送话语。"""

    def __init__(self, brain: Brain, host: str = WS_HOST, port: int = WS_PORT):
        self.brain = brain
        self.host, self.port = resolve_bind(host, port)
        self.clients: set[Any] = set()
        self.running = False
        self._server = None
        self._ping_task: asyncio.Task | None = None

    async def start(self) -> None:
        import websockets

        self.running = True
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            origins=list(WS_ALLOWED_ORIGINS),
        )
        self._ping_task = asyncio.create_task(self._ping_loop())
        logger.info("具身通道已打开 ws://%s:%s", self.host, self.port)
        # stop() 关闭 server 后这里返回，避免永久 Future 只能靠 cancel 收尾
        await self._server.wait_closed()

    async def stop(self) -> None:
        """关闭监听与已有连接；wait_closed 有超时，避免 Ctrl+C 卡死。"""
        self.running = False
        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        # 先关客户端，否则 wait_closed 会一直等卡在 LLM/收消息里的 handler
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.close(), timeout=1.0)
            except Exception:
                pass

        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=3.0)
            except TimeoutError:
                logger.warning(
                    "具身通道关闭超时（仍有 %d 个连接）",
                    len(self.clients),
                )
            self._server = None

    async def _ping_loop(self) -> None:
        while self.running:
            await asyncio.sleep(30)
            await self.broadcast({"type": "ping", "payload": {"ts": int(time.time() * 1000)}})

    async def _handler(self, websocket) -> None:
        self.clients.add(websocket)
        try:
            await websocket.send(
                json.dumps(self._state_packet(), ensure_ascii=False)
            )
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle_client_message(msg, websocket)
        except Exception:
            logger.debug("前端连接关闭", exc_info=True)
        finally:
            self.clients.discard(websocket)

    def _state_packet(self) -> dict:
        avatar = (
            self.brain.avatar.current_state.to_dict()
            if getattr(self.brain, "avatar", None)
            else {"posture": "idle", "expression": "neutral", "effect": "none"}
        )
        season = "spring"
        if getattr(self.brain, "relationship", None) is not None:
            season = self.brain.relationship.state.season
        mode = "awake"
        if hasattr(self.brain, "public_mode"):
            mode = self.brain.public_mode()
        elif getattr(self.brain, "emotion", None) is not None:
            mode = self.brain.emotion.mode.value
        stasis = bool(getattr(self.brain, "in_stasis", False))
        return {
            "type": "state",
            "payload": {
                "avatar_state": avatar,
                "season": season,
                "mode": mode,
                "stasis": stasis,
            },
        }

    async def _handle_client_message(self, msg: dict, websocket: Any = None) -> None:
        msg_type = msg.get("type")
        payload = msg.get("payload") or {}
        if msg_type == "user_message":
            text = (payload.get("text") or "").strip()
            if not text:
                return
            if getattr(self.brain, "in_stasis", False):
                await self.brain.receive_user_message(text)
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
            prev = bool(getattr(self.brain, "user_online", True))
            self.brain.user_online = online
            self.brain.perception.set_user_presence(online)
            # 广播给桌宠等旁听端；仅在状态变化时推，避免刷屏
            if online != prev:
                await self.broadcast(
                    {"type": "presence", "payload": {"online": online}}
                )
        elif msg_type == "pong":
            pass
        elif msg_type == "command":
            cmd = (payload.get("text") or "").strip()
            if cmd == "/state":
                e = self.brain.emotion
                mode = (
                    self.brain.public_mode()
                    if hasattr(self.brain, "public_mode")
                    else e.mode.value
                )
                # 刷新表情映射，供桌宠 / 壳同时读到
                if getattr(self.brain, "avatar", None) is not None:
                    season = "spring"
                    if getattr(self.brain, "relationship", None) is not None:
                        season = self.brain.relationship.state.season
                    self.brain.avatar.map_state(
                        e,
                        mode if mode != "stasis" else "solitary",
                        season=season,
                    )
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
                            "mode": mode,
                            "stasis": bool(getattr(self.brain, "in_stasis", False)),
                            "description": e.description(),
                            "stage": self.brain.relationship_stage,
                        },
                    }
                )
                await self.broadcast(self._state_packet())
            elif cmd == "/history":
                await self._send_history(websocket)
            elif cmd == "/journal":
                await self._send_journal(websocket)
            elif cmd == "/wake":
                result = await self.brain.resume_from_stasis()
                await self.broadcast(
                    {
                        "type": "wake_result",
                        "payload": result,
                    }
                )
                if result.get("ok"):
                    await self.broadcast(self._state_packet())

    async def _send_history(self, websocket: Any | None) -> None:
        """把最近 HISTORY_WINDOW 条对话 + 同窗创作卡推给请求方（本机单用户；无 websocket 则广播）。"""
        db = getattr(self.brain, "_db", None)
        rows: list[dict] = []
        if db is not None:
            try:
                rows = await db.load_messages(limit=HISTORY_WINDOW)
            except Exception:
                logger.exception("拉取对话历史失败")

        messages = []
        for r in rows:
            role = r.get("role")
            ui_role = "me" if role == "user" else "qi"
            ts_raw = str(r.get("timestamp") or "")
            at_ms = _iso_to_ms(ts_raw)
            if at_ms is None:
                at_ms = int(time.time() * 1000)
            text = (r.get("content") or "").strip()
            if not text:
                continue
            messages.append(
                {
                    "id": f"db-{r.get('id')}",
                    "role": ui_role,
                    "text": text,
                    "at": at_ms,
                    "tone": r.get("tone") or "",
                }
            )

        cards: list[dict] = []
        if db is not None:
            oldest = messages[0]["at"] if messages else None
            creations = await build_history_creation_cards(db, oldest_at_ms=oldest)
            explores = await build_history_explore_cards(db, oldest_at_ms=oldest)
            cards = sorted(
                [*creations, *explores],
                key=lambda c: int(c.get("at") or 0),
            )

        packet = {
            "type": "history",
            "payload": {"messages": messages, "cards": cards},
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 history 失败", exc_info=True)
        await self.broadcast(packet)

    async def _send_journal(self, websocket: Any | None) -> None:
        """把内在日记（独白/梦/第一次）推给请求方。"""
        db = getattr(self.brain, "_db", None)
        entries: list[dict] = []
        if db is not None:
            try:
                entries = await db.load_journal_entries(limit=80)
            except Exception:
                logger.exception("拉取内在日记失败")

        packet = {"type": "journal", "payload": {"entries": entries}}
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 journal 失败", exc_info=True)
        await self.broadcast(packet)

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

    async def notify_journal_entry(self, entry: dict) -> None:
        """实时推送单条内在日记（独白/梦/第一次）到前端。"""
        await self.broadcast({"type": "journal_entry", "payload": entry})

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
