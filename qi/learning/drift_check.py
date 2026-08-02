"""异时测试骨架：对比两版语料差异（不训也能跑）。

真训练后的「响应漂移」对比可复用本模块（届时喂真实模型输出）。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from qi.learning.corpus import CorpusStore


def summarize_corpus(samples: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = Counter(str(s.get("winner_kind") or "idle") for s in samples)
    curiosities: list[float] = []
    surprises: list[float] = []
    for s in samples:
        motive = s.get("motive") if isinstance(s.get("motive"), dict) else {}
        try:
            curiosities.append(float(motive.get("curiosity") or 0.0))
        except (TypeError, ValueError):
            pass
        try:
            surprises.append(float(motive.get("world_surprise") or 0.0))
        except (TypeError, ValueError):
            pass
    return {
        "n": len(samples),
        "winner_kind_counts": dict(kinds),
        "curiosity_mean": (
            sum(curiosities) / len(curiosities) if curiosities else 0.0
        ),
        "world_surprise_mean": (
            sum(surprises) / len(surprises) if surprises else 0.0
        ),
        "beats": sorted({s.get("beat") for s in samples if s.get("beat") is not None}),
    }


def probe_pairs(samples: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    """固定探针：(winner_kind, curiosity, world_surprise)。"""
    pairs: list[tuple[str, float, float]] = []
    for s in samples:
        motive = s.get("motive") if isinstance(s.get("motive"), dict) else {}
        try:
            c = float(motive.get("curiosity") or 0.0)
        except (TypeError, ValueError):
            c = 0.0
        try:
            w = float(motive.get("world_surprise") or 0.0)
        except (TypeError, ValueError):
            w = 0.0
        pairs.append((str(s.get("winner_kind") or "idle"), round(c, 4), round(w, 4)))
    return pairs


def diff_versions(
    path_a: str | Path,
    path_b: str | Path,
) -> dict[str, Any]:
    """两版语料差异摘要（退出判据 #1 地基，非真响应漂移）。"""
    store = CorpusStore()
    a = store.load_version(path_a)
    b = store.load_version(path_b)
    sa, sb = summarize_corpus(a), summarize_corpus(b)
    pa, pb = set(probe_pairs(a)), set(probe_pairs(b))
    kinds_a = set(sa["winner_kind_counts"])
    kinds_b = set(sb["winner_kind_counts"])
    return {
        "path_a": str(path_a),
        "path_b": str(path_b),
        "summary_a": sa,
        "summary_b": sb,
        "n_delta": sb["n"] - sa["n"],
        "kinds_only_in_a": sorted(kinds_a - kinds_b),
        "kinds_only_in_b": sorted(kinds_b - kinds_a),
        "probe_only_in_a": sorted(pa - pb),
        "probe_only_in_b": sorted(pb - pa),
        "curiosity_mean_delta": sb["curiosity_mean"] - sa["curiosity_mean"],
        "world_surprise_mean_delta": (
            sb["world_surprise_mean"] - sa["world_surprise_mean"]
        ),
        "note": (
            "本摘要仅对比语料版本字段（#1-地基）。"
            "真异时响应漂移需维护者显式训练后另喂模型输出。"
        ),
    }


def format_diff_report(diff: dict[str, Any]) -> str:
    return json.dumps(diff, ensure_ascii=False, indent=2)
