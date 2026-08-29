"""P0：叫住她 / 重说 / 打断意图（非口令唯一入口）。"""

from __future__ import annotations

import pytest
from qi.core.turn_interrupt import (
    REPHRASE_ACK,
    STOP_ACK,
    classify_turn_interrupt,
    maybe_interrupt_gate,
    _parse_kind,
)


def test_gate_is_not_sole_classifier():
    """门控命中 ≠ 已判定打断；只表示值得问模型。"""
    assert maybe_interrupt_gate("等下，我想重说刚才那句")
    assert maybe_interrupt_gate("先停一下")
    # 长新话题：门控可 false，最终靠 none
    assert not maybe_interrupt_gate(
        "对了我想跟你聊聊下周去哈尔滨看冰灯的计划，你觉得哪天比较好"
    )


def test_parse_kind_json():
    assert _parse_kind('{"kind":"rephrase"}') == "rephrase"
    assert _parse_kind('{"kind":"stop"}') == "stop"
    assert _parse_kind('{"kind":"none"}') == "none"


@pytest.mark.asyncio
async def test_classify_non_command_colloquial_rephrase():
    """非口令白话：由模型判别为 rephrase（mock）。"""

    class Fake:
        async def call(self, purpose, messages, temperature=None):
            assert purpose == "fact"
            user = messages[-1]["content"]
            assert "我想改一下刚才说的" in user  # 非「我想重说」按钮文案
            return '{"kind":"rephrase"}'

    kind = await classify_turn_interrupt(Fake(), "我想改一下刚才说的，说错了")  # type: ignore[arg-type]
    assert kind == "rephrase"


@pytest.mark.asyncio
async def test_classify_skips_llm_when_gate_closed():
    class Boom:
        async def call(self, *a, **k):
            raise AssertionError("不应叫模型")

    kind = await classify_turn_interrupt(
        Boom(),  # type: ignore[arg-type]
        "对了我想跟你聊聊下周去哈尔滨看冰灯的计划，你觉得哪天比较好",
    )
    assert kind == "none"


def test_ack_copy_short():
    assert len(REPHRASE_ACK) < 20
    assert len(STOP_ACK) < 10
