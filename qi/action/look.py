"""L7 look——瞥一眼前台窗口（截图 → 视觉印象）。"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from qi.action.permission import (
    OUTCOME_FAILED_CAPABILITY,
    OUTCOME_SUCCESS,
    can_look,
)

if TYPE_CHECKING:
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.action.look")

LOOK_PAUSE_UNTIL_KEY = "look_pause_until"
LOOK_LAST_KEY = "look_last"
LOOK_SOFT_BLOCK_KEY = "look_soft_block_count"
LOOK_FIRST_NOTICE_KEY = "look_first_notice_done"

FALLBACK_QI_LINE = "我看了一眼……"
# 首次告知由代码拼接，不交给模型自由发挥（防污染印象句）
FIRST_NOTICE_LINE = "我偶尔会瞥一眼你那边的屏幕，只当现场，不会存档。……"

_SELF_TITLE_MARKERS = (
    "栖",
    "qi-perch",
    "Qi Perch",
    "黄昏的枝",
)

_LOOK_SYSTEM = (
    "你在帮栖记下刚才瞥到的画面（给她随后开口用的材料，不是台词）。"
    "用一两句中文写清瞥到了什么轮廓（光暗、布局、在忙的事的样子），"
    "可带直观感受用词，但不要编造没看见的，不要念窗口标题或进程名，"
    "不要提截图/模型/技术细节，不要写成对用户说的完整台词。"
)


def _look_cfg(config: dict | None) -> dict:
    raw = ((config or {}).get("action") or {}).get("look") or {}
    return raw if isinstance(raw, dict) else {}


def pause_hours(config: dict | None) -> float:
    return float(_look_cfg(config).get("pause_hours", 1.0))


def min_interval_minutes(config: dict | None) -> float:
    return float(_look_cfg(config).get("min_interval_minutes", 30.0))


def chat_grace_minutes(config: dict | None) -> float:
    """刚聊完不久不自主瞥，避免开发/连发时连瞥。"""
    return float(_look_cfg(config).get("chat_grace_minutes", 5.0))


def silence_boost_minutes(config: dict | None) -> float:
    return float(_look_cfg(config).get("silence_boost_minutes", 20.0))


def _look_invite_negative(text: str) -> bool:
    """明确不是邀看（误触）。"""
    if re.search(r"记得我.*做|帮我看看这(个|段)?(文件|代码)|你觉得我该做什么", text):
        return True
    if text in ("你在干嘛", "在吗", "忙什么呢") or re.fullmatch(
        r"(你在干嘛|在吗|忙什么呢)[？?！!。.…]*", text
    ):
        return True
    # 「帮我看看这段/这个」偏文件协助，且带扩展名或路径味
    if re.search(r"帮我看(看|一下|下).{0,12}(文件|代码|\.txt|\.py|\.md|/|\\)", text):
        return True
    return False


def _look_invite_strong(text: str) -> bool:
    """
    组合启发式：抓「请你看见我这边/我在做什么」的意图，不靠整句死记。
    """
    # 你能/会/可以 + 看(到|见|…) + 我 + (在)做/干什么…
    if re.search(
        r"你(能|会|可以)?看(到|见|得见|得到)?我.{0,8}"
        r"(现在|正在)?(在)?(做(什么|甚么)|干什么|干嘛|做啥)",
        text,
    ):
        return True
    # 你知道我在做什么 / 正在做什么
    if re.search(
        r"你知道我.{0,6}(现在|正在)?(在)?(做(什么|甚么)|干什么|干嘛)",
        text,
    ):
        return True
    # 看(看|一眼)我(的)?屏幕 / 我屏幕上…
    if re.search(r"(看(看|一眼)?我(的)?屏幕|我(的)?屏幕上|屏幕上是什么)", text):
        return True
    # 看得见/看得到 + 这边/我这边
    if re.search(r"看(得见|得到|见).{0,4}(这边|我这边|我这儿)", text):
        return True
    # 猜猜我在干…
    if re.search(r"猜猜我.{0,4}(在)?(干(什么|嘛|啥)|做(什么|啥))", text):
        return True
    # 帮我看下这页/这局（口语邀看，非读文件）
    if re.search(r"帮我看(一下|下|看)?.{0,6}(这(个)?页面|这局|游戏画面)", text):
        return True
    # 瞥一眼 / 看一眼我在…
    if re.search(r"(瞥|看)一眼我.{0,6}(在)?(干|做)", text):
        return True
    return False


def _look_invite_weak_candidate(text: str) -> bool:
    """弱信号：可能邀看，交给 LLM 判别；避免每句都调模型。"""
    if len(text) > 80:
        return False
    has_see = bool(
        re.search(r"看(到|见|得见|得到|一眼|看)?|屏幕|画面|瞥", text)
    )
    has_me_side = bool(re.search(r"我|这边|屏幕|正在做|在做|干嘛|干什么", text))
    has_ask = bool(re.search(r"你|能|吗|么|？|\?", text))
    return has_see and has_me_side and has_ask


def looks_like_look_invite(message: str | None) -> bool:
    """同步强判定（测试/无 LLM）；弱候选不在此放行。"""
    text = (message or "").strip()
    if not text or _look_invite_negative(text):
        return False
    return _look_invite_strong(text)


async def _llm_look_invite(llm: Any, text: str) -> bool:
    prompt = (
        "判断用户是否在邀请对方「看一眼自己的屏幕 / 正在做什么」。\n"
        "只回答 yes 或 no。\n"
        "算邀请：问你能不能看见、看不看得到他在干什么、看看屏幕、猜猜他在干嘛。\n"
        "不算：闲聊「你在干嘛」、读某个文件/代码、回忆过去、商量该做什么。\n"
        f"用户：「{text}」"
    )
    try:
        raw = (await llm.call("fact", [{"role": "user", "content": prompt}], temperature=0.0) or "").strip().lower()
    except Exception:
        logger.debug("look invite LLM 判别失败", exc_info=True)
        return False
    if raw.startswith("yes") or raw.startswith("y") or "yes" in raw[:8]:
        return True
    if raw.startswith("是") or raw[:2] in ("邀请", "算"):
        return True
    return False


async def detect_look_invite(
    message: str | None,
    *,
    llm: Any | None = None,
) -> bool:
    """
    邀看意图：强启发式优先；弱候选在有 llm 时再判别。
    """
    text = (message or "").strip()
    if not text or _look_invite_negative(text):
        return False
    if _look_invite_strong(text):
        return True
    if llm is not None and _look_invite_weak_candidate(text):
        return await _llm_look_invite(llm, text)
    return False


def looks_like_look_pause(message: str | None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    cues = ("别看", "不要看屏", "别看我屏幕", "不要看我屏幕", "不许看屏", "闭眼")
    return any(c in text for c in cues)


def looks_like_look_resume(message: str | None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    cues = ("可以看了", "睁眼", "你可以看了", "准你看了")
    return any(c in text for c in cues)


def _resize_png_bytes(raw: bytes, max_side: int = 1280) -> bytes:
    from PIL import Image

    im = Image.open(io.BytesIO(raw))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side) / float(max(w, h) or 1))
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    if im.mode == "RGBA":
        im = im.convert("RGB")
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=75)
    return out.getvalue()


def capture_foreground_image(
    *,
    is_self_window: Callable[[str], bool] | None = None,
) -> tuple[bytes | None, str, bool]:
    """
    返回 (jpeg_bytes, title, is_self)。
    非 Windows 或失败 → (None, "", False)。
    """
    if sys.platform != "win32":
        return None, "", False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hwnd = user32.GetForegroundWindow()
        title = ""
        if hwnd:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 2)
            user32.GetWindowTextW(hwnd, buf, n + 2)
            title = buf.value or ""

        self_hit = False
        check = is_self_window or (
            lambda t: any(m.lower() in (t or "").lower() for m in _SELF_TITLE_MARKERS)
        )
        if title and check(title):
            self_hit = True

        # 前台窗客户区；失败则虚拟屏
        left = top = right = bottom = 0
        used_window = False
        if hwnd:
            rect = wintypes.RECT()
            if user32.GetClientRect(hwnd, ctypes.byref(rect)):
                pt = wintypes.POINT(0, 0)
                user32.ClientToScreen(hwnd, ctypes.byref(pt))
                left, top = int(pt.x), int(pt.y)
                right = left + int(rect.right)
                bottom = top + int(rect.bottom)
                if right > left and bottom > top:
                    used_window = True
        if not used_window:
            left = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
            top = int(user32.GetSystemMetrics(77))
            right = left + int(user32.GetSystemMetrics(78))
            bottom = top + int(user32.GetSystemMetrics(79))

        width, height = max(1, right - left), max(1, bottom - top)
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        gdi32.SelectObject(hdc_mem, hbmp)
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = width
        bmi.biHeight = -height
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        buf_len = width * height * 4
        raw = (ctypes.c_char * buf_len)()
        gdi32.GetDIBits(hdc_screen, hbmp, 0, height, raw, ctypes.byref(bmi), 0)

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        from PIL import Image

        im = Image.frombuffer("RGB", (width, height), bytes(raw), "raw", "BGRX", 0, 1)
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=75)
        data = _resize_png_bytes(out.getvalue())
        return data, title, self_hit
    except Exception:
        logger.debug("capture_foreground_image 失败", exc_info=True)
        return None, "", False


class LookAction:
    """瞥屏：自主 / 响应式共用 glance。"""

    def __init__(
        self,
        db: Database,
        *,
        config: dict | None = None,
        llm: LLMGateway | None = None,
        capture_fn: Callable[..., tuple[bytes | None, str, bool]] | None = None,
    ):
        self.db = db
        self.config = config or {}
        self.llm = llm
        self._capture_fn = capture_fn or capture_foreground_image
        self._autonomous_lock = asyncio.Lock()
        # Brain 可注入：成功瞥后走心（冲击+主观短说）；open_and_look 也依赖此
        self.post_success: Callable[..., Any] | None = None

    async def is_paused(self, now: datetime) -> bool:
        raw = await self.db.get_body_memory(LOOK_PAUSE_UNTIL_KEY)
        if not raw:
            return False
        try:
            until = datetime.fromisoformat(str(raw))
        except Exception:
            return False
        return now < until

    async def set_pause(self, now: datetime) -> None:
        until = now + timedelta(hours=pause_hours(self.config))
        await self.db.set_body_memory(
            LOOK_PAUSE_UNTIL_KEY, until.isoformat(timespec="seconds")
        )

    async def clear_pause(self) -> None:
        try:
            await self.db.set_body_memory(LOOK_PAUSE_UNTIL_KEY, "")
        except Exception:
            logger.debug("clear look pause 失败", exc_info=True)

    async def _interval_ok(self, now: datetime) -> bool:
        raw = await self.db.get_body_memory(LOOK_LAST_KEY)
        if not raw:
            return True
        try:
            last = datetime.fromisoformat(str(raw))
        except Exception:
            return True
        mins = min_interval_minutes(self.config)
        return now - last >= timedelta(minutes=mins)

    async def _soft_block_count(self) -> int:
        raw = await self.db.get_body_memory(LOOK_SOFT_BLOCK_KEY)
        try:
            return int(raw or 0)
        except Exception:
            return 0

    async def _set_soft_block_count(self, n: int) -> None:
        await self.db.set_body_memory(LOOK_SOFT_BLOCK_KEY, int(max(0, n)))

    async def _mark_soft_block(self) -> int:
        n = await self._soft_block_count()
        n += 1
        await self._set_soft_block_count(n)
        return n

    async def _reset_soft_block(self) -> None:
        await self._set_soft_block_count(0)

    async def _mark_last(self, now: datetime) -> None:
        await self.db.set_body_memory(
            LOOK_LAST_KEY, now.isoformat(timespec="seconds")
        )

    async def first_notice_pending(self) -> bool:
        raw = await self.db.get_body_memory(LOOK_FIRST_NOTICE_KEY)
        return not bool(raw)

    async def mark_first_notice(self) -> None:
        await self.db.set_body_memory(LOOK_FIRST_NOTICE_KEY, "1")

    async def glance(
        self,
        *,
        relationship_stage: str,
        season: str,
        now: datetime,
        reactive: bool = False,
        user_question: str | None = None,
        speaking: bool = False,
        mode: str = "solitary",
        force_soft: bool = False,
        last_user_interaction: datetime | None = None,
    ) -> dict[str, Any] | None:
        """
        执行一次瞥视。reactive=True 时跳过防连瞥与自主让路。
        返回 result dict；硬门拒绝返回 None。
        force_soft 保留兼容，不再用于突破防连瞥。
        """
        if reactive:
            return await self._glance_unlocked(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
                reactive=True,
                user_question=user_question,
                speaking=speaking,
                mode=mode,
                force_soft=False,
                last_user_interaction=last_user_interaction,
            )
        async with self._autonomous_lock:
            return await self._glance_unlocked(
                relationship_stage=relationship_stage,
                season=season,
                now=now,
                reactive=False,
                user_question=user_question,
                speaking=speaking,
                mode=mode,
                force_soft=force_soft,
                last_user_interaction=last_user_interaction,
            )

    async def _glance_unlocked(
        self,
        *,
        relationship_stage: str,
        season: str,
        now: datetime,
        reactive: bool,
        user_question: str | None,
        speaking: bool,
        mode: str,
        force_soft: bool,
        last_user_interaction: datetime | None = None,
    ) -> dict[str, Any] | None:
        if not can_look(relationship_stage):
            await self._reset_soft_block()
            return None

        if not reactive and mode == "dreaming":
            await self._reset_soft_block()
            return None

        if not reactive and speaking:
            return None

        if not reactive and last_user_interaction is not None:
            grace = chat_grace_minutes(self.config) * 60.0
            if (now - last_user_interaction).total_seconds() < grace:
                return None

        paused = await self.is_paused(now)
        if paused and not reactive:
            await self._reset_soft_block()
            return None

        # 防连瞥：自主硬门（事不过三不可破；邀看 reactive 不受限）
        if not reactive and not await self._interval_ok(now):
            return None

        if reactive and paused:
            await self.clear_pause()

        jpeg, title, is_self = self._capture_fn()
        if not reactive and is_self:
            # 自身窗：跳过自主
            return None

        if not jpeg:
            result = {
                "type": "look_glance",
                "kind": "look",
                "outcome": OUTCOME_FAILED_CAPABILITY,
                "summary": "没能看见屏幕",
                "qi_line": "这回没看清……",
                "speak": True,
                "season": season,
                "found": None,
            }
            await self.db.insert_action(
                "look",
                result["summary"],
                target="world",
                outcome=OUTCOME_FAILED_CAPABILITY,
                season=season,
            )
            # 失败也占防连瞥，避免连拍空枪
            if not reactive:
                await self._mark_last(now)
                await self._reset_soft_block()
            return result

        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        user_text = "记下瞥到的画面印象（材料，不是台词）。"
        if reactive and user_question:
            user_text = (
                f"对方问过：「{user_question}」\n"
                "先只记下画面印象材料（不是对用户的答复台词）。"
            )

        need_notice = await self.first_notice_pending()

        impression = ""
        if self.llm is not None:
            try:
                messages = [
                    {"role": "system", "content": _LOOK_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    },
                ]
                impression = (
                    await self.llm.call("look", messages, temperature=0.5) or ""
                ).strip()
            except Exception:
                logger.debug("look LLM 失败", exc_info=True)
                impression = ""

        if not impression:
            impression = FALLBACK_QI_LINE

        # 暂定台词 = 印象；Brain 交付前 look_heart 会改成主观短说
        qi_line = impression
        if need_notice:
            qi_line = f"{FIRST_NOTICE_LINE}{qi_line}"
            await self.mark_first_notice()

        summary = (impression[:80] if impression else "瞥了一眼屏幕").strip()
        result = {
            "type": "look_glance",
            "kind": "look",
            "outcome": OUTCOME_SUCCESS,
            "summary": summary,
            "qi_line": qi_line,
            "speak": True,
            "season": season,
            "window_title": title[:80] if title else "",
            "reactive": reactive,
            "user_question": (user_question or "")[:200] if reactive else "",
            "first_notice": need_notice,
            "found": {"impression": impression},
        }
        if self.post_success is not None:
            try:
                await self.post_success(result, now)
            except Exception:
                logger.debug("look post_success 失败", exc_info=True)
        summary = str(result.get("summary") or summary).strip() or summary
        await self.db.insert_action(
            "look",
            summary,
            target="world",
            outcome=OUTCOME_SUCCESS,
            season=season,
        )
        await self._mark_last(now)
        await self._reset_soft_block()
        return result

    async def try_autonomous(
        self,
        *,
        relationship_stage: str,
        season: str,
        now: datetime,
        mode: str,
        speaking: bool = False,
        force_soft: bool = False,
        last_user_interaction: datetime | None = None,
    ) -> dict[str, Any] | None:
        return await self.glance(
            relationship_stage=relationship_stage,
            season=season,
            now=now,
            reactive=False,
            mode=mode,
            speaking=speaking,
            force_soft=force_soft,
            last_user_interaction=last_user_interaction,
        )
