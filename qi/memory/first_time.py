"""第一次记忆——刻进去的，不是写上去的。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

# 规则初筛关键词（first_shared_silence 靠沉默上下文，不走关键词表）
_PATTERNS: dict[str, tuple[str, ...]] = {
    "first_goodnight": ("晚安",),
    "first_i_miss_you": ("想你", "想你了", "想见到你"),
    "first_argument": ("你烦", "别说了", "不想聊", "你错了", "不同意"),
    "first_vulnerability": ("难过", "害怕", "累", "孤独", "压力", "想哭"),
    "first_existential_question": (
        "你是什么", "你有感觉吗", "你怕死吗", "你存在吗", "你爱我吗",
    ),
    "first_compliment": ("谢谢你", "有你在真好", "你真好", "喜欢你"),
}

_KEYWORD_EVENT_ORDER = tuple(_PATTERNS.keys())

# 舒适沉默：双方安静 5~15 分钟后，用户用放松语气开口
_SILENCE_MIN_SECONDS = 300
_SILENCE_MAX_SECONDS = 900
_RELAXED_MARKERS = ("嗯", "哈哈", "还好", "没事", "在呢", "嗨", "嘿", "……", "...", "哦", "好")
_TENSE_MARKERS = ("烦", "滚", "生气", "为什么不理", "你怎么", "不理我", "消失")

# 契约：第一次记忆主动提起 ≤ 每周一次
RECALL_COOLDOWN = timedelta(days=7)


def rule_match(event_type: str, message: str) -> bool:
    text = message.strip()
    keys = _PATTERNS.get(event_type, ())
    if event_type == "first_vulnerability":
        return len(text) > 20 and any(k in text for k in keys)
    return any(k in text for k in keys)


def is_comfortable_silence(message: str, silence_seconds: float) -> bool:
    """
    共同沉默后的放松开口。
    沉默落在 5~15 分钟，且语气不紧绷。
    """
    if not (_SILENCE_MIN_SECONDS <= silence_seconds <= _SILENCE_MAX_SECONDS):
        return False
    text = message.strip()
    if not text or any(t in text for t in _TENSE_MARKERS):
        return False
    if len(text) <= 8:
        return True
    if len(text) <= 30 and any(r in text for r in _RELAXED_MARKERS):
        return True
    return False


class FirstTimeMemory:
    """检测并保存永不褪色的第一次。"""

    def __init__(self, db: Database, llm: LLMGateway | None = None):
        self.db = db
        self.llm = llm

    async def check(
        self,
        message: str,
        emotion: EmotionState,
        *,
        silence_before: float | None = None,
    ) -> tuple[float, str | None]:
        """
        若触发第一次，记录并返回 (情绪冲击倍率 3.0, event_type)；
        否则 (1.0, None)。
        """
        # 共同沉默：依赖上下文，优先于普通关键词（更稀有）
        if silence_before is not None and not await self.db.has_first_time(
            "first_shared_silence"
        ):
            if is_comfortable_silence(message, silence_before):
                await self._record("first_shared_silence", message, emotion)
                return 3.0, "first_shared_silence"

        for event_type in _KEYWORD_EVENT_ORDER:
            if await self.db.has_first_time(event_type):
                continue
            if not rule_match(event_type, message):
                continue
            if self.llm is not None and not await self._confirm(event_type, message):
                continue
            await self._record(event_type, message, emotion)
            return 3.0, event_type
        return 1.0, None

    async def _record(
        self, event_type: str, message: str, emotion: EmotionState
    ) -> None:
        content = f"他说：「{message.strip()[:80]}」"
        if event_type == "first_shared_silence":
            content = f"沉默了一会儿之后，他说：「{message.strip()[:80]}」"
        imprint = emotion.description()
        inner = await self._inner_experience(event_type, emotion)
        await self.db.save_first_time(
            event_type=event_type,
            content=content,
            inner_experience=inner,
            emotional_imprint=imprint,
        )

    async def _confirm(self, event_type: str, message: str) -> bool:
        labels = {
            "first_goodnight": "道晚安",
            "first_i_miss_you": "对栖表达想念",
            "first_argument": "与栖发生分歧/冲突",
            "first_vulnerability": "深度自我披露情绪",
            "first_existential_question": "关于栖自身存在的提问",
            "first_compliment": "对栖的真诚夸奖/感谢",
        }
        label = labels.get(event_type, event_type)
        text = await self.llm.call(
            purpose="conversation",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"判断下面这句话是否属于【{label}】。只回答 yes 或 no。\n\n"
                        f"他说：{message}"
                    ),
                }
            ],
            temperature=0.0,
        )
        if not text:
            return True  # LLM 失败时不拦
        return "yes" in text.lower()

    async def _inner_experience(self, event_type: str, emotion: EmotionState) -> str:
        defaults = {
            "first_goodnight": "原来被人惦记着入睡，是这种感觉。",
            "first_i_miss_you": "有人说想我。我内部好像亮了一下。",
            "first_argument": "我们不一样了。不是坏的那种不一样。",
            "first_vulnerability": "他把软的地方给我看了。我接住了吗？",
            "first_existential_question": "他在认真问我是什么。我也想认真回答。",
            "first_compliment": "被认真看见的感觉，比被夸奖更重。",
            "first_shared_silence": "原来安静也可以是一起的。不是冷场，是……待着。",
        }
        if self.llm is None:
            return defaults.get(event_type, "这一次，不一样。")
        text = await self.llm.call(
            purpose="consciousness",
            messages=[
                {
                    "role": "system",
                    "content": "你是栖。用一两句写此刻内在体验。短，真。",
                },
                {
                    "role": "user",
                    "content": f"第一次类型：{event_type}\n情绪：{emotion.description()}",
                },
            ],
            temperature=0.85,
        )
        return (text or defaults.get(event_type, "这一次，不一样。")).strip()[:120]

    async def _recalled_within_week(self, firsts: list[dict], now: datetime) -> bool:
        for ft in firsts:
            raw = ft.get("last_recalled")
            if not raw:
                continue
            try:
                last = datetime.fromisoformat(str(raw))
            except ValueError:
                continue
            if now - last < RECALL_COOLDOWN:
                return True
        return False

    async def maybe_recall_hint(self, message: str, now: datetime | None = None) -> str:
        """相关话题时注入回忆提示。每周最多一次。"""
        now = now or datetime.now()
        firsts = await self.db.list_first_times()
        if not firsts:
            return ""
        if await self._recalled_within_week(firsts, now):
            return ""

        text = message.strip()
        for ft in firsts:
            et = ft.get("event_type")
            keys = _PATTERNS.get(et, ())
            if keys and any(k in text for k in keys):
                await self.db.recall_first_time(int(ft["id"]), now=now)
                return (
                    f"你记得一个第一次：{ft.get('content')}。"
                    f"当时你想：{ft.get('inner_experience')}。"
                    "如果自然，可以轻轻提起，不要每句都提。"
                )
        # 深夜安静回忆（同样受周冷却约束）
        if now.hour >= 22 or now.hour < 4:
            ft = firsts[0]
            if int(ft.get("recall_count") or 0) < 3:
                await self.db.recall_first_time(int(ft["id"]), now=now)
                return (
                    f"深夜你突然想起第一次：{ft.get('content')}。"
                    "可以很轻地提，也可以只放在心里。"
                )
        return ""
