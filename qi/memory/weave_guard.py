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

    # 去重标签保序
    seen: set[str] = set()
    uniq = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return text, uniq
