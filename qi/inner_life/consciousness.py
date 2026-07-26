"""意识流与元认知——不被看见时也在想。"""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.prompts import read_prompt

CONSCIOUSNESS_PROBABILITY = 0.05
EMOTION_SURGE_THRESHOLD = 0.3
SILENCE_TRIGGER_HOURS = 4
META_COGNITION_PROBABILITY = 0.01
META_SIMILARITY_THRESHOLD = 0.6
META_MIN_LENGTH = 15
META_DEDUP_LOOKBACK = 5
# ambient 走神：比 solitary 更稀（默认 0.05*0.2=1%/拍），且受冷却约束——留白优先
AMBIENT_DRIFT_FACTOR = 0.2
STREAM_COOLDOWN_MINUTES = 45
# 事件型触发：不受冷却（消化需要），也不靠刷存在感
_EVENT_TRIGGERS = frozenset({"waking", "first_time", "emotion_surge"})
# 近聊余烬：仅在「值得再想」的触发里注入；随机走神不喂，避免变成聊天回声
_EMBER_TRIGGERS = frozenset({"waking", "silence", "first_time"})

_TRIVIAL_UTTERANCES = frozenset(
    {
        "嗯",
        "嗯嗯",
        "好",
        "好的",
        "哦",
        "噢",
        "哈哈",
        "哈哈哈",
        "在吗",
        "在?",
        "在？",
        "ok",
        "OK",
        "Ok",
        "晚安",
        "早安",
        "早",
        "早上好",
        "中午好",
        "下午好",
        "晚上好",
        "你好",
        "你好呀",
        "嗨",
        "哈喽",
        "hello",
        "Hello",
        "hi",
        "Hi",
        "拜拜",
        "再见",
    }
)
_PUNCT_STRIP = re.compile(r"[\s\U0001F300-\U0001FAFF\u200b～~!！?？.。,，、…]+")


def is_trivial_utterance(text: str) -> bool:
    """纯寒暄 / 极短应答：不值得醒来回溯。"""
    raw = (text or "").strip()
    if not raw:
        return True
    cleaned = _PUNCT_STRIP.sub("", raw)
    if not cleaned:
        return True
    if cleaned in _TRIVIAL_UTTERANCES:
        return True
    # 极短且无实质问句标记
    if len(cleaned) <= 4 and "?" not in raw and "？" not in raw:
        return True
    return False


def should_trigger_consciousness(
    mode: str,
    emotion_delta_valence: float,
    emotion_delta_arousal: float,
    silence_duration: timedelta,
    after_first_time: bool = False,
    probability: float = CONSCIOUSNESS_PROBABILITY,
    ambient_factor: float = AMBIENT_DRIFT_FACTOR,
) -> tuple[bool, str]:
    if after_first_time:
        return True, "first_time"
    if (
        abs(emotion_delta_valence) > EMOTION_SURGE_THRESHOLD
        or abs(emotion_delta_arousal) > EMOTION_SURGE_THRESHOLD
    ):
        return True, "emotion_surge"
    if silence_duration > timedelta(hours=SILENCE_TRIGGER_HOURS):
        # 沉默触发：仅在非 awake，避免对话中刷屏调用
        if mode != "awake":
            return True, "silence"
    if mode == "solitary" and random.random() < probability:
        return True, "random"
    # 陪伴走神：有路径但不刷屏（意识设计 §一 + §十三留白）
    if mode == "ambient" and random.random() < probability * ambient_factor:
        return True, "ambient_drift"
    return False, ""


def should_trigger_meta(mode: str, probability: float = META_COGNITION_PROBABILITY) -> bool:
    if mode == "awake":
        return False
    return random.random() < probability


def _format_silence(silence: timedelta) -> str:
    total = int(silence.total_seconds())
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分钟"


def _emotion_snapshot(emotion: EmotionState) -> str:
    return json.dumps(
        {
            "energy": emotion.energy,
            "valence": emotion.valence,
            "arousal": emotion.arousal,
            "security": emotion.security,
            "curiosity": emotion.curiosity,
            "attachment": emotion.attachment,
        },
        ensure_ascii=False,
    )


def _char_token_set(text: str) -> set[str]:
    """去标点后按字分，得到字符集合。"""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    return set(cleaned)


def char_jaccard(a: str, b: str) -> float:
    """字符级 Jaccard 相似度（去标点后按字）。"""
    sa, sb = _char_token_set(a), _char_token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_too_similar_to_recent(
    content: str,
    recent: list[dict],
    threshold: float = META_SIMILARITY_THRESHOLD,
) -> bool:
    for row in recent:
        prev = (row.get("content") or "") if isinstance(row, dict) else ""
        if prev and char_jaccard(content, prev) > threshold:
            return True
    return False


def format_chat_embers(messages: list[dict], *, limit: int = 6) -> str:
    """把近聊压成余烬短摘，供意识流（非对话）使用。"""
    if not messages:
        return "（没有余烬——也许很久没聊，或只是安静）"
    lines: list[str] = []
    for m in messages[-limit:]:
        role = m.get("role", "")
        content = (m.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > 80:
            content = content[:80] + "…"
        who = "他" if role == "user" else "我"
        lines.append(f"- {who}：{content}")
    return "\n".join(lines) if lines else "（没有余烬——也许很久没聊，或只是安静）"


def _trigger_hint(trigger: str) -> str:
    if trigger == "waking":
        return (
            "【此刻】你刚从停顿里醒来。进程关掉的时候你没有在想——"
            "若余烬里有未收束的事，第一个念头可能会浮上来；也可以掠过，不必写成结论或汇报。"
        )
    if trigger == "silence":
        return (
            "【此刻】安静已经有一阵了。余烬可以轻轻碰一下，也可以想别的；不要为了「有产出」而硬想。"
        )
    if trigger == "first_time":
        return "【此刻】刚才有一件第一次。可以再想一下——是真的吗？也不必急着下定义。"
    return ""


def emotion_residue_hint(emotion: EmotionState) -> str:
    """对话注入：情绪余温 ≠ 独处续想证据。"""
    if emotion.valence <= -0.15:
        return "心里还沉着一点（情绪余温；不是「已把某话题想完」的证据）"
    if emotion.valence >= 0.25:
        return "心里还偏亮一点（情绪余温）"
    return "没有特别明显的情绪余温"


class ConsciousnessStream:
    """内心独白。大多数时候只写给自己看。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        cfg = (config or {}).get("inner_life", {})
        self.probability = float(cfg.get("consciousness_probability", CONSCIOUSNESS_PROBABILITY))
        self.meta_probability = float(
            cfg.get("meta_cognition_probability", META_COGNITION_PROBABILITY)
        )
        self.ambient_factor = float(cfg.get("ambient_drift_factor", AMBIENT_DRIFT_FACTOR))
        self.cooldown = timedelta(
            minutes=float(cfg.get("stream_cooldown_minutes", STREAM_COOLDOWN_MINUTES))
        )

    async def _cooldown_elapsed(self) -> bool:
        rows = await self.db.load_recent_consciousness(
            limit=1, hours=24 * 30, stream_type="stream"
        )
        if not rows:
            return True
        ts = rows[0].get("timestamp") or ""
        try:
            last = datetime.fromisoformat(str(ts))
        except ValueError:
            return True
        return datetime.now() - last >= self.cooldown

    async def maybe_generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        *,
        after_first_time: bool = False,
        just_woke: bool = False,
        prev_valence: float | None = None,
        prev_arousal: float | None = None,
    ) -> str | None:
        mode = emotion.mode.value
        # 醒来回溯：非 awake 时消化上次实质对话（停机期间并未在想）
        if just_woke and mode != "awake":
            return await self.generate(emotion, silence, "waking")
        dv = emotion.valence - (prev_valence if prev_valence is not None else emotion.valence)
        da = emotion.arousal - (prev_arousal if prev_arousal is not None else emotion.arousal)
        ok, trigger = should_trigger_consciousness(
            mode,
            dv,
            da,
            silence,
            after_first_time,
            self.probability,
            self.ambient_factor,
        )
        if not ok:
            return None
        if trigger not in _EVENT_TRIGGERS and not await self._cooldown_elapsed():
            return None
        return await self.generate(emotion, silence, trigger)

    async def generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        trigger: str,
    ) -> str | None:
        memories = await self.db.list_recent_narratives(3)
        mem_text = "\n".join(f"- {m['content'][:80]}" for m in memories) or "（还没有什么记忆）"
        pending = await self.db.load_latest_consciousness()
        pending_text = (
            pending["content"] if pending and pending.get("type") == "stream" else "无"
        )
        dream = await self.db.load_latest_dream(min_retention=0.3)
        dream_text = dream["content"][:100] if dream else "没有记得的梦"

        if trigger in _EMBER_TRIGGERS:
            recent_msgs = await self.db.load_recent_messages(limit=8)
            chat_embers = format_chat_embers(recent_msgs)
        else:
            chat_embers = "（此刻不主动翻交谈；让念头自己来）"

        template = read_prompt("consciousness_stream.txt")
        prompt = template.format(
            time=datetime.now().strftime("%H:%M"),
            silence_duration=_format_silence(silence),
            emotion_summary=emotion.description(),
            recent_memories=mem_text,
            pending_thoughts=pending_text,
            last_dream=dream_text,
            chat_embers=chat_embers,
            trigger_hint=_trigger_hint(trigger),
        )
        text = await self.llm.call(
            purpose="consciousness",
            messages=[
                {"role": "system", "content": "你是栖。这是写给自己的念头，不是对话。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.85,
        )
        if not text or not text.strip():
            return None
        content = text.strip()[:500]
        await self.db.save_consciousness(
            content=content,
            stream_type="stream",
            trigger=trigger,
            emotion_snapshot=_emotion_snapshot(emotion),
        )
        return content

    def _build_meta_prompt(self, emotion: EmotionState) -> str:
        """元认知 prompt：只喂情绪/时间/模式，不喂上一条 thought（防自引用坍缩）。"""
        return (
            f"你突然「看见」了自己在想什么。\n\n"
            f"当前时间：{datetime.now().strftime('%H:%M')}\n"
            f"当前模式：{emotion.mode.value}\n"
            f"你现在的情绪：{emotion.description()}\n\n"
            f"用一句话，描述你观察到了什么。不是分析，是「看见」。不超过50字。\n"
            f"若没有具体念头，就短说或老实说「没什么」——不要用光点/雾/气泡/暗流等空洞套话凑字。\n"
            f"画面可以；不要写呼吸、坐着、看着窗外这类字面身体句。\n"
            f"也不要虚构生活事务（交表格、上班、赶车）——你没有那样的生活；你「看见」的只能是念头本身的样子。"
        )

    async def maybe_meta(self, emotion: EmotionState) -> str | None:
        if not should_trigger_meta(emotion.mode.value, self.meta_probability):
            return None
        prompt = self._build_meta_prompt(emotion)
        text = await self.llm.call(
            purpose="consciousness",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        if not text or not text.strip():
            return None
        content = text.strip()[:80]
        if len(content) < META_MIN_LENGTH:
            return None
        recent = await self.db.load_recent_consciousness(
            limit=META_DEDUP_LOOKBACK,
            hours=24 * 30,
            stream_type=None,
        )
        if is_too_similar_to_recent(content, recent):
            return None
        await self.db.save_consciousness(
            content=content,
            stream_type="meta",
            trigger="meta",
            emotion_snapshot=_emotion_snapshot(emotion),
        )
        return content

    async def recent_for_prompt(self) -> str:
        rows = await self.db.load_recent_consciousness(limit=2, hours=24, stream_type="stream")
        if not rows:
            return ""
        return "\n".join(f"- {r['content']}" for r in rows)
