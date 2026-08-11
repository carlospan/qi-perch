"""叙事编织后的方向消毒——对照 role_map，纠人称/施事织反（非文案墙）。"""

from __future__ import annotations

import re
from typing import Any

# 用户原话：把栖当女生 / 希望栖是女生（用户视角「你」=栖）
_USER_QI_AS_FEMALE = re.compile(
    r"把你当女生|把你当女孩|希望你是女生|希望你是女(?:孩|生|的)?"
)

# 织文脏句：栖第一人称里变成「我把你（用户）当女生」
_DIRTY_QI_USER_AS_FEMALE = (
    ("又说我总把你当女生", "又说你一直把我当女生"),
    ("说我总把你当女生", "说你一直把我当女生"),
    ("我总把你当女生", "你一直把我当女生"),
    ("我把你当女生", "你把我当女生"),
    ("总把你当女孩", "一直把我当女孩"),
)

# 用户承认「你（栖）教了我」或栖侧「我教了」→ 施教方向 taught_by_qi
_USER_ACK_QI_TAUGHT = re.compile(
    r"你教了我|你教过我|你教的(?:那个)?(?:法子|方法)?|是你教"
)
_QI_SAID_TAUGHT = re.compile(r"我教了|我教过|教了你|教过你|教给你")

# 织文里把「栖教用户」说反
_TEACH_INVERT_FIXES = (
    ("你教给我那个方法", "我教给你那个方法"),
    ("你教给我", "我教给你"),
    ("你教给了我", "我教给了你"),
    ("你之前教过我", "我之前教过你"),
    ("你教过我", "我教过你"),
    ("你教我的那个方法", "我教你的那个方法"),
    ("你教我的方法", "我教你的方法"),
    ("你教的方法", "我教的方法"),
    ("你教的法子", "我教的法子"),
)

# 归因主语：避开「听你说话 / 让我说」这类复合词里的假「你说/我说」
_ATTR_SUBJECT_LOOKBEHIND = r"(?<![听看让对跟和给把被向])"
# 第一人称回忆里，把「说话/写/发」归因给用户（你…）
# 覆盖「你断断续续发了几条消息，说…」；间隙不得跨过另一人称，避免「我记得那天你说」误匹配成「我说」
_ATTR_GAP = r"(?:[^。！？\n，,我你说写发问]{0,12})"
_ATTR_TO_USER_RE = re.compile(
    _ATTR_SUBJECT_LOOKBEHIND
    + r"你"
    r"(?:"
    r"(?:" + _ATTR_GAP + r")?发(?:过|了)(?:几条)?(?:消息)?[，,]说(?:过|了)?"
    r"|(?:又|还|就|也|曾经|那天|那晚|之前)?"
    r"(?:"
    r"说(?:过|了)?(?![错对得完话])"
    r"|写(?:过|了|道)?(?=[\u4e00-\u9fff「『\"“])"
    r"|告诉我"
    r"|跟我说"
    r")"
    r")"
)

# 第一人称回忆里，把「说话/写/发」归因给自己（我…）
_ATTR_TO_SELF_RE = re.compile(
    _ATTR_SUBJECT_LOOKBEHIND
    + r"我"
    r"(?:"
    r"(?:" + _ATTR_GAP + r")?发(?:过|了)(?:几条)?(?:消息)?[，,]说(?:过|了)?"
    r"|(?:又|还|就|也|曾经|那天|那晚|之前)?"
    r"(?:"
    r"说(?:过|了)?(?![错对得完话])"
    r"|写(?:过|了|道)?(?=[\u4e00-\u9fff「『\"“])"
    r"|告诉你"
    r"|跟你说"
    r")"
    r")"
)

_PUNCT_RE = re.compile(
    r"[\s，。！？、…\.\!\?\,;；:：\"\"\"\'「」『』\(\)（）\[\]【】—–―\-]"
)
# 引号内常是转述对方的话（尤其 [想过] 里嵌用户原话）——比对归属时剥掉，避免独占误判
_QUOTE_SPAN_RE = re.compile(r"[「『\"“][^」』\"”]{1,40}[」』\"”]")


def _normalize_for_match(s: str) -> str:
    t = _PUNCT_RE.sub("", s or "")
    # 给你/给我在分享句里常被织反，比对时视为同一方向占位
    t = t.replace("给我", "给X").replace("给你", "给X")
    # 「写了个东西」vs「写了东西」——量词不参与归属指纹
    return t.replace("个", "")


def _ownership_text(s: str) -> str:
    """归属比对用正文：去掉引号与「你说…」转述，降低栖复述污染 qi_said。"""
    text = _QUOTE_SPAN_RE.sub("", s or "")
    # 栖侧常有「你说下班了…」——那是复述用户，不能算栖独占原话
    text = re.sub(
        r"你(?:说|问|提到)(?:过|了)?[^。！？\n]{0,48}",
        "",
        text,
    )
    return text


def _strong_overlap(needle: str, haystacks: list[str]) -> bool:
    """强重合：归一化后互为子串、前缀，或任意连续 4 字落在对方原话里。

    不用松散 Jaccard——短句乱撞会误伤正确「我说…」自述。
    窗口取 4：分享句常被织成删字版，中间还可能被「很短」等插入隔开。
    """
    nn = _normalize_for_match(needle)
    if len(nn) < 4:
        return False
    core = re.sub(r"^[我你他她它]+", "", nn)
    for h in haystacks:
        hn = _normalize_for_match(h)
        if not hn:
            continue
        if nn in hn or hn in nn:
            return True
        if len(nn) >= 4 and nn[:4] in hn:
            return True
        if len(hn) >= 4 and hn[:4] in nn:
            return True
        if len(core) >= 4 and core in hn:
            return True
        window = 4
        if len(nn) >= window:
            for i in range(len(nn) - window + 1):
                if nn[i : i + window] in hn:
                    return True
        if len(core) >= window and core != nn:
            for i in range(len(core) - window + 1):
                if core[i : i + window] in hn:
                    return True
    return False


def _flip_attr_you_to_i(match: re.Match[str]) -> str:
    """你…说/写/发 → 我说/我写；发消息赘语收成「说」。"""
    full = match.group(0)
    if re.search(r"发(?:过|了).{0,16}说", full):
        verb_m = re.search(r"说(?:过|了)?$", full)
        verb = verb_m.group(0) if verb_m else "说"
        return "我" + verb
    rest = full[1:]
    rest = rest.replace("告诉我", "告诉你", 1).replace("跟我说", "跟你说", 1)
    return "我" + rest


def _flip_attr_i_to_you(match: re.Match[str]) -> str:
    """我…说/写 → 你说/你写（用户原话被织成栖自述时）。"""
    full = match.group(0)
    if re.search(r"发(?:过|了).{0,16}说", full):
        verb_m = re.search(r"说(?:过|了)?$", full)
        verb = verb_m.group(0) if verb_m else "说"
        return "你" + verb
    rest = full[1:]
    rest = rest.replace("告诉你", "告诉我", 1).replace("跟你说", "跟我说", 1)
    return "你" + rest


def _flip_give_pronouns(sentence: str, *, qi_blob: str, user_blob: str) -> str:
    """分享方向「给你/给我」随说话人翻转时一并纠正。"""
    if "给你" in qi_blob and "给我" in sentence:
        return sentence.replace("给我", "给你", 1)
    if "给我" in qi_blob and "给你" in sentence:
        return sentence.replace("给你", "给我", 1)
    if "给我" in user_blob and "给你" in sentence:
        return sentence.replace("给你", "给我", 1)
    if "给你" in user_blob and "给我" in sentence:
        return sentence.replace("给我", "给你", 1)
    return sentence


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\n])", text)
    return [p for p in parts if p]


def _attributed_content(sentence: str, match: re.Match[str]) -> str:
    """取归因动词之后的内容从句。

    优先取紧跟的引号内容；否则只取到下一处逗号/句号，
    避免把同句后半段栖自己的话卷进比对（「你又说『下班了』，我愣着…」）。
    """
    after = sentence[match.end() :]
    qm = re.match(r'\s*[「『"“]([^」』"”]+)[」』"”]', after)
    if qm:
        return qm.group(1).strip()
    cut = re.search(r"[。！？\n，,；;]", after)
    content = after[: cut.start()] if cut else after
    return re.sub(r'^[\s「」『』"\']+|[\s「」『』"\']+$', "", content)[:48]


def _content_matches_side(
    content: str,
    own: list[str],
    other: list[str],
    *,
    min_len: int = 4,
) -> bool:
    """归因从句是否只落在 own 侧原话上（强子串；两侧都有或不确定则不动）。

    own/other 会先剥引号片段再比对，避免栖侧 [想过] 嵌套用户原话导致误翻。
    """
    cn = _normalize_for_match(content)
    if len(cn) < min_len:
        return False
    own_corp = [_ownership_text(x) for x in own]
    other_corp = [_ownership_text(x) for x in other]
    # 剥引号后为空的条目不参与（整句都是引语时无法独占归属）
    own_corp = [x for x in own_corp if _normalize_for_match(x)]
    other_corp = [x for x in other_corp if _normalize_for_match(x)]
    if _strong_overlap(content, other_corp):
        return False
    return _strong_overlap(content, own_corp)


def first_person_sketch_from_role_map(role_map: dict[str, Any] | None) -> str:
    """role_map 保真草稿：说话人不可反，供消毒失败时落盘。"""
    if not role_map:
        return ""
    bits: list[str] = []
    for t in role_map.get("turns") or []:
        text = str(t.get("text") or "").strip()
        if not text:
            continue
        if t.get("speaker") == "user":
            bits.append(f"你说「{text}」")
        else:
            bits.append(f"我说「{text}」")
    if not bits:
        return ""
    body = "。".join(bits)
    if not body.endswith(("。", "！", "？")):
        body += "。"
    return body


def _qi_owns_as_speaker(content: str, qi_said: list[str], user_said: list[str]) -> bool:
    """内容是否属于栖自己说出口的话（不是复述用户）。

    要求：强重合到某条栖原话，且该原话去转述后仍以「我」起首，或带明确「给你」给出。
    """
    if _strong_overlap(content, [_ownership_text(u) for u in user_said]):
        return False
    for q in qi_said:
        own = _ownership_text(q)
        if not own or not _strong_overlap(content, [own]):
            continue
        raw = (q or "").strip()
        qn = _normalize_for_match(own)
        if raw.startswith("我") or qn.startswith("我"):
            return True
        if "给你" in raw or "给X" in qn:
            return True
    return False


def detect_speaker_inversion(woven: str, role_map: dict[str, Any] | None) -> bool:
    """织文是否仍把一侧独有原话安到另一侧头上。"""
    if not woven or not role_map:
        return False
    user_said = [str(x) for x in (role_map.get("user_said") or [])]
    qi_said = [str(x) for x in (role_map.get("qi_said") or [])]
    if not user_said and not qi_said:
        return False

    for sent in _split_sentences(woven):
        for m in _ATTR_TO_USER_RE.finditer(sent):
            content = _attributed_content(sent, m)
            if _qi_owns_as_speaker(content, qi_said, user_said):
                return True
        for m in _ATTR_TO_SELF_RE.finditer(sent):
            content = _attributed_content(sent, m)
            if _content_matches_side(content, user_said, qi_said):
                return True
    return False


def _rewrite_speaker_attribution(
    text: str, role_map: dict[str, Any]
) -> tuple[str, list[str]]:
    """对照 qi_said/user_said，把说错主体的归因句改回。"""
    user_said = [str(x) for x in (role_map.get("user_said") or [])]
    qi_said = [str(x) for x in (role_map.get("qi_said") or [])]
    qi_blob = "\n".join(qi_said)
    user_blob = "\n".join(user_said)
    tags: list[str] = []
    out: list[str] = []

    for sent in _split_sentences(text):
        fixed = sent
        # 从右往左替换，避免偏移；每处只在「从句内容」确属另一侧时翻
        matches = list(_ATTR_TO_USER_RE.finditer(fixed))
        for m in reversed(matches):
            content = _attributed_content(fixed, m)
            if not _qi_owns_as_speaker(content, qi_said, user_said):
                continue
            flipped = _flip_attr_you_to_i(m)
            fixed = fixed[: m.start()] + flipped + fixed[m.end() :]
            fixed = _flip_give_pronouns(fixed, qi_blob=qi_blob, user_blob=user_blob)
            tags.append("speaker_direction")

        matches = list(_ATTR_TO_SELF_RE.finditer(fixed))
        for m in reversed(matches):
            content = _attributed_content(fixed, m)
            if not _content_matches_side(content, user_said, qi_said):
                continue
            flipped = _flip_attr_i_to_you(m)
            fixed = fixed[: m.start()] + flipped + fixed[m.end() :]
            fixed = _flip_give_pronouns(fixed, qi_blob=qi_blob, user_blob=user_blob)
            tags.append("speaker_direction")

        out.append(fixed)

    return "".join(out), tags


def sanitize_woven_narrative(
    woven: str, role_map: dict[str, Any] | None
) -> tuple[str, list[str]]:
    """对照 role_map 做确定性替换；返回 (正文, 修复标签列表)。"""
    text = str(woven or "")
    if not text or not role_map:
        return text, []

    tags: list[str] = []
    user_blob = "\n".join(str(x) for x in (role_map.get("user_said") or []))
    qi_blob = "\n".join(str(x) for x in (role_map.get("qi_said") or []))

    if _USER_QI_AS_FEMALE.search(user_blob):
        for old, new in _DIRTY_QI_USER_AS_FEMALE:
            if old in text:
                text = text.replace(old, new)
                tags.append("gender_direction")

    taught_by_qi = bool(_USER_ACK_QI_TAUGHT.search(user_blob)) or bool(
        _QI_SAID_TAUGHT.search(qi_blob)
    )
    if taught_by_qi:
        for old, new in _TEACH_INVERT_FIXES:
            if old in text:
                text = text.replace(old, new)
                tags.append("teach_direction")

    text, speaker_tags = _rewrite_speaker_attribution(text, role_map)
    tags.extend(speaker_tags)

    # 改写后仍颠倒，或改写完全动不了 → 退回 role_map 保真草稿
    if detect_speaker_inversion(text, role_map):
        sketch = first_person_sketch_from_role_map(role_map)
        if sketch:
            text = sketch
            tags.append("speaker_direction_fallback")

    # 去重标签保序
    seen: set[str] = set()
    uniq = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return text, uniq
