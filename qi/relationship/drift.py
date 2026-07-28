"""用户漂移——他在变，安静地重新认识。"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

DRIFT_THRESHOLD = 0.4
# 基线门槛：样本不足时不谈「他变了」——小样本比对会虚构出从未发生过的历史（实证：「不再聊书了」）
DRIFT_MIN_USER_MESSAGES = 30
DRIFT_MIN_BASELINE_TOPICS = 2

_TOPIC_WORDS = (
    "工作", "代码", "项目", "吉他", "音乐", "电影", "书", "猫", "狗",
    "家人", "朋友", "旅行", "游戏", "学习", "考试", "睡觉", "吃饭",
)


def extract_topics(messages: list[dict]) -> list[str]:
    found: list[str] = []
    for m in messages:
        if m.get("role") != "user":
            continue
        text = m.get("content") or ""
        for w in _TOPIC_WORDS:
            if w in text:
                found.append(w)
    counts = Counter(found)
    # 偶然提一次不算话题：单次命中进基线会在下个窗口变成假的「不再聊X了」
    return [t for t, c in counts.most_common(8) if c >= 2]


def compute_emotional_baseline(messages: list[dict]) -> float:
    """极简：用感叹/负面词粗估。"""
    score = 0.0
    n = 0
    for m in messages:
        if m.get("role") != "user":
            continue
        text = m.get("content") or ""
        n += 1
        if any(k in text for k in ("开心", "哈哈", "谢谢", "好")):
            score += 0.3
        if any(k in text for k in ("累", "难过", "烦", "不想")):
            score -= 0.3
    if n == 0:
        return 0.0
    return max(-1.0, min(1.0, score / n))


def compute_linguistic_profile(messages: list[dict]) -> dict:
    user_msgs = [m.get("content") or "" for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return {"avg_len": 0.0, "emoji_freq": 0.0}
    avg_len = sum(len(t) for t in user_msgs) / len(user_msgs)
    emoji = sum(1 for t in user_msgs if re.search(r"[\U0001F300-\U0001FAFF]", t))
    return {
        "avg_len": round(avg_len, 1),
        "emoji_freq": round(emoji / len(user_msgs), 3),
    }


def _parse_message_time(msg: dict) -> datetime | None:
    raw = msg.get("timestamp")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def compute_rhythm(messages: list[dict]) -> dict[str, Any]:
    """从用户消息时间戳粗估生活节奏：常活跃小时、平均间隔。"""
    times: list[datetime] = []
    for m in messages:
        if m.get("role") != "user":
            continue
        ts = _parse_message_time(m)
        if ts is not None:
            times.append(ts)
    times.sort()
    if not times:
        return {"active_hours": [], "avg_gap_seconds": 0.0, "msg_count": 0}

    hour_counts = Counter(t.hour for t in times)
    active_hours = [h for h, _ in hour_counts.most_common(5)]

    avg_gap = 0.0
    if len(times) >= 2:
        gaps = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
        short = [g for g in gaps if 30 <= g < 6 * 3600]
        if short:
            avg_gap = sum(short) / len(short)

    return {
        "active_hours": sorted(active_hours),
        "avg_gap_seconds": round(avg_gap, 1),
        "msg_count": len(times),
    }


def _as_rhythm_dict(raw: Any) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def compute_rhythm_distance(old_rhythm: Any, new_rhythm: Any) -> float:
    old_r = _as_rhythm_dict(old_rhythm)
    new_r = _as_rhythm_dict(new_rhythm)
    if not old_r or not new_r:
        return 0.0
    if int(old_r.get("msg_count") or 0) < 3 or int(new_r.get("msg_count") or 0) < 3:
        return 0.0

    old_hours = set(old_r.get("active_hours") or [])
    new_hours = set(new_r.get("active_hours") or [])
    if old_hours or new_hours:
        union = old_hours | new_hours
        hour_dist = 1.0 - (len(old_hours & new_hours) / len(union) if union else 0.0)
    else:
        hour_dist = 0.0

    old_gap = float(old_r.get("avg_gap_seconds") or 0.0)
    new_gap = float(new_r.get("avg_gap_seconds") or 0.0)
    if old_gap > 0:
        gap_dist = min(1.0, abs(new_gap - old_gap) / max(old_gap, 1.0))
    else:
        gap_dist = 0.0

    return min(1.0, hour_dist * 0.5 + gap_dist * 0.5)


def detect_user_drift(user_model: dict[str, Any], recent_messages: list[dict]) -> list[str]:
    signals: list[str] = []
    deviations: dict[str, float] = {}

    # 样本门槛：近期用户消息太少时，任何「变化」都不可信
    user_count = sum(1 for m in recent_messages if m.get("role") == "user")
    if user_count < DRIFT_MIN_USER_MESSAGES:
        return []

    old_topics = set(user_model.get("topics") or [])
    if isinstance(user_model.get("topics"), str):
        try:
            old_topics = set(json.loads(user_model["topics"]))
        except json.JSONDecodeError:
            old_topics = set()
    new_topics = set(extract_topics(recent_messages))
    if len(old_topics) >= DRIFT_MIN_BASELINE_TOPICS:
        union = old_topics | new_topics
        inter = old_topics & new_topics
        topic_distance = 1 - (len(inter) / len(union) if union else 0)
    else:
        # 基线话题太少，话题漂移不可信
        topic_distance = 0.0
    deviations["topics"] = topic_distance
    if topic_distance > 0.5 and old_topics - new_topics:
        faded = "、".join(list(old_topics - new_topics)[:3])
        signals.append(f"不再聊{faded}了")

    old_baseline = float(user_model.get("emotional_baseline") or 0.0)
    new_baseline = compute_emotional_baseline(recent_messages)
    emotion_distance = abs(new_baseline - old_baseline)
    deviations["emotion"] = min(1.0, emotion_distance)
    if emotion_distance > 0.2:
        direction = "变好了" if new_baseline > old_baseline else "变低沉了"
        signals.append(f"情绪底色{direction}")

    old_profile = user_model.get("linguistic_profile") or {}
    if isinstance(old_profile, str):
        try:
            old_profile = json.loads(old_profile)
        except json.JSONDecodeError:
            old_profile = {}
    new_profile = compute_linguistic_profile(recent_messages)
    old_len = float(old_profile.get("avg_len") or 0)
    new_len = float(new_profile.get("avg_len") or 0)
    if old_len > 0:
        ling = min(1.0, abs(new_len - old_len) / max(old_len, 1))
    else:
        ling = 0.0
    deviations["linguistic"] = ling
    if ling > 0.4:
        signals.append("说话方式变了")

    new_rhythm = compute_rhythm(recent_messages)
    rhythm_distance = compute_rhythm_distance(user_model.get("rhythm"), new_rhythm)
    deviations["rhythm"] = rhythm_distance
    if rhythm_distance > 0.4:
        signals.append("生活节奏变了")

    total = (
        deviations["topics"] * 0.3
        + deviations["emotion"] * 0.3
        + deviations["rhythm"] * 0.2
        + deviations["linguistic"] * 0.2
    )
    if total > DRIFT_THRESHOLD:
        return signals
    return []


def build_updated_user_model(recent_messages: list[dict], signals: list[str]) -> dict:
    return {
        "topics": extract_topics(recent_messages),
        "emotional_baseline": compute_emotional_baseline(recent_messages),
        "rhythm": compute_rhythm(recent_messages),
        "linguistic_profile": compute_linguistic_profile(recent_messages),
        "life_context": "",
        "drift_signals": signals,
    }
