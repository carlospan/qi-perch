"""意识流与元认知——未闭合念头驱动；文本走 LLM / 模板降级链。"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

from qi.memory.open_loops import OpenLoopQueue, build_concern
from qi.prompts import read_prompt
from qi.relationship.season import SEASON_BEHAVIOR_HINTS

logger = logging.getLogger("qi.inner_life.consciousness")

CONSCIOUSNESS_PROBABILITY = 0.05
EMOTION_SURGE_THRESHOLD = 0.3
SILENCE_TRIGGER_HOURS = 4
META_COGNITION_PROBABILITY = 0.01
META_SIMILARITY_THRESHOLD = 0.6
META_MIN_LENGTH = 15
META_DEDUP_LOOKBACK = 5
# ambient 走神：比 solitary 更稀；有积压才摇骰（C4 时机阀）
AMBIENT_DRIFT_FACTOR = 0.2
STREAM_COOLDOWN_MINUTES = 45
# 事件型触发：不受冷却（消化需要），也不靠刷存在感
_EVENT_TRIGGERS = frozenset(
    {
        "waking",
        "first_time",
        "emotion_surge",
        "silence",
        "season_change",
        "user_drift",
    }
)
# 近聊余烬：仅在「值得再想」的触发里注入
_EMBER_TRIGGERS = frozenset({"waking", "silence", "first_time"})
_OPEN_TAIL = ("先这样放着。", "也不必现在就有答案。", "回头再碰一下就好。")

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
    *,
    open_loop_count: int = 0,
) -> tuple[bool, str]:
    """
    事件型即时触发；随机/ambient 仅在有 open loop 积压时作时机阀（C4）。
    """
    if after_first_time:
        return True, "first_time"
    if (
        abs(emotion_delta_valence) > EMOTION_SURGE_THRESHOLD
        or abs(emotion_delta_arousal) > EMOTION_SURGE_THRESHOLD
    ):
        return True, "emotion_surge"
    if silence_duration > timedelta(hours=SILENCE_TRIGGER_HOURS):
        if mode != "awake":
            return True, "silence"
    # 无积压 → 随机不得凭空造想
    if open_loop_count <= 0:
        return False, ""
    if mode == "solitary" and random.random() < probability:
        return True, "loop_backlog"
    if mode == "ambient" and random.random() < probability * ambient_factor:
        return True, "loop_backlog"
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
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    return set(cleaned)


def char_jaccard(a: str, b: str) -> float:
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
    if trigger == "loop_backlog":
        return "【此刻】有一件还没想完的事浮上来。顺着它想，不必另起炉灶。"
    if trigger == "season_change":
        return "【此刻】内在季节偏了。感受节奏的变化即可，不必命名或总结。"
    if trigger == "user_drift":
        return "【此刻】你察觉他有些不一样。可以轻轻碰一下，不要评判。"
    return ""


def emotion_residue_hint(emotion: EmotionState) -> str:
    """对话注入：情绪余温 ≠ 独处续想证据。"""
    if emotion.valence <= -0.15:
        return "心里还沉着一点（情绪余温；不是「已把某话题想完」的证据）"
    if emotion.valence >= 0.25:
        return "心里还偏亮一点（情绪余温）"
    return "没有特别明显的情绪余温"


def _surge_tone(dv: float, da: float) -> str:
    if abs(dv) >= abs(da):
        if dv > 0:
            return "亮"
        return "沉"
    if da > 0:
        return "躁"
    return "静"


def render_template_thought(
    loop: dict,
    emotion: EmotionState,
) -> str:
    """断网模板：心事 + 余温 + 开放尾句（不下结论）。"""
    concern = str(loop.get("concern") or "有一件事还没想完。").strip()
    fragment = str(loop.get("fragment") or "").strip()
    lines = [concern]
    if fragment:
        lines.append(f"上次想到：{fragment[:80]}……")
    residue = emotion_residue_hint(emotion)
    # 模板用更短余温
    if "沉" in residue:
        lines.append("心里还偏沉一点。")
    elif "亮" in residue:
        lines.append("心里还偏亮一点。")
    else:
        lines.append("没有特别明显的余温，可那一下还在。")
    lines.append(random.choice(_OPEN_TAIL))
    return "\n".join(lines)


class ConsciousnessStream:
    """内心独白。大多数时候只写给自己看。"""

    def __init__(self, db: Database, llm: LLMGateway, config: dict | None = None):
        self.db = db
        self.llm = llm
        self.loops = OpenLoopQueue(db)
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

    async def _waking_seed(self) -> str:
        msgs = await self.db.load_recent_messages(limit=6)
        for m in reversed(msgs):
            if m.get("role") != "user":
                continue
            text = (m.get("content") or "").strip()
            if text and not is_trivial_utterance(text):
                snippet = text[:40]
                return f"「{snippet}」"
        return ""

    async def enqueue_event(self, kind: str, seed: str = "") -> dict:
        return await self.loops.enqueue(kind, seed=seed)

    async def maybe_generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        *,
        after_first_time: bool = False,
        just_woke: bool = False,
        prefer_close: bool = False,
        prev_valence: float | None = None,
        prev_arousal: float | None = None,
        force_trigger: str | None = None,
        force_seed: str = "",
    ) -> str | None:
        await self.loops.load()
        mode = emotion.mode.value

        # 后台事件：enqueue + 即时 generate
        if force_trigger and force_trigger in _EVENT_TRIGGERS:
            await self.loops.enqueue(force_trigger, seed=force_seed)
            loop = self.loops.pick(prefer_kind=force_trigger)
            return await self.generate(
                emotion, silence, force_trigger, loop=loop
            )

        if just_woke and mode != "awake":
            seed = await self._waking_seed()
            await self.loops.enqueue("waking", seed=seed)
            loop = self.loops.pick(prefer_kind="waking")
            return await self.generate(emotion, silence, "waking", loop=loop)

        if prefer_close:
            if self.loops.count() == 0:
                return None
            loop = self.loops.pick(prefer_close=True)
            return await self.generate(
                emotion, silence, "loop_backlog", loop=loop
            )

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
            open_loop_count=self.loops.count(),
        )
        if not ok:
            return None
        if trigger not in _EVENT_TRIGGERS and not await self._cooldown_elapsed():
            return None

        prefer_kind = None
        if trigger == "first_time":
            await self.loops.enqueue("first_time", seed="那件第一次")
            prefer_kind = "first_time"
        elif trigger == "emotion_surge":
            await self.loops.enqueue(
                "emotion_surge", seed=_surge_tone(dv, da)
            )
            prefer_kind = "emotion_surge"
        elif trigger == "silence":
            await self.loops.enqueue("silence", seed="")
            prefer_kind = "silence"

        loop = self.loops.pick(
            prefer_kind=prefer_kind,
            prefer_close=trigger == "loop_backlog",
        )
        return await self.generate(emotion, silence, trigger, loop=loop)

    async def generate(
        self,
        emotion: EmotionState,
        silence: timedelta,
        trigger: str,
        *,
        loop: dict | None = None,
    ) -> str | None:
        if loop is None and self.loops.count() > 0:
            loop = self.loops.pick(prefer_kind=trigger if trigger in _EVENT_TRIGGERS else None)

        open_loop_text = "（此刻没有特别悬着的心事）"
        if loop:
            open_loop_text = str(loop.get("concern") or "")
            frag = str(loop.get("fragment") or "").strip()
            if frag:
                open_loop_text += f"\n上次想到：{frag[:80]}……"

        pending_text = self.loops.overview(
            exclude_id=str(loop["id"]) if loop and loop.get("id") else None
        )

        memories = await self.db.list_recent_narratives(3)
        mem_text = "\n".join(f"- {m['content'][:80]}" for m in memories) or "（还没有什么记忆）"
        dream = await self.db.load_latest_dream(min_retention=0.3)
        dream_text = dream["content"][:100] if dream else "没有记得的梦"

        if trigger in _EMBER_TRIGGERS:
            recent_msgs = await self.db.load_recent_messages(limit=8)
            chat_embers = format_chat_embers(recent_msgs)
        else:
            chat_embers = "（此刻不主动翻交谈；让念头自己来）"

        season = "spring"
        stage = "stranger"
        trust = 0.0
        culture = None
        rel = await self.db.load_relationship()
        if rel:
            if rel.get("season"):
                season = str(rel["season"])
            if rel.get("stage"):
                stage = str(rel["stage"])
            trust = float(rel.get("trust") or 0)
            culture = rel.get("shared_culture")
        season_hint = SEASON_BEHAVIOR_HINTS.get(
            season, SEASON_BEHAVIOR_HINTS["spring"]
        )

        from qi.inner_life.identity_snapshot import ensure_identity_snapshot

        identity_snapshot = await ensure_identity_snapshot(
            self.db,
            stage=stage,
            trust=trust,
            season=season,
            shared_culture=culture,
        )

        if loop and loop.get("id"):
            await self.loops.note_think_attempt(str(loop["id"]))

        path = "llm"
        text = ""
        try:
            template = read_prompt("consciousness_stream.txt")
            prompt = template.format(
                time=datetime.now().strftime("%H:%M"),
                silence_duration=_format_silence(silence),
                emotion_summary=emotion.description(),
                season_hint=season_hint,
                identity_snapshot=identity_snapshot,
                recent_memories=mem_text,
                open_loop=open_loop_text,
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
        except Exception:
            logger.debug("意识流 LLM 异常，走模板", exc_info=True)
            text = ""

        if not text or not str(text).strip():
            path = "template"
            if loop is None:
                loop = {
                    "id": "",
                    "kind": trigger,
                    "concern": build_concern(trigger, ""),
                    "fragment": "",
                }
            text = render_template_thought(loop, emotion)

        content = str(text).strip()[:500]
        if not content:
            return None

        await self.db.save_consciousness(
            content=content,
            stream_type="stream",
            trigger=trigger,
            emotion_snapshot=_emotion_snapshot(emotion),
        )

        if loop and loop.get("id"):
            closed = await self.loops.close(str(loop["id"]), fragment=content[:120])
            if closed is not None:
                await self._sediment(closed, content)
                try:
                    await self.db.set_body_memory(
                        "last_loop_close",
                        {
                            "at": datetime.now().isoformat(timespec="seconds"),
                            "loop_id": closed.get("id"),
                            "kind": closed.get("kind"),
                            "path": path,
                            "concern": closed.get("concern"),
                        },
                    )
                except Exception:
                    logger.debug("loop close trace 写入失败", exc_info=True)
        return content

    async def _sediment(self, loop: dict, thought: str) -> None:
        """闭合沉淀：一条 internal raw_event，不立刻 weave。"""
        concern = str(loop.get("concern") or "")[:40]
        snippet = thought.strip()[:80]
        try:
            await self.db.save_raw_event(
                "internal",
                f"[想过] {concern} → {snippet}",
                emotional_impact=0.2,
                attention_weight=1.0,
            )
        except Exception:
            logger.debug("loop 沉淀 raw_event 失败", exc_info=True)

    def _build_meta_prompt(self, emotion: EmotionState) -> str:
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
