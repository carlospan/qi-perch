"""用户事实记忆——栖对你的稳定认识（骨头，不是会褪色的故事）。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qi.core.emotion import EmotionState
    from qi.llm.gateway import LLMGateway
    from qi.storage.database import Database

logger = logging.getLogger("qi.memory.facts")

CONFIDENCE_FLOOR = 0.6

# 身份信号：任何关系阶段都留意。命中即规则抽取，不调 LLM。不含「我是」（歧义大）。
IDENTITY_SIGNALS = (
    "我叫",
    "我名字",
    "我的名字",
    "叫我",
    "称呼我",
    "你可以叫我",
    "我大名",
    "我小名",
    "我英文名",
    "我姓",
)

# 用户表示「就要告诉你名字」但本句可能还没给出——武装 awaiting_name
_NAME_DISCLOSURE_INTENTS = (
    "告诉你我的名字",
    "告诉你名字",
    "跟你说我的名字",
    "和你说我的名字",
    "说一下我的名字",
    "我是说我的名字",
    "我想告诉你我的名字",
    "想告诉你我叫",
    "我跟你说下我叫",
)

# 栖侧邀名（工作记忆里最近 qi 句）
_QI_NAME_INVITE_CUES = (
    "告诉我",
    "你告诉我",
    "说吧",
    "说啊",
    "说呀",
    "我听着",
    "愿意听",
    "你说",
)

# 绝不能当成人名的碎片
_NAME_REJECT_TOKENS = frozenset(
    {
        "吗",
        "呢",
        "啊",
        "呀",
        "吧",
        "么",
        "什麼",
        "什么",
        "谁",
        "哪",
        "好的",
        "好",
        "嗯",
        "哦",
        "啊哈",
        "记得",
        "重启",
        "项目",
        "名字",
        "姓名",
        "叫什么",
        "什么名",
        "不知道",
        "不想",
        "算了",
        "再见",
        "你好",
        "谢谢",
        "谢谢你",
        "感谢",
        "多谢",
        "不客气",
    }
)

_AWAITING_NAME_USER_LIMIT = 6  # 武装后最多再等几条用户消息
_AWAITING_NAME_SECONDS = 1800  # 或半小时

# 其他事实信号：关系 ≥ acquaintance 才留意。
OTHER_FACT_SIGNALS = (
    "我妈",
    "我爸",
    "我老婆",
    "我老公",
    "我女朋友",
    "我男朋友",
    "我孩子",
    "我儿子",
    "我女儿",
    "我家人",
    "我工作",
    "我上班",
    "我同事",
    "我老板",
    "我是做",
    "我干",
    "我住",
    "我搬家",
    "我家在",
    "我在",  # 「我在上海」；抽取时排除「我在想/说…」
    "我喜欢",
    "我讨厌",
    "我不吃",
    "我怕",
    "我过敏",
)

# 状态变更口语（设计验收「我换工作了」）；回写注明相对 OTHER_FACT_SIGNALS 的扩展。
_OCCUPATION_CHANGE_SIGNALS = ("换工作", "跳槽", "离职", "辞了职")

_DEFAULT_STABILITY: dict[str, str] = {
    "identity": "stable",
    "family": "stable",
    "preference": "stable",
    "important_date": "stable",
    "life_event": "stable",
    "occupation": "state",
    "location": "state",
    "concern": "state",
    "health": "stable",
    "other": "stable",
}

_STAGE_RANK = {
    "stranger": 0,
    "acquaintance": 1,
    "friend": 2,
    "bonded": 3,
}

_SIMILARITY_CONFIRM = 0.72
_SIMILARITY_CONFLICT = 0.35  # 同 type 已有 active 且不够像 → 视为冲突可取代（state）

# 注入 prompt 时按阶段的条数上限（克制，不堆砌）
_FACT_PROMPT_LIMITS = {
    "stranger": 2,
    "acquaintance": 4,
    "friend": 6,
    "bonded": 8,
}

# 更正信号：命中后走 supersede，再记新
_CORRECTION_SIGNALS = (
    "我不叫",
    "其实是",
    "其实叫",
    "其实我叫",
    "我现在不",
    "不是",
    "记错了",
    "你记错",
)


def default_stability(fact_type: str) -> str:
    return _DEFAULT_STABILITY.get(fact_type, "stable")


def format_facts_for_prompt(facts: list[dict], relationship_stage: str) -> str:
    """
    把 active 事实组织成一小段「你认识的他」。
    按 emotional_weight 排序、设条数上限；陌生期偏短、偏身份。
    """
    if not facts:
        return "（你还不太了解他）"

    limit = _FACT_PROMPT_LIMITS.get(relationship_stage, 4)
    ranked = sorted(
        facts,
        key=lambda f: float(f.get("emotional_weight") or 0),
        reverse=True,
    )

    if relationship_stage == "stranger":
        identity = [f for f in ranked if f.get("fact_type") == "identity"]
        others = [f for f in ranked if f.get("fact_type") != "identity"]
        picked = (identity[:1] + others)[:limit]
    else:
        picked = ranked[:limit]

    sentences: list[str] = []
    for f in picked:
        content = str(f.get("content") or "").strip()
        if not content:
            continue
        if f.get("fact_type") == "identity":
            frag = identity_name_fragment(content)
            if frag is not None and not looks_like_person_name(frag):
                continue
        if not content.endswith(("。", "！", "？", ".", "!", "?")):
            content = f"{content}。"
        sentences.append(content)
    return "".join(sentences) if sentences else "（你还不太了解他）"


def stage_at_least(stage: str, minimum: str) -> bool:
    return _STAGE_RANK.get(stage, 0) >= _STAGE_RANK.get(minimum, 0)


def looks_like_person_name(name: str) -> bool:
    """人名形态门控：拒疑问尾、拒常见非名碎片。"""
    name = (name or "").strip().strip("的了啊呀呢吧嘛哟欸")
    if not name:
        return False
    if name in _NAME_REJECT_TOKENS:
        return False
    if any(
        x in name
        for x in (
            "什么",
            "什麼",
            "名字",
            "姓名",
            "记得",
            "重启",
            "项目",
            "叫什么",
            "不知道",
        )
    ):
        return False
    if name.endswith(("吗", "呢", "么", "吧", "啊", "呀", "嘛", "？", "?")):
        return False
    if len(name) > 12:
        return False
    # 汉字名（可含 ·）；或较短拉丁名
    if re.fullmatch(r"[\u4e00-\u9fff·]{1,8}", name):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z\-'. ]{0,30}", name) and len(name) <= 32:
        return True
    return False


def is_name_memory_question(text: str) -> bool:
    """在问「记不记得 / 叫什么」——绝不当介绍自己。"""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(r"(记得|想起|还记得).{0,12}(名字|我叫|叫什么)", t):
        return True
    if re.search(r"(我叫|叫我|我的名字).{0,8}什么", t):
        return True
    if re.search(r"我的名字[吗麼呢么]", t):
        return True
    if re.search(r"你还记得我.{0,6}名", t):
        return True
    if "记得我叫什么" in t or "记得我的名字" in t:
        return True
    return False


def is_name_disclosure_intent(text: str) -> bool:
    """用户表示即将 / 正在交代名字，但本句未必已给出可落库的人名。"""
    t = (text or "").strip()
    if not t or is_name_memory_question(t):
        return False
    if any(s in t for s in _NAME_DISCLOSURE_INTENTS):
        return True
    # 「我的名字啊 / 说名字」类软信号（无「吗」问句）
    if re.search(r"(告诉你|跟你说|和你说).{0,6}(我的)?名字", t):
        return True
    if re.search(r"我是说.{0,4}(我的)?名字", t):
        return True
    return False


def is_bare_name_utterance(text: str) -> bool:
    """整句几乎就是一个人名（可带句末标点）。"""
    t = (text or "").strip()
    t = re.sub(r"^[「『\"'（(]+|[」』\"'）)。.!！？?…]+$", "", t).strip()
    if not t or any(ch in t for ch in ("，", ",", "。", "！", "？", " ", "\t")):
        # 允许中间空格的英文名：上面已因空格失败；英文另行放宽
        if re.fullmatch(r"[A-Za-z][A-Za-z\-'. ]{0,30}", t):
            return looks_like_person_name(t)
        return False
    return looks_like_person_name(t)


def identity_name_fragment(content: str) -> str | None:
    """从「他叫X / 他希望被叫做X」里取出名字片段。"""
    c = (content or "").strip()
    for prefix in ("他希望被叫做", "他叫", "他姓"):
        if c.startswith(prefix):
            return c[len(prefix) :].rstrip("。.!！？?").strip() or None
    return None


def _qi_asking_user_name(content: str) -> bool:
    """栖在问对方叫什么（可武装 awaiting_name）。"""
    t = (content or "").strip()
    if not t:
        return False
    if re.search(
        r"你叫什么(?:名字)?|你叫啥|怎么称呼你|"
        r"你的名字(?:是什么|呢|啊)?|告诉我你(?:的)?名字|"
        r"你呢[？?。.!！\s]*你叫",
        t,
    ):
        return True
    return False


def _qi_recently_invited_name(recent: list[dict] | None) -> bool:
    """只看最近一条栖的话，避免更早的「告诉我」长期误武装。"""
    if not recent:
        return False
    last_qi: str | None = None
    for msg in reversed(recent):
        role = str(msg.get("role") or "")
        if role in ("qi", "assistant"):
            last_qi = str(msg.get("content") or "")
            break
    if not last_qi:
        return False
    if _qi_asking_user_name(last_qi):
        return True
    if any(cue in last_qi for cue in _QI_NAME_INVITE_CUES):
        return True
    if re.search(r"(名字|怎么称呼|叫什么)", last_qi) and any(
        x in last_qi for x in ("告诉", "说", "听")
    ):
        return True
    return False


def _last_qi_asked_user_name(recent: list[dict] | None) -> bool:
    if not recent:
        return False
    for msg in reversed(recent):
        role = str(msg.get("role") or "")
        if role in ("qi", "assistant"):
            return _qi_asking_user_name(str(msg.get("content") or ""))
    return False


def _user_recently_disclosed_name_intent(recent: list[dict] | None) -> bool:
    if not recent:
        return False
    for msg in reversed(recent[-4:]):
        if str(msg.get("role") or "") != "user":
            continue
        if is_name_disclosure_intent(str(msg.get("content") or "")):
            return True
    return False


def _normalize_fact_text(text: str) -> str:
    t = text.strip()
    for prefix in ("他", "她", "你"):
        if t.startswith(prefix):
            t = t[len(prefix) :]
    t = re.sub(r"\s+", "", t)
    return t


def _token_set(text: str) -> set[str]:
    """中文按字 + 连续数字/字母片段。"""
    norm = _normalize_fact_text(text)
    chars = set(norm)
    for m in re.finditer(r"[A-Za-z0-9]+", norm):
        chars.add(m.group(0).lower())
    return chars


def content_similarity(a: str, b: str) -> float:
    """同 type 下去重用的轻量相似度（不接向量库）。"""
    na, nb = _normalize_fact_text(a), _normalize_fact_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    sa, sb = _token_set(a), _token_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


class FactStore:
    """user_facts 存取：active / 新增 / 确认 / 取代 / 相似查找。"""

    def __init__(self, db: Database):
        self.db = db

    async def active_facts(self, fact_type: str | None = None) -> list[dict]:
        return await self.db.list_active_user_facts(fact_type)

    async def add(
        self,
        fact_type: str,
        content: str,
        confidence: float,
        stability: str,
        source: str | None,
        emotional_weight: float,
        now: datetime,
    ) -> int:
        return await self.db.insert_user_fact(
            fact_type,
            content,
            confidence,
            stability,
            source,
            emotional_weight,
            now=now,
        )

    async def confirm(self, fact_id: int, now: datetime) -> None:
        await self.db.confirm_user_fact(fact_id, now=now)

    async def supersede(self, old_id: int, new_id: int) -> None:
        await self.db.supersede_user_fact(old_id, new_id)

    async def retire(self, fact_id: int) -> None:
        """作废一条事实（不指向继任者）：superseded_by = 自身。"""
        await self.db.supersede_user_fact(fact_id, fact_id)

    async def find_similar(self, fact_type: str, content: str) -> dict | None:
        """在 active 同 type 里找最像的一条；不够像则 None。"""
        best: dict | None = None
        best_score = 0.0
        for row in await self.active_facts(fact_type):
            score = content_similarity(content, str(row.get("content") or ""))
            if score > best_score:
                best_score = score
                best = row
        if best is not None and best_score >= _SIMILARITY_CONFIRM:
            return best
        return None

    async def find_active_of_type(self, fact_type: str) -> dict | None:
        """同 type 下任意一条 active（state 取代时用）。"""
        rows = await self.active_facts(fact_type)
        return rows[0] if rows else None


class FactNoticer:
    """在收到用户消息的当下留意事实（非定期回顾）。"""

    def __init__(self, store: FactStore, llm: LLMGateway | None = None):
        self.store = store
        self.llm = llm
        # 进程内短状态：邀名后等待光给名字（重启清空，可接受）
        self._awaiting_name_until: datetime | None = None
        self._awaiting_name_turns_left: int = 0

    def _arm_awaiting_name(self, now: datetime) -> None:
        from datetime import timedelta

        self._awaiting_name_until = now + timedelta(seconds=_AWAITING_NAME_SECONDS)
        self._awaiting_name_turns_left = _AWAITING_NAME_USER_LIMIT

    def _clear_awaiting_name(self) -> None:
        self._awaiting_name_until = None
        self._awaiting_name_turns_left = 0

    def _awaiting_name_active(self, now: datetime) -> bool:
        if self._awaiting_name_turns_left <= 0:
            return False
        if self._awaiting_name_until is None:
            return False
        if now > self._awaiting_name_until:
            self._clear_awaiting_name()
            return False
        return True

    def _tick_awaiting_name(self, now: datetime) -> None:
        """每条用户消息消耗一拍等待额度。"""
        if not self._awaiting_name_active(now):
            return
        self._awaiting_name_turns_left -= 1
        if self._awaiting_name_turns_left <= 0:
            self._clear_awaiting_name()

    async def notice(
        self,
        message: str,
        emotion: EmotionState,
        relationship_stage: str,
        now: datetime | None = None,
        recent_messages: list[dict] | None = None,
    ) -> list[dict]:
        """
        返回本拍新记下 / 确认 / 取代的事实摘要列表。

        recent_messages：当前句尚未入工作记忆前的近期对话（含 user / qi），
        用于邀名与多拍「光给名字」上下文。
        """
        now = now or datetime.now()
        text = (message or "").strip()
        if not text:
            return []

        results: list[dict] = []
        if any(s in text for s in _CORRECTION_SIGNALS):
            results.extend(
                await self._notice_corrections(text, relationship_stage, now)
            )

        # 问「记得名字吗」：绝不抽取；也不武装 awaiting
        memory_q = is_name_memory_question(text)
        armed_this_turn = False
        if not memory_q and is_name_disclosure_intent(text):
            self._arm_awaiting_name(now)
            armed_this_turn = True
        elif not memory_q and _last_qi_asked_user_name(recent_messages):
            # 栖刚问「你叫什么名字」→ 下一拍光给名字应能落库
            if not self._awaiting_name_active(now):
                self._arm_awaiting_name(now)
                armed_this_turn = True
        elif not memory_q and _user_recently_disclosed_name_intent(
            recent_messages
        ) and _qi_recently_invited_name(recent_messages):
            # 用户已表态要说名字、栖刚邀名：补武装（防中间空拍把等待耗尽）
            if not self._awaiting_name_active(now):
                self._arm_awaiting_name(now)
                armed_this_turn = True

        drafts: list[dict] = []
        if not memory_q:
            drafts = self._rule_extract(text, relationship_stage)
            # 待名状态下的光给名字
            if self._awaiting_name_active(now) and is_bare_name_utterance(text):
                bare = re.sub(
                    r"^[「『\"'（(]+|[」』\"'）)。.!！？?…]+$", "", text.strip()
                ).strip()
                if looks_like_person_name(bare):
                    drafts.append(
                        {
                            "fact_type": "identity",
                            "content": f"他叫{bare}",
                            "confidence": 0.93,
                            "stability": "stable",
                            "emotional_weight": 0.85,
                            "source": "他在被问起或表示要告诉名字后说的",
                            "force_supersede_type": True,
                        }
                    )
            if not drafts and self._needs_llm(text, relationship_stage):
                drafts = await self._llm_extract(text, emotion, relationship_stage)

        landed_identity = False
        for draft in drafts:
            conf = float(draft.get("confidence") or 0.0)
            if conf < CONFIDENCE_FLOOR:
                continue
            applied = await self._land(draft, text, now)
            if applied:
                results.append(applied)
                if applied.get("fact_type") == "identity":
                    landed_identity = True
                    self._clear_awaiting_name()

        # 消耗等待：本拍刚武装或已落库则不扣
        if (
            not armed_this_turn
            and not landed_identity
            and self._awaiting_name_active(now)
        ):
            self._tick_awaiting_name(now)

        await self._purge_bogus_identity(
            now,
            keep_ids={int(r["id"]) for r in results if r.get("fact_type") == "identity"},
        )

        return results

    async def _purge_bogus_identity(
        self, now: datetime, keep_ids: set[int] | None = None
    ) -> None:
        """作废人名门控失败的 active identity（如「他叫吗」），不硬删。"""
        del now  # 保留签名与调用一致；作废不依赖时钟
        keep_ids = keep_ids or set()
        actives = await self.store.active_facts("identity")
        good = next(
            (
                row
                for row in actives
                if looks_like_person_name(
                    identity_name_fragment(str(row.get("content") or "")) or ""
                )
            ),
            None,
        )
        for row in actives:
            rid = int(row["id"])
            if rid in keep_ids:
                continue
            frag = identity_name_fragment(str(row.get("content") or ""))
            if frag is not None and looks_like_person_name(frag):
                continue
            if frag is None:
                # 无法解析出名字的 identity 也不该占 active（清理占位污染）
                content = str(row.get("content") or "")
                if content.startswith(("他叫", "他姓", "他希望被叫做")):
                    pass  # 解析失败仍视为非法
                else:
                    continue
            if good is not None and rid != int(good["id"]):
                await self.store.supersede(rid, int(good["id"]))
            else:
                await self.store.retire(rid)

    async def _notice_corrections(
        self, text: str, stage: str, now: datetime
    ) -> list[dict]:
        """识别更正 → 定位 active → supersede 再记新。"""
        out: list[dict] = []

        # 我不叫小明，我叫小红
        m = re.search(
            r"我不叫\s*([^\s，。！？,.!?]{1,20})[，,]?\s*"
            r"(?:我叫|叫)\s*([^\s，。！？,.!?]{1,20})",
            text,
        )
        if m:
            old_hint = m.group(1).strip("的了啊呀呢吧")
            new_name = m.group(2).strip("的了啊呀呢吧")
            if new_name and looks_like_person_name(new_name):
                applied = await self._correct_identity(
                    f"他叫{new_name}",
                    text,
                    now,
                    old_hint=old_hint,
                )
                if applied:
                    out.append(applied)
                return out

        # 其实是小红 / 其实叫小红 / 其实我叫小红
        m = re.search(
            r"其实(?:是|叫|我叫)\s*([^\s，。！？,.!?]{1,20})",
            text,
        )
        if m:
            new_name = m.group(1).strip("的了啊呀呢吧")
            if new_name and looks_like_person_name(new_name):
                applied = await self._correct_identity(
                    f"他叫{new_name}", text, now
                )
                if applied:
                    out.append(applied)
                return out

        # 不是小明，是小红
        m = re.search(
            r"不是\s*([^\s，。！？,.!?]{1,20})[，,]?\s*是\s*([^\s，。！？,.!?]{1,20})",
            text,
        )
        if m:
            old_hint = m.group(1).strip("的了啊呀呢吧")
            new_val = m.group(2).strip("的了啊呀呢吧")
            if old_hint and new_val:
                applied = await self._correct_not_but(old_hint, new_val, text, now, stage)
                if applied:
                    out.append(applied)
                return out

        # 我现在不在甲公司了 / 我现在不住上海了
        if stage_at_least(stage, "acquaintance"):
            m = re.search(
                r"我现在不(?:在|住(?:在)?)?\s*([^\s，。！？,.!?]{1,20})(?:了|啦|啊)?",
                text,
            )
            if m and "我现在不" in text:
                fragment = m.group(1).strip("的了啊呀呢吧")
                if fragment and fragment not in ("想", "说", "知道"):
                    applied = await self._correct_state_away(fragment, text, now)
                    if applied:
                        out.append(applied)

        return out

    async def _correct_identity(
        self,
        content: str,
        original: str,
        now: datetime,
        *,
        old_hint: str | None = None,
    ) -> dict | None:
        old = await self._find_identity_to_correct(old_hint)
        similar = await self.store.find_similar("identity", content)
        if similar is not None:
            await self.store.confirm(int(similar["id"]), now)
            if old is not None and int(old["id"]) != int(similar["id"]):
                await self.store.supersede(int(old["id"]), int(similar["id"]))
                return {
                    "action": "supersede",
                    "id": int(similar["id"]),
                    "old_id": int(old["id"]),
                    "fact_type": "identity",
                    "content": similar.get("content"),
                }
            return {
                "action": "confirm",
                "id": int(similar["id"]),
                "fact_type": "identity",
                "content": similar.get("content"),
            }

        new_id = await self.store.add(
            "identity",
            content,
            0.95,
            "stable",
            "他纠正名字时说的",
            0.85,
            now,
        )
        if old is not None:
            await self.store.supersede(int(old["id"]), new_id)
            return {
                "action": "supersede",
                "id": new_id,
                "old_id": int(old["id"]),
                "fact_type": "identity",
                "content": content,
            }
        return {
            "action": "add",
            "id": new_id,
            "fact_type": "identity",
            "content": content,
        }

    async def _find_identity_to_correct(self, old_hint: str | None) -> dict | None:
        if old_hint:
            for row in await self.store.active_facts("identity"):
                if old_hint in str(row.get("content") or ""):
                    return row
        return await self.store.find_active_of_type("identity")

    async def _correct_not_but(
        self,
        old_hint: str,
        new_val: str,
        text: str,
        now: datetime,
        stage: str,
    ) -> dict | None:
        # 优先对上 identity
        for row in await self.store.active_facts("identity"):
            if old_hint in str(row.get("content") or ""):
                if not looks_like_person_name(new_val):
                    return None
                return await self._correct_identity(
                    f"他叫{new_val}", text, now, old_hint=old_hint
                )

        if not stage_at_least(stage, "acquaintance"):
            return None

        for ftype, tmpl in (
            ("occupation", "他在{val}"),
            ("location", "他在{val}"),
            ("preference", "他喜欢{val}"),
        ):
            for row in await self.store.active_facts(ftype):
                if old_hint in str(row.get("content") or ""):
                    content = tmpl.format(val=new_val)
                    return await self._supersede_existing(
                        row,
                        ftype,
                        content,
                        now,
                        source="他纠正时说的",
                        stability=default_stability(ftype),
                        weight=0.7,
                    )
        return None

    async def _correct_state_away(
        self, fragment: str, text: str, now: datetime
    ) -> dict | None:
        for ftype, content in (
            ("occupation", f"他不再在{fragment}"),
            ("location", f"他不在{fragment}了"),
        ):
            for row in await self.store.active_facts(ftype):
                if fragment in str(row.get("content") or ""):
                    return await self._supersede_existing(
                        row,
                        ftype,
                        content,
                        now,
                        source="他说自己情况变了时",
                        stability="state",
                        weight=0.65,
                    )
        # 无精确命中：occupation 用 find_active_of_type 兜底（「我现在不……」常指工作）
        if "工作" in text or "公司" in fragment or "上班" in text:
            old = await self.store.find_active_of_type("occupation")
            if old is not None:
                return await self._supersede_existing(
                    old,
                    "occupation",
                    f"他不再在{fragment}",
                    now,
                    source="他说自己情况变了时",
                    stability="state",
                    weight=0.65,
                )
        return None

    async def _supersede_existing(
        self,
        old: dict,
        fact_type: str,
        content: str,
        now: datetime,
        *,
        source: str,
        stability: str,
        weight: float,
        confidence: float = 0.92,
    ) -> dict:
        similar = await self.store.find_similar(fact_type, content)
        if similar is not None:
            await self.store.confirm(int(similar["id"]), now)
            if int(old["id"]) != int(similar["id"]):
                await self.store.supersede(int(old["id"]), int(similar["id"]))
                return {
                    "action": "supersede",
                    "id": int(similar["id"]),
                    "old_id": int(old["id"]),
                    "fact_type": fact_type,
                    "content": similar.get("content"),
                }
            return {
                "action": "confirm",
                "id": int(similar["id"]),
                "fact_type": fact_type,
                "content": similar.get("content"),
            }

        new_id = await self.store.add(
            fact_type,
            content,
            confidence,
            stability,
            source,
            weight,
            now,
        )
        await self.store.supersede(int(old["id"]), new_id)
        return {
            "action": "supersede",
            "id": new_id,
            "old_id": int(old["id"]),
            "fact_type": fact_type,
            "content": content,
        }

    def _needs_llm(self, text: str, stage: str) -> bool:
        if self.llm is None:
            return False
        if any(s in text for s in IDENTITY_SIGNALS):
            return False  # 身份走规则；规则抽空也不滥调 LLM
        if not stage_at_least(stage, "acquaintance"):
            return False
        return any(s in text for s in OTHER_FACT_SIGNALS)

    def _rule_extract(self, text: str, stage: str) -> list[dict]:
        out: list[dict] = []

        if any(s in text for s in IDENTITY_SIGNALS):
            out.extend(self._extract_identity(text))

        if stage_at_least(stage, "acquaintance"):
            out.extend(self._extract_other_rules(text))

        return out

    def _extract_identity(self, text: str) -> list[dict]:
        # 「我的名字」必须跟 是/叫，避免「我的名字吗」吞进「吗」
        patterns: list[tuple[str, str]] = [
            (r"你可以叫我\s*([^\s，。！？,.!?]{1,20})", "他希望被叫做{name}"),
            (r"称呼我\s*([^\s，。！？,.!?]{1,20})", "他希望被叫做{name}"),
            (r"叫我\s*([^\s，。！？,.!?]{1,20})", "他希望被叫做{name}"),
            (r"我的名字(?:是|叫)\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
            (r"我名字(?:是|叫)\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
            (r"我大名(?:是|叫)\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
            (r"我小名(?:是|叫)\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
            (r"我英文名(?:是|叫)\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
            (r"我姓\s*([^\s，。！？,.!?]{1,10})", "他姓{name}"),
            (r"我叫\s*([^\s，。！？,.!?]{1,20})", "他叫{name}"),
        ]
        found: list[dict] = []
        seen: set[str] = set()
        for pat, tmpl in patterns:
            m = re.search(pat, text)
            if not m:
                continue
            name = m.group(1).strip("的了啊呀呢吧")
            if not name or name in seen:
                continue
            if not looks_like_person_name(name):
                continue
            if any(x in name for x in ("你别", "一声")):
                continue
            seen.add(name)
            content = tmpl.format(name=name)
            found.append(
                {
                    "fact_type": "identity",
                    "content": content,
                    "confidence": 0.95,
                    "stability": "stable",
                    "emotional_weight": 0.85,
                    "source": "他介绍自己时说的",
                    "force_supersede_type": True,
                }
            )
        return found

    def _extract_other_rules(self, text: str) -> list[dict]:
        found: list[dict] = []

        # 换工作 / 状态变更（扩展信号，见文档回写）
        if any(s in text for s in _OCCUPATION_CHANGE_SIGNALS):
            found.append(
                {
                    "fact_type": "occupation",
                    "content": "他换了工作",
                    "confidence": 0.9,
                    "stability": "state",
                    "emotional_weight": 0.7,
                    "source": "他说自己换工作时",
                    "force_supersede_type": True,
                }
            )

        m = re.search(
            r"我(?:现在)?(?:在|于)\s*([^\s，。！？,.!?]{1,20}?)(?:工作|上班|任职)",
            text,
        )
        if m:
            place = m.group(1).strip()
            if place and place not in ("想", "说", "看", "听", "忙"):
                found.append(
                    {
                        "fact_type": "occupation",
                        "content": f"他在{place}工作",
                        "confidence": 0.9,
                        "stability": "state",
                        "emotional_weight": 0.65,
                        "source": "他说起工作时",
                        "force_supersede_type": True,
                    }
                )

        m = re.search(r"我是做\s*([^\s，。！？,.!?]{1,20})", text)
        if m:
            found.append(
                {
                    "fact_type": "occupation",
                    "content": f"他是做{m.group(1).strip()}的",
                    "confidence": 0.9,
                    "stability": "state",
                    "emotional_weight": 0.65,
                    "source": "他说起工作时",
                    "force_supersede_type": True,
                }
            )

        # 地点：我家在 / 我住 / 我在上海（排除我在想/说/看…）
        m = re.search(r"我家在\s*([^\s，。！？,.!?]{1,20})", text)
        if m:
            found.append(
                {
                    "fact_type": "location",
                    "content": f"他家在{m.group(1).strip()}",
                    "confidence": 0.9,
                    "stability": "state",
                    "emotional_weight": 0.6,
                    "source": "他说起住处时",
                    "force_supersede_type": True,
                }
            )
        m = re.search(r"我住(?:在)?\s*([^\s，。！？,.!?]{1,20})", text)
        if m:
            found.append(
                {
                    "fact_type": "location",
                    "content": f"他住在{m.group(1).strip()}",
                    "confidence": 0.9,
                    "stability": "state",
                    "emotional_weight": 0.6,
                    "source": "他说起住处时",
                    "force_supersede_type": True,
                }
            )
        m = re.search(
            r"我在(?!想|说|看|听|做|忙|这|那|这儿|那儿|这里|那里)"
            r"([^\s，。！？,.!?]{1,12})(?:[，。！？\s]|$)",
            text,
        )
        if m and not any(s in text for s in _OCCUPATION_CHANGE_SIGNALS):
            city = m.group(1).strip()
            if city and "工作" not in city:
                found.append(
                    {
                        "fact_type": "location",
                        "content": f"他在{city}",
                        "confidence": 0.85,
                        "stability": "state",
                        "emotional_weight": 0.55,
                        "source": "他说起所在地时",
                        "force_supersede_type": True,
                    }
                )

        for cue, label in (
            ("我妈", "他的妈妈"),
            ("我爸", "他的爸爸"),
            ("我老婆", "他的妻子"),
            ("我老公", "他的丈夫"),
            ("我女朋友", "他的女朋友"),
            ("我男朋友", "他的男朋友"),
            ("我儿子", "他的儿子"),
            ("我女儿", "他的女儿"),
            ("我孩子", "他的孩子"),
        ):
            if cue in text:
                # 「我妈叫X」
                mm = re.search(rf"{cue}(?:叫|是)\s*([^\s，。！？,.!?]{{1,20}})", text)
                if mm:
                    found.append(
                        {
                            "fact_type": "family",
                            "content": f"{label}叫{mm.group(1).strip()}",
                            "confidence": 0.92,
                            "stability": "stable",
                            "emotional_weight": 0.75,
                            "source": "他说起家人时",
                        }
                    )
                else:
                    found.append(
                        {
                            "fact_type": "family",
                            "content": f"他提到了{label}",
                            "confidence": 0.8,
                            "stability": "stable",
                            "emotional_weight": 0.55,
                            "source": "他说起家人时",
                        }
                    )

        m = re.search(r"我喜欢\s*([^\s，。！？,.!?]{1,20})", text)
        if m:
            found.append(
                {
                    "fact_type": "preference",
                    "content": f"他喜欢{m.group(1).strip()}",
                    "confidence": 0.88,
                    "stability": "stable",
                    "emotional_weight": 0.55,
                    "source": "他说起喜好时",
                }
            )
        m = re.search(r"我讨厌\s*([^\s，。！？,.!?]{1,20})", text)
        if m:
            found.append(
                {
                    "fact_type": "preference",
                    "content": f"他讨厌{m.group(1).strip()}",
                    "confidence": 0.88,
                    "stability": "stable",
                    "emotional_weight": 0.55,
                    "source": "他说起好恶时",
                }
            )

        return found

    async def _llm_extract(
        self,
        text: str,
        emotion: EmotionState,
        stage: str,
    ) -> list[dict]:
        if self.llm is None:
            return []
        from qi.prompts import read_prompt

        try:
            template = read_prompt("fact_noticing.txt")
        except Exception:
            template = (
                "从用户的话里抽出关于用户自己的事实，用「他……」第三人称。"
                "JSON 数组，每项含 fact_type/content/confidence/stability。"
                "没有就返回 []。\n用户说：{message}\n关系阶段：{stage}\n情绪：{emotion}"
            )
        prompt = template.format(
            message=text,
            stage=stage,
            emotion=emotion.description() if hasattr(emotion, "description") else "",
        )
        raw = await self.llm.call(
            purpose="fact",
            messages=[
                {
                    "role": "system",
                    "content": "你只抽取事实，输出 JSON 数组，不要解释。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return _parse_llm_facts(raw or "")

    async def _land(
        self, draft: dict, original_message: str, now: datetime
    ) -> dict | None:
        fact_type = str(draft.get("fact_type") or "other")
        content = str(draft.get("content") or "").strip()
        if not content:
            return None
        confidence = float(draft.get("confidence") or 0.0)
        if confidence < CONFIDENCE_FLOOR:
            return None
        stability = str(draft.get("stability") or default_stability(fact_type))
        source = draft.get("source") or f"他说：「{original_message[:40]}」"
        weight = float(draft.get("emotional_weight") or 0.5)
        force_type = bool(draft.get("force_supersede_type"))

        similar = await self.store.find_similar(fact_type, content)
        if similar is not None:
            await self.store.confirm(int(similar["id"]), now)
            return {
                "action": "confirm",
                "id": int(similar["id"]),
                "fact_type": fact_type,
                "content": similar.get("content"),
            }

        # 先定位旧 active（find_active_of_type），再插入新行，避免把新行当成旧行
        old: dict | None = None
        if stability == "state" or force_type:
            old = await self.store.find_active_of_type(fact_type)

        new_id = await self.store.add(
            fact_type,
            content,
            confidence,
            stability,
            source if isinstance(source, str) else None,
            weight,
            now,
        )

        if old is not None:
            score = content_similarity(content, str(old.get("content") or ""))
            if force_type or score < _SIMILARITY_CONFIRM:
                await self.store.supersede(int(old["id"]), new_id)
                return {
                    "action": "supersede",
                    "id": new_id,
                    "old_id": int(old["id"]),
                    "fact_type": fact_type,
                    "content": content,
                }

        return {
            "action": "add",
            "id": new_id,
            "fact_type": fact_type,
            "content": content,
        }


def _parse_llm_facts(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        return []
    # 允许模型包在 ```json 里
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试截取第一个数组
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            logger.warning("fact LLM 返回无法解析: %s", raw[:200])
            return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        ftype = str(item.get("fact_type") or "other")
        conf = float(item.get("confidence") or 0.0)
        stab = str(item.get("stability") or default_stability(ftype))
        out.append(
            {
                "fact_type": ftype,
                "content": content,
                "confidence": conf,
                "stability": stab,
                "emotional_weight": float(item.get("emotional_weight") or 0.5),
                "source": item.get("source"),
            }
        )
    return out


# 供测试与外部引用
__all__ = [
    "CONFIDENCE_FLOOR",
    "IDENTITY_SIGNALS",
    "OTHER_FACT_SIGNALS",
    "FactNoticer",
    "FactStore",
    "content_similarity",
    "default_stability",
    "format_facts_for_prompt",
    "is_bare_name_utterance",
    "is_name_disclosure_intent",
    "is_name_memory_question",
    "looks_like_person_name",
    "stage_at_least",
]
