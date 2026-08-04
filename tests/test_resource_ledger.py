"""阶段四·包 12：N0 资源账本。"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from qi.action.budget import ActionBudget
from qi.core.brain import Brain
from qi.llm.gateway import LLMCallOutcome
from qi.stasis.ledger import (
    INCOME_DAILY_CAP,
    INCOME_MIN_INTERVAL_SEC,
    INCOME_SOURCES_REJECTED,
    MEM_RETRIEVAL_TOKEN_COST,
    ONLINE_PRESENCE_AMOUNT,
    ONLINE_PRESENCE_MIN_INTERVAL_SEC,
    STORAGE_ESTIMATE_EVERY_N_BEATS,
    TOKEN_SPEND_SCALE,
    ResourceLedger,
)
from qi.storage.database import Database


class _StubLLM:
    def __init__(self, text: str = "嗯。"):
        self.text = text
        self.last_outcome = LLMCallOutcome(text=text, failure=None)

    async def call(self, purpose, messages, temperature=None):
        return self.text


class _FailLLM:
    def __init__(self):
        self.last_outcome = LLMCallOutcome(text="", failure="unreachable")

    async def call(self, purpose, messages, temperature=None):
        return ""


def test_add_compute_increments():
    led = ResourceLedger()
    led.tick_window(1)
    led.add_compute(0.05)
    led.tick_window(2)
    led.add_compute(0.07)
    assert led.compute_seconds == pytest.approx(0.12)
    assert led.spend_window > 0
    assert led.balance < 0


def test_add_token_cost_and_attempt():
    led = ResourceLedger()
    led.tick_window(1)
    led.add_token_cost(MEM_RETRIEVAL_TOKEN_COST)
    assert led.token_budget == MEM_RETRIEVAL_TOKEN_COST
    before = led.spend_window
    led.add_token_cost(10)  # 失败尝试成本
    assert led.spend_window == pytest.approx(before + 10 * TOKEN_SPEND_SCALE)


def test_estimate_storage_not_every_beat_semantics():
    """estimate_storage 本身只赋值；brain 侧每 N 拍才调——此处验赋值。"""
    led = ResourceLedger()
    led.estimate_storage(4096)
    assert led.storage_bytes == 4096
    led.estimate_storage(8192)
    assert led.storage_bytes == 8192
    assert STORAGE_ESTIMATE_EVERY_N_BEATS >= 1


def test_snapshot_restore_roundtrip():
    led = ResourceLedger()
    led.tick_window(3)
    led.add_compute(0.1)
    led.add_token_cost(40)
    assert led.credit_income("effective_interaction", now=datetime(2026, 8, 2, 12, 0, 0))
    snap = led.snapshot()
    other = ResourceLedger()
    other.restore(snap)
    assert other.compute_seconds == pytest.approx(led.compute_seconds)
    assert other.token_budget == led.token_budget
    assert other.income == led.income
    assert other.balance == pytest.approx(led.balance)
    assert other.last_interaction_credit_at == led.last_interaction_credit_at


@pytest.mark.parametrize("src", sorted(INCOME_SOURCES_REJECTED))
def test_r3_rejects_satisfaction_sources(src: str):
    led = ResourceLedger()
    led.tick_window(1)
    before = led.income
    assert led.credit_income(src, amount=10.0) is False
    assert led.income == before


def test_r3_whitelist_accepts():
    led = ResourceLedger()
    led.tick_window(1)
    now = datetime(2026, 8, 2, 10, 0, 0)
    assert led.credit_income("effective_interaction", now=now) is True
    assert led.credit_income("online_presence", now=now + timedelta(seconds=10)) is True
    assert led.income == pytest.approx(2.0)


def test_anti_spam_interval_and_daily_cap():
    led = ResourceLedger()
    led.tick_window(1)
    t0 = datetime(2026, 8, 2, 11, 0, 0)
    assert led.credit_income("effective_interaction", now=t0) is True
    assert (
        led.credit_income(
            "effective_interaction",
            now=t0 + timedelta(seconds=INCOME_MIN_INTERVAL_SEC - 0.5),
        )
        is False
    )
    assert (
        led.credit_income(
            "effective_interaction",
            now=t0 + timedelta(seconds=INCOME_MIN_INTERVAL_SEC + 0.1),
        )
        is True
    )
    # 日帽
    led2 = ResourceLedger()
    led2.tick_window(1)
    day = datetime(2026, 8, 2, 8, 0, 0)
    for i in range(INCOME_DAILY_CAP):
        ok = led2.credit_income(
            "effective_interaction",
            now=day + timedelta(seconds=i * (INCOME_MIN_INTERVAL_SEC + 0.1)),
        )
        assert ok is True
    assert (
        led2.credit_income(
            "effective_interaction",
            now=day + timedelta(seconds=INCOME_DAILY_CAP * 10),
        )
        is False
    )


def test_action_budget_does_not_affect_ledger_balance():
    led = ResourceLedger()
    led.tick_window(1)
    led.add_token_cost(5)
    bal = led.balance
    budget = ActionBudget({})
    now = datetime.now()
    assert budget.can_autonomous(now)
    budget.record("explore", now)
    assert led.balance == pytest.approx(bal)


def test_balance_trends_negative_without_income():
    led = ResourceLedger()
    for beat in range(1, 20):
        led.tick_window(beat)
        led.add_compute(0.01)
    assert led.balance < 0


def test_force_balance_zero():
    led = ResourceLedger()
    led.tick_window(1)
    led.add_token_cost(100)
    led.force_balance(0.0)
    assert led.balance == 0.0


def test_description_human_readable():
    led = ResourceLedger()
    led.add_compute(1.5)
    text = led.description()
    assert "认知" in text and "收入" in text


@pytest.mark.asyncio
async def test_brain_heartbeat_ledger_no_llm_dependency():
    """拔管：FailLLM 下仍记账。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _FailLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        before = brain.ledger.compute_seconds
        brain._pending_queue.append("还在吗")
        await brain._heartbeat()
        assert brain.ledger.compute_seconds > before
        assert brain.ledger.token_budget > 0  # 尝试成本
        await brain.save_state(db)
        brain2 = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c2")}},
            _FailLLM(),  # type: ignore[arg-type]
        )
        await brain2.restore_state(db)
        assert brain2.ledger.compute_seconds == pytest.approx(
            brain.ledger.compute_seconds
        )
        await db.close()


@pytest.mark.asyncio
async def test_idle_heartbeat_credits_online_presence():
    """空闲且 user_online 时记 online_presence。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = Brain(
            {
                "tts": {"enabled": False},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
                "stasis": {
                    "presence_income": 2.0,
                    "presence_min_interval_sec": 0.0,
                },
            },
            _StubLLM(),  # type: ignore[arg-type]
        )
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        brain.user_online = True
        before = brain.ledger.income
        await brain._heartbeat()
        assert brain.ledger.income == pytest.approx(before + ONLINE_PRESENCE_AMOUNT)


@pytest.mark.asyncio
async def test_offline_idle_skips_presence_income():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = Brain(
            {
                "tts": {"enabled": False},
                "memory": {"chroma_path": str(Path(tmp) / "c")},
                "stasis": {"presence_min_interval_sec": 0.0},
            },
            _StubLLM(),  # type: ignore[arg-type]
        )
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        brain.user_online = False
        before = brain.ledger.income
        await brain._heartbeat()
        assert brain.ledger.income == pytest.approx(before)


def test_interaction_income_covers_typical_reply_tokens():
    """标定：一次有效交互收入 ≈ 覆盖约 500 token 折算支出。"""
    led = ResourceLedger()
    led.tick_window(1)
    led.credit_income(
        "effective_interaction",
        amount=25.0,
        now=datetime(2026, 8, 5, 12, 0, 0),
    )
    led.add_token_cost(500)
    assert led.balance == pytest.approx(0.0)


def test_presence_min_interval_override():
    led = ResourceLedger()
    led.tick_window(1)
    t0 = datetime(2026, 8, 5, 12, 0, 0)
    assert led.credit_income(
        "online_presence",
        amount=2.0,
        now=t0,
        min_interval_sec=ONLINE_PRESENCE_MIN_INTERVAL_SEC,
    )
    assert (
        led.credit_income(
            "online_presence",
            amount=2.0,
            now=t0 + timedelta(seconds=10),
            min_interval_sec=ONLINE_PRESENCE_MIN_INTERVAL_SEC,
        )
        is False
    )
    assert led.credit_income(
        "online_presence",
        amount=2.0,
        now=t0 + timedelta(seconds=ONLINE_PRESENCE_MIN_INTERVAL_SEC + 0.1),
        min_interval_sec=ONLINE_PRESENCE_MIN_INTERVAL_SEC,
    )


@pytest.mark.asyncio
async def test_brain_storage_estimate_on_nth_beat():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "qi.db")
        db = Database(db_path)
        await db.initialize()
        brain = Brain(
            {"tts": {"enabled": False}, "memory": {"chroma_path": str(Path(tmp) / "c")}},
            _StubLLM(),  # type: ignore[arg-type]
        )
        brain._db = db
        brain.action = None
        brain.inner_life = None
        brain.first_times = None
        brain.relationship = None
        brain.memory = None
        # 推到刚好整除 N
        brain.heartbeat_count = STORAGE_ESTIMATE_EVERY_N_BEATS - 1
        await brain._heartbeat()
        assert brain.ledger.storage_bytes > 0
        await db.close()
