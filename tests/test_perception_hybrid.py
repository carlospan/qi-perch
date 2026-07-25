"""混合冲击感知：触发规则 + 超时回退。"""

from __future__ import annotations

import asyncio

import pytest
from qi.core.emotion import EmotionState
from qi.core.perception import Perception


def test_needs_llm_on_mixed_and_long_and_exclaim():
    p = Perception({})
    assert p._needs_llm_impact("哈哈但这事真讨厌", 1, 1)
    assert p._needs_llm_impact("x" * 41, 0, 0)
    assert p._needs_llm_impact("真烦人！", 0, 1)
    assert not p._needs_llm_impact("你好", 1, 0)
    assert not p._needs_llm_impact("嗯嗯", 0, 0)


@pytest.mark.asyncio
async def test_async_falls_back_on_timeout():
    class _SlowLLM:
        async def call(self, **kwargs):
            await asyncio.sleep(3)
            return "0.9"

    p = Perception({}, llm=_SlowLLM())  # type: ignore[arg-type]
    e = EmotionState()
    # 正负同时命中 → 会走 LLM，但超时回退关键词
    val = await p.assess_impact_async("哈哈但这事真讨厌", e)
    keyword = p.assess_impact("哈哈但这事真讨厌", e)
    assert val == keyword


@pytest.mark.asyncio
async def test_async_uses_llm_value():
    class _LLM:
        async def call(self, **kwargs):
            return "-0.7"

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    e = EmotionState()
    val = await p.assess_impact_async("哈哈但这事真讨厌", e)
    assert val < 0


@pytest.mark.asyncio
async def test_chitchat_skips_llm():
    calls = {"n": 0}

    class _LLM:
        async def call(self, **kwargs):
            calls["n"] += 1
            return "0.5"

    p = Perception({}, llm=_LLM())  # type: ignore[arg-type]
    await p.assess_impact_async("你好", EmotionState())
    assert calls["n"] == 0
