"""W4：编织调度——长睡眠分段轮询，积压中途涨够提前织。

mock asyncio.sleep 跑真实循环（不抽纯函数）；重点断言「提前醒」与「安静时不是 12h」。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qi.core.brain import Brain

WEAVE_CFG = {
    "memory": {
        "narrative_weave_interval": 100,       # 长周期（测试用小值）
        "narrative_weave_backlog_threshold": 8,
        "narrative_weave_backlog_interval": 5,  # 短周期
        "narrative_weave_check_period": 3,      # 长睡眠复查粒度
    }
}


def _make_brain(count_side_effect) -> tuple[Brain, list, list]:
    """造一个 Brain：memory 的 unprocessed_event_count 用给定 side_effect；
    weave_narrative 记调用并把 alive 置 False（只跑一轮，防无限循环）。"""
    brain = Brain(WEAVE_CFG, MagicMock())
    brain.alive = True
    memory = MagicMock()
    memory.unprocessed_event_count = AsyncMock(side_effect=count_side_effect)
    memory.has_unprocessed_events = AsyncMock(return_value=True)
    weaves: list[int] = []
    sleeps: list[float] = []

    async def fake_weave(*args, **kwargs):
        weaves.append(1)
        brain.alive = False  # 织完一次就停

    memory.weave_narrative = AsyncMock(side_effect=fake_weave)
    brain.memory = memory
    return brain, sleeps, weaves


@pytest.mark.asyncio
async def test_weave_wakes_early_when_backlog_crosses_threshold():
    """核心：长睡中途积压涨过阈值 → 在总等待 < interval 时就织。"""
    # 首查 0（进长睡分支），复查时涨到 10（≥8）→ 提前跳出
    counts = [0] + [10] * 100
    brain, sleeps, weaves = _make_brain(counts)

    with patch("qi.core.brain.asyncio.sleep", side_effect=lambda s: sleeps.append(s)):
        await brain._background_narrative_weaving()

    assert len(weaves) == 1
    total = sum(sleeps)
    assert total < 100, f"应提前醒，实际总等待 {total}"
    assert total == 3  # 第一段 check_period 后复查就涨够


@pytest.mark.asyncio
async def test_weave_quiet_sleeps_full_interval_not_double():
    """安静（积压始终 <8）→ 总等待 ≈ interval（100），不是 2×interval（防 12h 回归硬伤）。"""
    counts = [0] * 1000  # 始终 <8
    brain, sleeps, weaves = _make_brain(counts)

    with patch("qi.core.brain.asyncio.sleep", side_effect=lambda s: sleeps.append(s)):
        await brain._background_narrative_weaving()

    assert len(weaves) == 1
    total = sum(sleeps)
    assert total == pytest.approx(100), f"安静时应睡满 interval，实际 {total}"
    assert total < 200, "绝不能是 2×interval（12h 硬伤回归）"


@pytest.mark.asyncio
async def test_weave_backlog_uses_short_cycle():
    """积压一开始就 ≥8：首轮不睡 backlog_interval，直接织（包19 first_pass）。"""
    counts = [10] * 100
    brain, sleeps, weaves = _make_brain(counts)

    with patch("qi.core.brain.asyncio.sleep", side_effect=lambda s: sleeps.append(s)):
        await brain._background_narrative_weaving()

    assert len(weaves) == 1
    assert sleeps == []  # 启动即积压：首轮不睡


@pytest.mark.asyncio
async def test_weave_backlog_second_pass_sleeps_short_cycle():
    """首轮织完后若仍积压且继续跑：第二轮才睡 backlog_interval。"""
    counts = [10] * 100
    brain = Brain(WEAVE_CFG, MagicMock())
    brain.alive = True
    memory = MagicMock()
    memory.unprocessed_event_count = AsyncMock(side_effect=counts)
    memory.has_unprocessed_events = AsyncMock(return_value=True)
    sleeps: list[float] = []
    weaves: list[int] = []

    async def fake_weave(*args, **kwargs):
        weaves.append(1)
        if len(weaves) >= 2:
            brain.alive = False

    memory.weave_narrative = AsyncMock(side_effect=fake_weave)
    brain.memory = memory

    with patch("qi.core.brain.asyncio.sleep", side_effect=lambda s: sleeps.append(s)):
        await brain._background_narrative_weaving()

    assert len(weaves) == 2
    assert sleeps == [5]


@pytest.mark.asyncio
async def test_memory_decay_uses_resume_interval_wait():
    """包19：memory_decay 首睡走 _resume_interval_wait，不再硬睡满 interval。"""
    cfg = {"memory": {"decay_interval": 86400}}
    brain = Brain(cfg, MagicMock())
    brain.alive = True
    narrative = MagicMock()
    decayed: list[int] = []

    async def fake_decay():
        decayed.append(1)
        brain.alive = False

    narrative.decay = AsyncMock(side_effect=fake_decay)
    memory = MagicMock()
    memory.narrative = narrative
    brain.memory = memory

    sleeps: list[float] = []
    resume_calls: list[tuple] = []

    async def fake_resume(key, interval, default_first):
        resume_calls.append((key, interval, default_first))
        return 120.0

    brain._resume_interval_wait = AsyncMock(side_effect=fake_resume)
    brain._mark_interval_done = AsyncMock()

    with patch("qi.core.brain.asyncio.sleep", side_effect=lambda s: sleeps.append(s)):
        await brain._background_memory_decay()

    assert resume_calls == [("last_memory_decay", 86400.0, 120.0)]
    assert sleeps[0] == 120.0
    assert len(decayed) == 1
    brain._mark_interval_done.assert_awaited_with("last_memory_decay")
    # decay 后 while 尾部仍会排一次 sleep(interval)，随后因 alive=False 退出
    assert 86400.0 in sleeps