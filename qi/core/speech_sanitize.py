# -*- coding: utf-8 -*-
"""对话出口消毒：剥模型偶发念出的元指令/导演备忘前缀。"""

from __future__ import annotations

import re

# 首行/首段像「工作备忘」而非对人说话（宜窄，防误伤）
_META_START = re.compile(
    r"^(?:"
    r"意图[：:]|"
    r"回应[^。\n]{0,48}[：:]|"
    r"依据|"
    r"本拍意向|"
    r"导演备注|"
    r"工作备忘"
    r")"
)

_META_MARKERS = (
    "不添新事实",
    "不补画面",
    "回应取",
    "不编造其他事",
    "不编造其他",
)


def _is_meta_block(block: str) -> bool:
    s = (block or "").strip()
    if not s or len(s) > 220:
        return False
    # 纯括号舞台指示（旧风格）不按元指令剥，除非同时带备忘词
    if s.startswith("（") and not any(m in s for m in _META_MARKERS) and not s.startswith(
        "（依据"
    ):
        if "意图" not in s[:12] and not s.startswith("（回应"):
            return False
    first = s.split("\n", 1)[0].strip()
    if _META_START.search(first) or _META_START.search(s):
        # 「回应你一声」等人话：无冒号则不剥
        if first.startswith("回应") and "：" not in first[:24] and ":" not in first[:24]:
            return False
        return True
    if any(m in s for m in _META_MARKERS):
        return True
    # 「语气安静、亲近，承接…」类
    if "语气" in s and ("承接" in s or "亲近" in s) and (
        "问候" in s or "不添" in s or "不编造" in s
    ):
        return True
    return False


def strip_meta_preamble(text: str) -> str:
    """
    若以元指令/导演备忘起头且后文仍有对白，剥掉前缀；否则原样。
    剥空则回退原文（避免整句消失）。
    """
    raw = (text or "").strip()
    if not raw:
        return raw

    # 1) 空行分段：最常见（2094 / 复现 #5 / 2074）
    parts = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if len(parts) >= 2 and _is_meta_block(parts[0]):
        cleaned = "\n\n".join(parts[1:]).strip()
        if cleaned:
            return cleaned

    # 2) 单段但首行是备忘、其后还有内容
    lines = raw.split("\n")
    if len(lines) >= 2:
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        if rest and _is_meta_block(first):
            return rest

    return raw
