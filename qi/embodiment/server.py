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
# 上翻加载更早：每页条数
HISTORY_PAGE = 50
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
        self._turn_task: asyncio.Task | None = None
        self._turn_user_text: str | None = None
        self._emotion_last_payload: dict | None = None
        self._emotion_push_task: asyncio.Task | None = None
        self._emotion_push_gen = 0

    def schedule_emotion_push(self) -> None:
        """心跳后调度：约 1s 合并；有可见变化才广播 emotion_update。"""
        if not self.running:
            return
        self._emotion_push_gen += 1
        gen = self._emotion_push_gen
        if self._emotion_push_task is not None and not self._emotion_push_task.done():
            self._emotion_push_task.cancel()

        async def _debounced() -> None:
            from qi.embodiment.emotion_push import (
                EMOTION_PUSH_DEBOUNCE_S,
                build_emotion_snapshot,
                emotion_snapshot_changed,
            )

            try:
                await asyncio.sleep(EMOTION_PUSH_DEBOUNCE_S)
            except asyncio.CancelledError:
                return
            if gen != self._emotion_push_gen or not self.running:
                return
            try:
                payload = build_emotion_snapshot(self.brain)
            except Exception:
                logger.debug("构建情绪快照失败", exc_info=True)
                return
            if not emotion_snapshot_changed(self._emotion_last_payload, payload):
                return
            self._emotion_last_payload = payload
            await self.send_emotion_update(payload)

        self._emotion_push_task = asyncio.create_task(
            _debounced(), name="qi_emotion_push"
        )

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

        if self._emotion_push_task is not None:
            self._emotion_push_task.cancel()
            try:
                await self._emotion_push_task
            except asyncio.CancelledError:
                pass
            self._emotion_push_task = None

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
            client_id = str(payload.get("client_id") or "").strip()
            if not text:
                return
            # P0 ACK：先回执「接到了」，再处理（满/忙仍先 ACK）
            await self.send_message_ack(client_id)
            await self._on_user_message(text)
        elif msg_type == "turn_control":
            action = str(payload.get("action") or "").strip().lower()
            if action in ("rephrase", "stop"):
                await self._interrupt_active_turn(action)  # type: ignore[arg-type]
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
                from qi.embodiment.emotion_push import build_emotion_snapshot

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
                payload = build_emotion_snapshot(self.brain)
                self._emotion_last_payload = payload
                await self.broadcast(
                    {
                        "type": "emotion_update",
                        "payload": payload,
                    }
                )
                await self.broadcast(self._state_packet())
            elif cmd == "/history":
                await self._send_history(websocket)
            elif cmd == "/history_before":
                raw_before = payload.get("before_id")
                try:
                    before_id = int(raw_before)
                except (TypeError, ValueError):
                    before_id = 0
                await self._send_history_before(websocket, before_id)
            elif cmd == "/journal":
                await self._send_journal(websocket)
            elif cmd == "/time_traces":
                await self._send_time_traces(websocket)
            elif cmd == "/review_memories":
                await self._send_review_memories(websocket)
            elif cmd == "/activity_glance":
                await self._send_activity_glance(websocket)
            elif cmd == "/settings_llm":
                await self._send_settings_llm(websocket)
            elif cmd == "/settings_llm_save":
                await self._save_settings_llm(websocket, payload)
            elif cmd == "/settings_llm_probe":
                await self._probe_settings_llm(websocket)
            elif cmd == "/open_data_dir":
                await self._open_data_dir(websocket)
            elif cmd == "/export_memory":
                await self._export_memory(websocket)
            elif cmd == "/wipe_memory":
                await self._wipe_memory(websocket)
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

    def _turn_in_flight(self) -> bool:
        return self._turn_task is not None and not self._turn_task.done()

    async def _on_user_message(self, text: str) -> None:
        if getattr(self.brain, "in_stasis", False):
            await self.brain.receive_user_message(text)
            return

        if self._turn_in_flight():
            from qi.core.turn_interrupt import classify_turn_interrupt

            kind = await classify_turn_interrupt(
                getattr(self.brain, "llm", None),
                text,
            )
            if kind in ("rephrase", "stop"):
                if self._turn_in_flight():
                    await self._interrupt_active_turn(kind)
                return
            from qi.embodiment.system_notice import notice_payload

            await self.send_system_notice(notice_payload("turn_busy"))
            return

        self._turn_user_text = text
        await self.send_typing()
        task = asyncio.create_task(
            self._run_user_turn(text),
            name="qi_user_turn",
        )
        self._turn_task = task

        def _done(t: asyncio.Task) -> None:
            if self._turn_task is t:
                self._turn_task = None
            try:
                t.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("用户轮次异常")

        task.add_done_callback(_done)
        # 不 await：让 WS 循环能收到打断 / 重说

    async def _run_user_turn(self, text: str) -> None:
        try:
            response = await self.brain.receive_user_message(text)
        except asyncio.CancelledError:
            raise
        notice = None
        if hasattr(self.brain, "take_pending_system_notice"):
            notice = self.brain.take_pending_system_notice()
        if notice:
            await self.send_system_notice(notice)
        elif not response:
            logger.debug("用户轮次无 speech 且无 system_notice")

    async def _interrupt_active_turn(self, action: str) -> None:
        """取消进行中轮次；广播 turn_interrupted + 短应。"""
        from qi.core.turn_interrupt import REPHRASE_ACK, STOP_ACK

        original = self._turn_user_text
        task = self._turn_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._turn_task = None
        stream = None
        if hasattr(self.brain, "on_turn_interrupted"):
            stream = self.brain.on_turn_interrupted()
        if stream is not None:
            try:
                await stream.retract()
            except Exception:
                logger.debug("打断收回流式气泡失败", exc_info=True)

        await self.broadcast(
            {
                "type": "turn_interrupted",
                "payload": {
                    "action": action,
                    "original_text": original or "",
                    "prefill": (original or "") if action == "rephrase" else "",
                },
            }
        )
        ack = REPHRASE_ACK if action == "rephrase" else STOP_ACK
        emotion = ""
        if getattr(self.brain, "emotion", None) is not None:
            emotion = self.brain.emotion.description()
        await self.send_speech(ack, emotion=emotion, tone="quiet")
        self._turn_user_text = None

    def _format_history_messages(self, rows: list[dict]) -> list[dict]:
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
        return messages

    async def _send_history(self, websocket: Any | None) -> None:
        """把最近 HISTORY_WINDOW 条对话 + 同窗创作卡推给请求方（本机单用户；无 websocket 则广播）。"""
        db = getattr(self.brain, "_db", None)
        rows: list[dict] = []
        if db is not None:
            try:
                rows = await db.load_messages(limit=HISTORY_WINDOW)
            except Exception:
                logger.exception("拉取对话历史失败")

        messages = self._format_history_messages(rows)

        cards: list[dict] = []
        if db is not None:
            # 创作/见闻按条数上限回灌；勿用对话 oldest 裁剪，否则「回顾」会变空
            creations = await build_history_creation_cards(db, oldest_at_ms=None)
            explores = await build_history_explore_cards(db, oldest_at_ms=None)
            cards = sorted(
                [*creations, *explores],
                key=lambda c: int(c.get("at") or 0),
            )

        packet = {
            "type": "history",
            "payload": {
                "messages": messages,
                "cards": cards,
                "has_more": len(rows) >= HISTORY_WINDOW,
            },
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 history 失败", exc_info=True)
        await self.broadcast(packet)

    async def _send_history_before(
        self, websocket: Any | None, before_id: int
    ) -> None:
        """上翻：before_id 之前最多 HISTORY_PAGE 条文本（无卡片）。"""
        db = getattr(self.brain, "_db", None)
        rows: list[dict] = []
        if db is not None and before_id > 0:
            try:
                rows = await db.load_messages_before(before_id, limit=HISTORY_PAGE)
            except Exception:
                logger.exception("拉取更早对话失败")

        messages = self._format_history_messages(rows)
        packet = {
            "type": "history_page",
            "payload": {
                "messages": messages,
                "has_more": len(rows) >= HISTORY_PAGE,
                "before_id": before_id,
            },
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 history_page 失败", exc_info=True)
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

    async def _send_time_traces(self, websocket: Any | None) -> None:
        """方向 D：时间的痕迹旁白（真统计；非 speech）。"""
        from qi.embodiment.time_traces import (
            format_time_trace_line,
            gather_time_trace_stats,
        )

        db = getattr(self.brain, "_db", None)
        stats = {"remembered": 0, "fading": 0, "days_known": 1}
        try:
            stats = await gather_time_trace_stats(db)
        except Exception:
            logger.exception("拉取时间痕迹失败")

        line = format_time_trace_line(stats)
        packet = {
            "type": "time_traces",
            "payload": {
                "line": line,
                "remembered": stats["remembered"],
                "fading": stats["fading"],
                "days_known": stats["days_known"],
            },
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 time_traces 失败", exc_info=True)
        await self.broadcast(packet)

    async def _send_review_memories(self, websocket: Any | None) -> None:
        """方向 D：回顾页记忆列表（真 strength；非 speech）。"""
        from qi.embodiment.memory_fade import gather_review_memories

        db = getattr(self.brain, "_db", None)
        items: list[dict] = []
        try:
            items = await gather_review_memories(db)
        except Exception:
            logger.exception("拉取回顾记忆失败")

        packet = {"type": "review_memories", "payload": {"items": items}}
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 review_memories 失败", exc_info=True)
        await self.broadcast(packet)

    async def _send_activity_glance(self, websocket: Any | None) -> None:
        """方向 D：存在页一行动向旁白。"""
        packet = await self._activity_glance_packet()
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 activity_glance 失败", exc_info=True)
        await self.broadcast(packet)

    async def _activity_glance_packet(self) -> dict:
        from qi.embodiment.activity_glance import (
            activity_glance_payload,
            gather_activity_glance,
        )

        db = (
            getattr(self.brain, "_db", None)
            if self.brain is not None
            else None
        )
        item = None
        try:
            item = await gather_activity_glance(db)
        except Exception:
            logger.exception("拉取动向旁白失败")
        return {
            "type": "activity_glance",
            "payload": activity_glance_payload(item),
        }

    async def push_activity_glance(self) -> None:
        """有新日记/创作/见闻后刷新动向旁白（可空 line）。"""
        await self.broadcast(await self._activity_glance_packet())

    async def _send_settings_llm(self, websocket: Any | None) -> None:
        from qi.config.secrets import settings_llm_snapshot
        from qi.paths import resolve_data_root

        snap = settings_llm_snapshot()
        snap["data_dir"] = str(resolve_data_root())
        packet = {
            "type": "settings_llm",
            "payload": snap,
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 settings_llm 失败", exc_info=True)
        await self.broadcast(packet)

    async def _open_data_dir(self, websocket: Any | None) -> None:
        from qi.paths import open_data_folder, resolve_data_root

        ok, detail = open_data_folder()
        packet = {
            "type": "open_data_dir_result",
            "payload": {
                "ok": ok,
                "path": str(resolve_data_root()),
                "message": None if ok else detail,
            },
        }
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 open_data_dir_result 失败", exc_info=True)
        await self.broadcast(packet)

    async def _reply_settings_op(
        self, websocket: Any | None, msg_type: str, payload: dict
    ) -> None:
        packet = {"type": msg_type, "payload": payload}
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 %s 失败", msg_type, exc_info=True)
        await self.broadcast(packet)

    async def _export_memory(self, websocket: Any | None) -> None:
        from qi.data_lifecycle import backups_dir, export_memory_backup

        try:
            ok, message, zip_path = await asyncio.to_thread(
                export_memory_backup, open_folder=True
            )
        except Exception as e:
            logger.exception("导出记忆失败")
            await self._reply_settings_op(
                websocket,
                "export_memory_result",
                {"ok": False, "message": f"导出失败：{e}"},
            )
            return
        await self._reply_settings_op(
            websocket,
            "export_memory_result",
            {
                "ok": ok,
                "message": message if not ok else "已导出到 backups 文件夹",
                "path": str(zip_path) if zip_path else None,
                "backups_dir": str(backups_dir()),
            },
        )

    async def _wipe_memory(self, websocket: Any | None) -> None:
        """关闭句柄 → 删记忆文件 → 重建空库并刷新前端。"""
        from qi.core.emotion import EmotionState
        from qi.data_lifecycle import wipe_memory_artifacts
        from qi.storage.database import Database

        if self._turn_in_flight():
            try:
                await self._interrupt_active_turn("stop")
            except Exception:
                logger.debug("清空记忆前打断本轮失败", exc_info=True)

        try:
            mm = getattr(self.brain, "memory", None)
            vs = getattr(mm, "vector_store", None) if mm is not None else None
            if vs is not None and hasattr(vs, "close"):
                try:
                    vs.close()
                except Exception:
                    logger.debug("关闭向量库失败", exc_info=True)

            db = getattr(self.brain, "_db", None)
            if db is not None:
                await db.close()

            ok, detail = await asyncio.to_thread(wipe_memory_artifacts)
            if not ok:
                await self._reply_settings_op(
                    websocket,
                    "wipe_memory_result",
                    {"ok": False, "message": detail},
                )
                return

            db_path = (self.brain.config.get("database") or {}).get("path")
            if not db_path:
                from qi.paths import under_data

                db_path = str(under_data("qi.db"))
            new_db = Database(str(db_path))
            await new_db.initialize()

            self.brain.emotion = EmotionState()
            self.brain._prev_valence = self.brain.emotion.valence
            self.brain._pending_queue.clear()
            self.brain._pending_speech = None
            self.brain._last_response = None
            self.brain.last_user_message = None
            if hasattr(self.brain, "session"):
                # 清会话侧请求，避免旧确认卡挂住
                try:
                    self.brain.session.last_assist_request = None
                    self.brain.session.pending_assist_confirmation = None
                except Exception:
                    pass

            await self.brain.restore_state(new_db)

            await self._reply_settings_op(
                websocket,
                "wipe_memory_result",
                {"ok": True, "message": "记忆已清空。钥匙还在。"},
            )
            await self.broadcast(self._state_packet())
            await self._send_history(None)
            await self.push_activity_glance()
            try:
                await self._send_time_traces(None)
            except Exception:
                logger.debug("清空后刷新时间痕迹失败", exc_info=True)
            try:
                await self._send_review_memories(None)
            except Exception:
                logger.debug("清空后刷新回顾记忆失败", exc_info=True)
        except Exception as e:
            logger.exception("清空记忆失败")
            await self._reply_settings_op(
                websocket,
                "wipe_memory_result",
                {"ok": False, "message": f"清空失败：{e}"},
            )

    async def _save_settings_llm(self, websocket: Any | None, payload: dict) -> None:
        from qi.config.secrets import (
            apply_secrets_to_environ,
            settings_llm_snapshot,
            write_secrets_file,
        )

        api_key = payload.get("api_key")
        base_url = payload.get("base_url")
        model = payload.get("model")
        # 未传字段 = 不改；传空串 = 清除（可选字段）或拒绝清空 key
        try:
            kwargs: dict = {}
            if "api_key" in payload:
                kwargs["api_key"] = str(api_key or "")
            if "base_url" in payload:
                kwargs["base_url"] = str(base_url or "")
            if "model" in payload:
                kwargs["model"] = str(model or "")
            if kwargs:
                write_secrets_file(**kwargs)
                apply_secrets_to_environ()
            result = {"ok": True, **settings_llm_snapshot()}
            from qi.paths import resolve_data_root

            result["data_dir"] = str(resolve_data_root())
            if hasattr(self.brain, "reload_llm_settings"):
                reloaded = self.brain.reload_llm_settings()
                result["ok"] = bool(reloaded.get("ok", True))
                if reloaded.get("error"):
                    result["error"] = str(reloaded["error"])
                result.update(
                    {
                        k: reloaded[k]
                        for k in ("has_key", "api_key_masked", "base_url", "model")
                        if k in reloaded
                    }
                )
        except Exception as e:
            logger.exception("保存 LLM 设置失败")
            result = {
                "ok": False,
                "error": str(e),
                **settings_llm_snapshot(),
            }

        packet = {"type": "settings_llm_saved", "payload": result}
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 settings_llm_saved 失败", exc_info=True)
                await self.broadcast(packet)

    async def _probe_settings_llm(self, websocket: Any | None) -> None:
        """设置页试连通：不入谈区/历史/记忆；结果只回 settings_llm_probe。"""
        from qi.config.llm_probe import run_settings_llm_probe

        try:
            result = await run_settings_llm_probe(getattr(self.brain, "llm", None))
        except Exception:
            logger.exception("设置页试连通异常")
            from qi.config.llm_probe import probe_result_payload

            result = probe_result_payload(kind="unreachable")

        packet = {"type": "settings_llm_probe", "payload": result}
        raw = json.dumps(packet, ensure_ascii=False)
        if websocket is not None:
            try:
                await websocket.send(raw)
                return
            except Exception:
                logger.debug("向请求方发送 settings_llm_probe 失败", exc_info=True)
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
        try:
            await self.push_activity_glance()
        except Exception:
            logger.debug("日记后刷新动向失败", exc_info=True)

    async def send_state_change(self, avatar_state: dict) -> None:
        await self.broadcast({"type": "state", "payload": {"avatar_state": avatar_state}})

    async def send_typing(self) -> None:
        await self.broadcast({"type": "typing", "payload": {}})

    async def send_message_ack(self, client_id: str) -> None:
        """发送回执：客户端 client_id 原样带回（可空，仍发 type 便于探测）。"""
        await self.broadcast(
            {
                "type": "message_ack",
                "payload": {"client_id": client_id or ""},
            }
        )

    async def send_system_notice(self, payload: dict) -> None:
        """系统态提示（失败可见）；非栖的 speech。"""
        await self.broadcast({"type": "system_notice", "payload": payload})

    async def send_emotion_update(self, snapshot: dict) -> None:
        await self.broadcast({"type": "emotion_update", "payload": snapshot})

    async def send_audio(self, audio_b64: str, mime: str = "audio/mpeg") -> None:
        await self.broadcast(
            {"type": "audio", "payload": {"data": audio_b64, "mime": mime}}
        )
