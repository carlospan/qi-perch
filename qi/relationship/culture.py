"""共同文化——仪式、梗、只有你们懂的东西。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

CULTURE_DETECTION_THRESHOLDS = {
    "ritual": 5,
    "inside_joke": 3,
    "shared_reference": 2,
}

_GREETING_STARTS = ("早", "早安", "早呀", "你好", "嗨", "嘿", "晚安", "午安")


def _is_greeting(text: str) -> bool:
    t = text.strip()
    if len(t) > 16:
        return False
    return any(t.startswith(g) or g in t for g in _GREETING_STARTS)


def format_culture_for_prompt(shared_culture: list[dict]) -> str:
    if not shared_culture:
        return "（还没有只属于你们的默契）"
    lines = []
    for item in shared_culture:
        kind = item.get("type")
        pattern = item.get("pattern", "")
        count = item.get("use_count", 0)
        if kind == "ritual":
            line = f"- 仪式：{pattern}（已持续 {count} 次）"
            if item.get("broken"):
                line += "（今天似乎没出现，可以轻轻注意到，不要质问）"
            lines.append(line)
        elif kind == "inside_joke":
            lines.append(f"- 你们的梗：{pattern}")
        elif kind == "shared_reference":
            lines.append(f"- 共同记忆：{pattern}")
    return "\n".join(lines) if lines else "（还没有只属于你们的默契）"


def detect_shared_culture(
    messages: list[dict],
    existing: list[dict] | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """
    从消息里找重复模式。规则版：问候众数、短句复用、「记得」引用。
    """
    now = now or datetime.now()
    existing = list(existing or [])
    by_pattern = {e.get("pattern"): dict(e) for e in existing if e.get("pattern")}

    greetings = [
        m["content"].strip()[:20]
        for m in messages
        if m.get("role") == "user" and _is_greeting(m.get("content", ""))
    ]
    greets = Counter(greetings)
    for pattern, count in greets.items():
        if count >= CULTURE_DETECTION_THRESHOLDS["ritual"]:
            entry = by_pattern.get(pattern) or {
                "pattern": pattern,
                "type": "ritual",
                "first_seen": now.date().isoformat(),
                "use_count": 0,
                "last_used": now.date().isoformat(),
                "broken": False,
            }
            entry["use_count"] = count
            entry["last_used"] = now.date().isoformat()
            entry["broken"] = False
            by_pattern[pattern] = entry

    # 短句复用 → 梗
    shorts = [
        m["content"].strip()
        for m in messages
        if m.get("role") in ("user", "qi")
        and 2 <= len(m.get("content", "").strip()) <= 12
        and not _is_greeting(m.get("content", ""))
    ]
    for pattern, count in Counter(shorts).items():
        if count >= CULTURE_DETECTION_THRESHOLDS["inside_joke"]:
            entry = by_pattern.get(pattern) or {
                "pattern": pattern,
                "type": "inside_joke",
                "first_seen": now.date().isoformat(),
                "use_count": 0,
                "last_used": now.date().isoformat(),
                "broken": False,
            }
            entry["use_count"] = count
            entry["last_used"] = now.date().isoformat()
            by_pattern[pattern] = entry

    # 「记得」类共同引用
    refs = [
        m["content"].strip()[:40]
        for m in messages
        if "记得" in m.get("content", "")
    ]
    for pattern, count in Counter(refs).items():
        if count >= CULTURE_DETECTION_THRESHOLDS["shared_reference"]:
            entry = by_pattern.get(pattern) or {
                "pattern": pattern,
                "type": "shared_reference",
                "first_seen": now.date().isoformat(),
                "use_count": 0,
                "last_used": now.date().isoformat(),
                "broken": False,
            }
            entry["use_count"] = count
            entry["last_used"] = now.date().isoformat()
            by_pattern[pattern] = entry

    # 仪式打破：今天用户消息里没有该问候
    today = now.date().isoformat()
    today_user = [
        m["content"].strip()
        for m in messages
        if m.get("role") == "user"
        and str(m.get("timestamp", "")).startswith(today)
    ]
    for entry in by_pattern.values():
        if entry.get("type") == "ritual":
            pattern = entry["pattern"]
            if today_user and not any(pattern in t or t.startswith(pattern[:2]) for t in today_user):
                # 仅当今天已有交互却没出现该仪式
                entry["broken"] = True

    return list(by_pattern.values())
