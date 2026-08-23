"""L7 响应式世界触达路由。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.brain import Brain

logger = logging.getLogger("qi.dialogue_router")

FALLTHROUGH = object()


async def try_responsive_world_reach(
    brain: Brain, text: str
) -> str | None | object:
    """尝试 L7 响应式路由；FALLTHROUGH 表示应入 pending 对话队列。"""
    if brain.pending_assist_confirmation is not None:
        if brain._is_reject_cue(text):
            brain._clear_pending_assist()
            brain._clear_assist_target()
            now = datetime.now()
            await brain._deliver_qi_message("好。", now, proactive=False)
            return "好。"
        sel = brain._pending_selected_index(text)
        if brain._is_confirm_cue(text) or sel is not None:
            confirmed_req = brain.pending_assist_confirmation
            brain._clear_pending_assist()
            try:
                if brain._is_open_pending(confirmed_req):
                    brain._clear_assist_target()
                    # allow 要约尚未填候选：先找路径再二次确认，勿直接写白名单
                    conf = True
                    try:
                        from qi.action.open import OpenRequest

                        if (
                            isinstance(confirmed_req, OpenRequest)
                            and confirmed_req.intent
                            in ("allow", "teach")
                            and not confirmed_req.candidates
                        ):
                            conf = False
                    except Exception:
                        pass
                    result = await brain._execute_open_on_request(
                        confirmed_req,
                        confirmed=conf,
                        selected_index=sel,
                    )
                    if result is not None and (
                        result.get("needs_confirmation")
                        or result.get("outcome") == "confirm_required"
                    ):
                        brain.pending_assist_confirmation = confirmed_req
                        brain.pending_assist_confirmation_at = (
                            datetime.now()
                        )
                        brain.pending_assist_heartbeats = 0
                    elif result is not None:
                        from qi.action.judgment import OUTCOME_RECAP
                        from qi.action.open import OpenRequest

                        if (
                            result.get("outcome") == OUTCOME_RECAP
                            or result.get("type") == "open_recap"
                        ):
                            alias = str(
                                result.get("allow_alias")
                                or getattr(confirmed_req, "target", "")
                            )
                            cands = result.get("candidates") or getattr(
                                confirmed_req, "candidates", None
                            ) or []
                            brain.pending_assist_confirmation = OpenRequest(
                                intent="allow",
                                target_type="app",
                                target=alias,
                                candidates=cands,
                            )
                            brain.pending_assist_confirmation_at = (
                                datetime.now()
                            )
                            brain.pending_assist_heartbeats = 0
                        else:
                            brain._arm_open_after_allow(result)
                elif brain._is_disk_pending(confirmed_req):
                    brain._clear_assist_target()
                    disk_payload = confirmed_req
                    try:
                        from qi.action.disk import DiskRequest, allowed_root

                        if (
                            isinstance(confirmed_req, DiskRequest)
                            and confirmed_req.intent == "offer_list"
                        ):
                            disk_payload = DiskRequest(
                                intent="list_dir",
                                path=confirmed_req.path
                                or str(allowed_root()),
                            )
                    except Exception:
                        pass
                    result = await brain._execute_disk_on_request(
                        disk_payload, confirmed=True
                    )
                    brain._remember_disk_listing(result)
                elif brain._is_write_pending(confirmed_req):
                    brain._clear_assist_target()
                    result = await brain._execute_write_on_request(
                        confirmed_req, confirmed=True
                    )
                    if result and result.get("outcome") == "success":
                        brain.write_desire = None
                elif brain._is_together_pending(confirmed_req):
                    brain._clear_assist_target()
                    result = await brain._execute_together_on_request(
                        confirmed_req, confirmed=True
                    )
                    brain._ingest_together_pool(result)
                else:
                    # assist-5：确认成功后保留 last_assist_target（粘性补执行）
                    result = await brain._execute_confirmed_assist(
                        confirmed_req
                    )
                if result is not None:
                    await brain._deliver_action_result(
                        result, datetime.now()
                    )
                    return (result.get("qi_line") or "").strip() or None
            except Exception:
                logger.exception("confirmed execute 失败")
            return None
        # 换话题 / 新请求：清旧 pending + 粘性 target，落入正常对话
        brain._clear_pending_assist()
        brain._clear_assist_target()

    # assist-5：pending 已消费但用户仍短语确认——粘性目标补执行
    if brain.last_assist_target is not None and brain._is_confirm_reexec_cue(
        text
    ):
        now = datetime.now()
        if brain._assist_target_fresh(now):
            from qi.action.volition import AssistRequest

            target = brain.last_assist_target
            brain._clear_assist_target()
            result = await brain._execute_assist_on_request(
                AssistRequest(op="read_file", target_path=target),
                confirmed_override=True,
            )
            if result is not None:
                await brain._deliver_action_result(
                    result, datetime.now()
                )
                return (result.get("qi_line") or "").strip() or None
        await brain._deliver_qi_message(
            "嗯？你想让我看什么？", datetime.now(), proactive=False
        )
        return "嗯？你想让我看什么？"

    # look：叫停 / 解除 / 邀看（先于 assist；邀看不弹确认卡）
    try:
        from qi.action.look import (
            detect_look_invite,
            looks_like_look_pause,
            looks_like_look_resume,
        )
    except Exception:
        detect_look_invite = None  # type: ignore[assignment]
        looks_like_look_pause = None  # type: ignore[assignment]
        looks_like_look_resume = None  # type: ignore[assignment]

    if (
        looks_like_look_pause is not None
        and looks_like_look_pause(text)
        and brain.action is not None
    ):
        try:
            await brain.action.look.set_pause(datetime.now())
            await brain._deliver_qi_message(
                "好，我先不看了。", datetime.now(), proactive=False
            )
            return "好，我先不看了。"
        except Exception:
            logger.exception("look pause 失败")

    if (
        looks_like_look_resume is not None
        and looks_like_look_resume(text)
        and brain.action is not None
    ):
        try:
            await brain.action.look.clear_pause()
        except Exception:
            logger.debug("look resume 失败", exc_info=True)

    # 不可逆对外动作：诚实说明尚未实现
    try:
        from qi.action.irreversible import try_irreversible_message

        ir_line = await try_irreversible_message(brain, text, datetime.now())
        if ir_line is not None:
            return ir_line
    except Exception:
        logger.exception("irreversible 对话拍失败")

    # 委托式联网检索（先于 together/open，与自主 explore 分轨）
    try:
        from qi.core import brain_judgment as bj

        ds_reply = await bj.try_delegate_search_message(
            brain, text, datetime.now()
        )
        if ds_reply is not None:
            return ds_reply
    except Exception:
        logger.exception("delegate_search 对话拍失败")

    # together：同看（先于 open，避免「一起看 url」被纯打开抢走）
    tog_req = None
    if brain.action is not None:
        try:
            from qi.action.together import detect_together_intent

            tog_req = await detect_together_intent(
                text, pool=brain.together_pool, llm=brain.llm
            )
        except Exception:
            logger.debug("together intent 判别失败", exc_info=True)
            tog_req = None
    if tog_req is not None:
        try:
            now = datetime.now()
            blocked = await brain._gate_responsive(
                "together",
                text,
                {"request_obj": tog_req},
                now=now,
            )
            if blocked is not None:
                return blocked
            result = await brain._execute_together_on_request(
                tog_req, confirmed=True
            )
            if result is not None:
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("together 对话拍 execute 失败")
        return None

    # write（D: 约定路径写下）：先于 disk
    write_req = None
    if brain.action is not None:
        try:
            from qi.action.write import (
                WriteRequest,
                detect_write_intent,
                extract_win_path,
            )

            write_req = await detect_write_intent(text, llm=brain.llm)
            # 无路径欲望粘性：用户补路径 → 接上 diary/write/allow
            if write_req is None and brain._write_desire_fresh():
                path = extract_win_path(text)
                if path:
                    desire = brain.write_desire or {}
                    intent = str(desire.get("intent") or "write")
                    topic = str(desire.get("topic") or text)
                    if intent == "diary":
                        write_req = WriteRequest(
                            intent="diary",
                            path=path,
                            topic=topic,
                        )
                    else:
                        write_req = WriteRequest(
                            intent="write",
                            path=path,
                            topic=topic,
                            create_new=True,
                        )
            elif (
                write_req is not None
                and write_req.intent in ("ask_where",)
                and brain._write_desire_fresh()
            ):
                pass
        except Exception:
            logger.debug("write intent 判别失败", exc_info=True)
            write_req = None
    if write_req is not None:
        try:
            now = datetime.now()
            blocked = await brain._gate_responsive(
                "write",
                text,
                {"request_obj": write_req},
                now=now,
            )
            if blocked is not None:
                return blocked
            result = await brain._execute_write_on_request(
                write_req, confirmed=True
            )
            if result is not None:
                brain._remember_write_desire(result)
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("write 对话拍 execute 失败")
        return None

    # disk（D: 列目录 / 开本地文件）：先于 open，避免「打开 D:\a.txt」误进应用 open
    disk_req = None
    if brain.action is not None:
        try:
            from qi.action.disk import (
                answer_listing_question,
                detect_disk_intent,
                resolve_listing_followup,
            )

            if brain._disk_listing_fresh():
                ans = answer_listing_question(text, brain.last_disk_listing)
                if ans:
                    now = datetime.now()
                    await brain._deliver_qi_message(ans, now, proactive=False)
                    return ans
                disk_req = resolve_listing_followup(
                    text, brain.last_disk_listing
                )
            if disk_req is None:
                disk_req = await detect_disk_intent(text, llm=brain.llm)
        except Exception:
            logger.debug("disk intent 判别失败", exc_info=True)
            disk_req = None
    if disk_req is not None:
        try:
            now = datetime.now()
            blocked = await brain._gate_responsive(
                "disk",
                text,
                {"request_obj": disk_req},
                now=now,
            )
            if blocked is not None:
                return blocked
            result = await brain._execute_disk_on_request(
                disk_req, confirmed=True
            )
            if result is not None:
                brain._remember_disk_listing(result)
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("disk 对话拍 execute 失败")
        return None

    # open：先于 look 邀看（「看看这个链接」走 open_and_look，不误成纯 look）
    open_req = None
    if brain.action is not None:
        try:
            from qi.action.open import detect_open_intent

            open_req = await detect_open_intent(text, llm=brain.llm)
        except Exception:
            logger.debug("open intent 判别失败", exc_info=True)
            open_req = None
    if open_req is not None:
        try:
            from qi.action.judgment import OUTCOME_RECAP
            from qi.action.open import OpenRequest

            now = datetime.now()
            kind = "allow" if open_req.intent in ("allow", "teach") else "open"
            blocked = await brain._gate_responsive(
                kind,
                text,
                {"request_obj": open_req},
                now=now,
            )
            if blocked is not None:
                return blocked
            result = await brain._execute_open_on_request(
                open_req,
                confirmed=open_req.intent not in ("allow", "teach"),
            )
            if result is not None:
                if result.get("outcome") == OUTCOME_RECAP or (
                    result.get("type") == "open_recap"
                ):
                    alias = str(
                        result.get("allow_alias")
                        or getattr(open_req, "target", "")
                    )
                    cands = result.get("candidates") or []
                    brain.pending_assist_confirmation = OpenRequest(
                        intent="allow",
                        target_type="app",
                        target=alias,
                        candidates=cands,
                    )
                    brain.pending_assist_confirmation_at = now
                    brain.pending_assist_heartbeats = 0
                    brain._clear_assist_target()
                else:
                    brain._arm_open_after_allow(result)
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("open 对话拍 execute 失败")
        return None

    look_invited = False
    if detect_look_invite is not None and brain.action is not None:
        try:
            look_invited = await detect_look_invite(text, llm=brain.llm)
        except Exception:
            logger.debug("look invite 判别失败", exc_info=True)
            look_invited = False
    if look_invited:
        try:
            now = datetime.now()
            scars = (
                await brain._db.list_scars()
                if brain._db is not None
                else None
            )
            trust = 0.5
            if brain.relationship is not None:
                trust = float(
                    getattr(brain.relationship.state, "trust", 0.5) or 0.5
                )
            result = await brain.action.execute_kind(
                "look",
                brain.emotion,
                brain.relationship_stage,
                brain._current_season(),
                now,
                mode=brain.emotion.mode.value,
                user_online=brain.user_online,
                scars=scars,
                trust=trust,
                op="invite",
                target_path=text,
                confirmed=True,
            )
            if result is not None:
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("look 邀看 execute 失败")
        return None

    # assist-4：对话拍有 assist 请求时，assist 开口 = respond（不走 conversation LLM）
    assist_req = None
    try:
        from qi.action.volition import parse_assist_request

        assist_req = parse_assist_request(text)
    except Exception:
        logger.debug("assist_request 解析失败", exc_info=True)
        assist_req = None
    brain.last_assist_request = assist_req
    if assist_req is not None:
        brain.last_assist_target = getattr(
            assist_req, "target_path", None
        )
        brain.last_assist_target_at = datetime.now()

    if assist_req is not None:
        try:
            now = datetime.now()
            blocked = await brain._gate_responsive(
                "assist",
                text,
                {
                    "op": assist_req.op,
                    "target_path": assist_req.target_path,
                },
                now=now,
            )
            if blocked is not None:
                return blocked
            result = await brain._execute_assist_on_request(assist_req)
            if result is not None:
                brain.last_assist_request = None
                await brain._deliver_action_result(result, now)
                return (result.get("qi_line") or "").strip() or None
        except Exception:
            logger.exception("assist 对话拍 execute 失败")
        return None

    return FALLTHROUGH
