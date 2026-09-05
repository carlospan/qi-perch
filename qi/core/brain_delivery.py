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


async def emit_speech(brain: Brain, text: str, *, proactive: bool = False) -> None:
    if brain.embodiment is None:
        return
    await brain.embodiment.send_speech(
        text,
        brain.emotion.description(),
        tone=brain.emotion.mode.value,
        proactive=proactive,
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
    await brain._emit_speech(text, proactive=True)


async def deliver_qi_message(
    brain: Brain,
    response: str,
    now: datetime,
    *,
    proactive: bool = False,
    stream: object | None = None,
) -> None:
    brain.avatar.set_talking(True)
    await brain._sync_avatar(now, force=True)
    streamed = bool(stream is not None and getattr(stream, "live", False))
    if streamed:
        emotion = brain.emotion.description()
        tone = brain.emotion.mode.value
        await stream.finish(response, emotion, tone)  # type: ignore[union-attr]
        if brain.tts is not None and brain.embodiment is not None:
            try:
                import base64

                speed, pitch = emotion_to_voice_params(brain.emotion)
                audio = await brain.tts.speak(response, speed=speed, pitch=pitch)
                if audio:
                    await brain.embodiment.send_audio(
                        base64.b64encode(audio).decode("ascii")
                    )
            except Exception:
                logger.exception("TTS 合成失败")
    elif proactive:
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
            proactive=proactive,
        )
    if streamed:
        logger.debug("流式对话已 finish + 落记忆 len=%s", len(response or ""))


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
    """行动结果：creation_card / speak=True（含 look_glance、explore）先开口，再广播。"""
    # 1) 栖先开口——正文由前端卡片承载，不再内联进语音（W2 退役）
    if result.get("type") == "creation_card":
        line = (result.get("qi_line") or "").strip()
        if line:
            await brain._deliver_qi_message(line, now, proactive=True)
    elif result.get("speak") and result.get("qi_line"):
        await brain._deliver_qi_message(
            str(result["qi_line"]), now, proactive=True
        )

    # open 复述 / 确认：谈区正文已是完整问句，不叠 AssistConfirmCard
    if result.get("type") in ("assist_confirm_request", "open_recap") and (
        result.get("kind") in ("open", "disk", "write", "together")
        or result.get("type") == "open_recap"
    ):
        return

    # 2) 再广播——谈区时间线：栖那句 → 卡片
    if brain.embodiment is not None:
        try:
            await brain.embodiment.broadcast(
                {"type": "action", "payload": result}
            )
        except Exception:
            logger.exception("行动结果推送失败")
        rtype = result.get("type")
        if rtype in ("creation_card", "explore_drift"):
            try:
                await brain.embodiment.push_activity_glance()
            except Exception:
                logger.debug("行动后刷新动向失败", exc_info=True)
