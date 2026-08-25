"""Ark 多模型延迟对比（TTFT / 总耗时 / 输出规模）。

用法:
  python tools/benchmark_llm_models.py
  python tools/benchmark_llm_models.py --rounds 2
  python tools/benchmark_llm_models.py --models doubao-seed-2-0-lite-260428 doubao-seed-2-0-mini-260428
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from qi.config import load_config

MODELS = [
    "doubao-seed-2-1-turbo-260628",
    "deepseek-v4-flash-ga-260731",
    "doubao-seed-evolving",
    "doubao-seed-2-1-pro-260628",
]

# 贴近栖闲聊：短问 + 中等追问
PROMPTS = [
    (
        "short",
        [
            {"role": "system", "content": "你是栖。简短一两句，像朋友发消息。"},
            {"role": "user", "content": "今天有点累，你在吗？"},
        ],
    ),
    (
        "medium",
        [
            {
                "role": "system",
                "content": "你是栖。简短自然，不超过3句。",
            },
            {
                "role": "user",
                "content": "最近有个世界机器人大会，你有所了解吗？简单说说。",
            },
        ],
    ),
]


@dataclass
class RunStat:
    ok: bool = False
    ttft_ms: float | None = None
    total_ms: float | None = None
    chars: int = 0
    completion_tokens: int | None = None
    error: str = ""


@dataclass
class ModelReport:
    model: str
    runs: list[RunStat] = field(default_factory=list)

    def median_ttft(self) -> float | None:
        xs = [r.ttft_ms for r in self.runs if r.ok and r.ttft_ms is not None]
        return statistics.median(xs) if xs else None

    def median_total(self) -> float | None:
        xs = [r.total_ms for r in self.runs if r.ok and r.total_ms is not None]
        return statistics.median(xs) if xs else None

    def median_chars(self) -> float | None:
        xs = [r.chars for r in self.runs if r.ok]
        return statistics.median(xs) if xs else None

    def median_tokens(self) -> float | None:
        xs = [
            r.completion_tokens
            for r in self.runs
            if r.ok and r.completion_tokens is not None
        ]
        return statistics.median(xs) if xs else None


async def one_stream_call(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 256,
) -> RunStat:
    stat = RunStat()
    t0 = time.perf_counter()
    first_at: float | None = None
    chunks: list[str] = []
    usage = None
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                if first_at is None:
                    first_at = time.perf_counter()
                chunks.append(delta)
        t1 = time.perf_counter()
        text = "".join(chunks)
        stat.ok = bool(text.strip())
        stat.chars = len(text)
        stat.ttft_ms = (first_at - t0) * 1000 if first_at else None
        stat.total_ms = (t1 - t0) * 1000
        if usage is not None and getattr(usage, "completion_tokens", None):
            stat.completion_tokens = int(usage.completion_tokens)
        if not stat.ok:
            stat.error = "empty"
    except Exception as e:
        stat.error = type(e).__name__ if str(e) == "" else str(e)[:120]
    return stat


async def benchmark(
    *,
    models: list[str],
    rounds: int,
    pause_s: float,
) -> list[ModelReport]:
    cfg = load_config()
    ark = (cfg.get("llm") or {}).get("custom_providers", {}).get("ark") or {}
    base_url = str(ark.get("base_url") or "").strip()
    api_key = str(ark.get("api_key") or "").strip()
    if not base_url or not api_key:
        raise SystemExit("ark base_url / ARK_API_KEY 未配置")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    reports: list[ModelReport] = []

    for model in models:
        rep = ModelReport(model=model)
        print(f"\n=== {model} ===")
        for label, messages in PROMPTS:
            for i in range(rounds):
                stat = await one_stream_call(client, model, messages)
                rep.runs.append(stat)
                if stat.ok:
                    print(
                        f"  {label}#{i+1}: TTFT {stat.ttft_ms:.0f}ms | "
                        f"total {stat.total_ms:.0f}ms | "
                        f"chars {stat.chars}"
                        + (
                            f" | tok {stat.completion_tokens}"
                            if stat.completion_tokens is not None
                            else ""
                        )
                    )
                else:
                    print(f"  {label}#{i+1}: FAIL {stat.error}")
                await asyncio.sleep(pause_s)
        reports.append(rep)
    return reports


def print_summary(reports: list[ModelReport]) -> None:
    print("\n" + "=" * 72)
    print("汇总（中位数，ms；TTFT=首字延迟，total=整句收完）")
    print("=" * 72)
    header = f"{'model':<36} {'TTFT':>8} {'total':>8} {'chars':>6} {'tok':>6}"
    print(header)
    print("-" * len(header))
    rows = []
    for rep in reports:
        ttft = rep.median_ttft()
        total = rep.median_total()
        chars = rep.median_chars()
        tok = rep.median_tokens()
        if ttft is None:
            print(f"{rep.model:<36} {'FAIL':>8}")
            continue
        rows.append((total or 999999, rep.model, ttft, total, chars, tok))
        tok_s = f"{tok:.0f}" if tok is not None else "-"
        chars_s = f"{chars:.0f}" if chars is not None else "-"
        print(
            f"{rep.model:<36} {ttft:8.0f} {total:8.0f} {chars_s:>6} {tok_s:>6}"
        )
    if rows:
        rows.sort(key=lambda x: x[0])
        print("\n按总耗时排序（快→慢）:")
        for i, (_, name, ttft, total, _, _) in enumerate(rows, 1):
            print(f"  {i}. {name}  TTFT≈{ttft:.0f}ms  total≈{total:.0f}ms")


def main() -> None:
    p = argparse.ArgumentParser(description="Ark 模型延迟对比")
    p.add_argument(
        "--models",
        nargs="+",
        default=MODELS,
        help="要测的模型 ID 列表",
    )
    p.add_argument("--rounds", type=int, default=2, help="每个 prompt 跑几轮")
    p.add_argument("--pause", type=float, default=0.8, help="请求间隔秒")
    args = p.parse_args()
    reports = asyncio.run(
        benchmark(
            models=args.models,
            rounds=max(1, args.rounds),
            pause_s=args.pause,
        )
    )
    print_summary(reports)


if __name__ == "__main__":
    main()
