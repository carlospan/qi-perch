"""Avatar 同步与消息递送——从 Brain 拆出的纯结构实现。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from qi.embodiment.voice.tts import emotion_to_voice_params

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.brain")


async def sync_avatar(
    brain: Brain, now: datetime | None = None, force: bool = False
) -> None:
    now = now or datetime.now()
    ui_mode = brain.public_mode()
    state = brain.avatar.map_state(
        brain.emotion,
        ui_mode if ui_mode != "stasis" else "solitary",
        season=brain._current_season(),
        now=now,
    )
    payload = state.to_dict()
    state_packet = {
        "avatar_state": payload,
        "season": brain._current_season(),
        "mode": ui_mode,
        "stasis": bool(getattr(brain, "in_stasis", False)),
    }
    if (
        not force
        and payload == brain._last_avatar_payload
        and getattr(brain, "_last_state_packet", None) == state_packet
    ):
        return
    brain._last_avatar_payload = payload
    brain._last_state_packet = state_packet
    if brain.embodiment is not None:
        await brain.embodiment.broadcast(
            {
                "type": "state",
                "payload": state_packet,
            }
        )


async def emit_speech(brain: Brain, text: str) -> None:
    if brain.embodiment is None:
        return
    await brain.embodiment.send_speech(
        text,
        brain.emotion.description(),
        tone=brain.emotion.mode.value,
    )
    if brain.tts is None:
        return
    try:
        import base64

        speed, pitch = emotion_to_voice_params(brain.emotion)
        audio = await brain.tts.speak(text, speed=speed, pitch=pitch)
        if audio:
            await brain.embodiment.send_audio(base64.b64encode(audio).decode("ascii"))
    except Exception:
        logger.exception("TTS 合成失败")


async def push_proactive_text(brain: Brain, text: str) -> None:
    await brain.proactive_queue.put(text)
    await brain._emit_speech(text)


async def deliver_qi_message(
    brain: Brain,
    response: str,
    now: datetime,
    *,
    proactive: bool = False,
) -> None:
    brain.avatar.set_talking(True)
    await brain._sync_avatar(now, force=True)
    if proactive:
        await brain._push_proactive_text(response)
    else:
        await brain._emit_speech(response)
    brain.avatar.set_talking(False)
    await brain._sync_avatar(now, force=True)

    if brain.memory is not None:
        brain.memory.on_qi_message(response)
    if brain._db is not None:
        await brain._db.save_message(
            "qi",
            response,
            emotion_context=brain.emotion.model_dump_json(),
        )


async def broadcast_journal_entries(brain: Brain) -> None:
    if brain.embodiment is None or brain.inner_life is None:
        return
    for entry in brain.inner_life.last_journal_entries:
        try:
            await brain.embodiment.notify_journal_entry(entry)
        except Exception:
            logger.debug("推送内在日记失败", exc_info=True)


async def notify_first_time(brain: Brain) -> None:
    if brain.embodiment is None or brain.first_times is None:
        return
    entry = brain.first_times.last_recorded
    if not entry or not str(entry.get("text") or "").strip():
        return
    brain.first_times.last_recorded = None
    try:
        await brain.embodiment.notify_journal_entry(entry)
    except Exception:
        logger.debug("推送第一次记忆失败", exc_info=True)


async def deliver_action_result(brain: Brain, result: dict, now: datetime) -> None:
    """行动结果：卡片推前端；share 的 qi_line 作为这一拍的开口（非主动言语通道）。"""
    if brain.embodiment is not None:
        try:
            await brain.embodiment.broadcast(
                {"type": "action", "payload": result}
            )
        except Exception:
            logger.exception("行动结果推送失败")

    # share 递出时说一句脆弱的话；tend/explore 默认向内不说
    if result.get("type") == "creation_card":
        line = (result.get("qi_line") or "").strip()
        content = str(result.get("content") or "").strip()
        # 作品正文必须跟着 qi_line 进对话流——前端无 creation_card handler，
        # 只发 qi_line 会让栖递了东西却谁都看不见，被问起只能现场虚构
        #（实证：22:52 递《凌晨五点》，23:16 被问时念了首现编的还说「放了好几天」）
        if line and content:
            await brain._deliver_qi_message(
                f"{line}\n\n{content}", now, proactive=True
            )
        elif line:
            await brain._deliver_qi_message(line, now, proactive=True)
    elif result.get("speak") and result.get("qi_line"):
        await brain._deliver_qi_message(
            str(result["qi_line"]), now, proactive=True
        )
