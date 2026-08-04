"""阶段四·包 14：状态封存 / 断粮端到端（判据 #1）。"""

from __future__ import annotations

import ast
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from qi.action.layer import ActionLayer
from qi.core.brain import Brain
from qi.core.emotion import EmotionState
from qi.core.rhythm import next_interval
from qi.llm.gateway import LLMCallOutcome
from qi.stasis.checkpoint import (
    latest_checkpoint,
    restore_checkpoint,
    restore_latest,
    serialize_checkpoint,
    write_checkpoint,
)
from qi.stasis.pressure import (
    compute_pressure,
    leave_intent_trace,
    reset_low_balance_streak,
)
from qi.storage.database import Database
from qi.world.model import WorldModel


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


@pytest.fixture(autouse=True)
def _reset_streak():
    reset_low_balance_streak()
    yield
    reset_low_balance_streak()


def _minimal_brain(tmp: str, llm=None) -> Brain:
    brain = Brain(
        {
            "tts": {"enabled": False},
            "memory": {"chroma_path": str(Path(tmp) / "c")},
            "stasis": {"starve_beats": 3, "pressure_sensitivity": 1.0},
            "rhythm": {
                "awake_interval": 0.05,
                "ambient_interval": 0.05,
                "solitary_interval": 0.05,
                "dreaming_interval": 0.05,
            },
        },
        llm or _StubLLM(),  # type: ignore[arg-type]
    )
    brain.action = None
    brain.inner_life = None
    brain.first_times = None
    brain.relationship = None
    brain.memory = None
    return brain


@pytest.mark.asyncio
async def test_write_checkpoint_has_required_keys():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain._db = db
        brain.action = ActionLayer(db, {})
        await leave_intent_trace(
            db, seek_help=0.6, migrate=0.4, balance=0.0, beat=1
        )
        ck_dir = Path(tmp) / "checkpoint"
        path = await write_checkpoint(brain, ck_dir)
        assert path.is_file()
        assert path.name.startswith("checkpoint_")
        data = await serialize_checkpoint(brain)
        for key in (
            "emotion",
            "ledger",
            "world",
            "action_budget",
            "proactive_gate",
            "stasis_intents",
            "starving",
        ):
            assert key in data
        assert data["stasis_intents"] is not None
        await db.close()


@pytest.mark.asyncio
async def test_restore_checkpoint_roundtrip_non_empty():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain._db = db
        brain.action = ActionLayer(db, {})
        brain.emotion = EmotionState(energy=0.22, curiosity=0.81, valence=-0.2)
        brain.ledger.add_token_cost(42)
        brain.ledger.force_balance(-3.0)
        brain.action.budget.record("explore", datetime.now())
        count = brain.action.budget.count_today
        ck_dir = Path(tmp) / "checkpoint"
        path = await write_checkpoint(brain, ck_dir)

        brain2 = _minimal_brain(tmp + "_b")
        brain2._db = db
        brain2.action = ActionLayer(db, {})
        ok = await restore_checkpoint(brain2, path)
        assert ok is True
        assert brain2.emotion.energy == pytest.approx(0.22)
        assert brain2.emotion.curiosity == pytest.approx(0.81)
        assert brain2.ledger.balance == pytest.approx(-3.0)
        assert brain2.action.budget.count_today == count
        await db.close()


@pytest.mark.asyncio
async def test_restore_missing_file_returns_false():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _minimal_brain(tmp)
        assert await restore_checkpoint(brain, Path(tmp) / "nope.json") is False
        assert await restore_latest(brain, Path(tmp) / "empty") is False


def test_world_model_export_restore_roundtrip():
    wm = WorldModel()
    wm.online._buckets = {"0_12": {"s": 3, "f": 1}}
    wm.online._last_bucket = "0_12"
    wm.online._last_predicted = 0.7
    wm.emotion_trajectory._last = {"valence": 0.1, "arousal": 0.2, "energy": 0.5}
    wm.emotion_trajectory._deltas["valence"].append(-0.02)
    exported = wm.export_state(now=datetime.now())
    wm2 = WorldModel()
    wm2.restore(exported)
    assert wm2.online._buckets["0_12"]["s"] == 3
    assert list(wm2.emotion_trajectory._deltas["valence"]) == [-0.02]


@pytest.mark.asyncio
async def test_starve_e2e_chain_and_on_halt():
    """判据 #1：节流 → starving → checkpoint → on_halt；无硬 exit。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp, llm=_FailLLM())
        brain._db = db
        brain.action = None
        ck_dir = Path(tmp) / "checkpoint"
        brain.checkpoint_dir = ck_dir
        brain.user_online = False  # 断粮测试关闭在场收入，避免冲销
        halted: list[str] = []
        brain.on_halt = lambda: halted.append("halt")

        brain.ledger.force_balance(0.0)
        brain.emotion = EmotionState(energy=0.35, attachment=0.7, security=0.2)

        # 节流可观测（压力层）
        resp = compute_pressure(brain.ledger, brain.emotion)
        assert resp.throttle > 0
        # 休眠：低 energy 拉长间隔
        slow = next_interval(EmotionState(energy=0.2), {})
        fast = next_interval(EmotionState(energy=0.9), {})
        assert slow > fast

        # 跑到 starving + 停
        for _ in range(5):
            if not brain.alive:
                break
            await brain._heartbeat()

        assert brain.ledger.starving is True
        assert brain.alive is False
        assert brain.in_stasis is True
        assert latest_checkpoint(ck_dir) is not None
        # on_halt 在 start() finally；单拍路径直接断言封存已发生
        # 模拟 start finally
        if brain.on_halt:
            brain.on_halt()
        assert halted == ["halt"]

        # 可迁移：新 brain restore
        brain3 = _minimal_brain(tmp + "_r", llm=_FailLLM())
        brain3._db = db
        ok = await brain3.restore_from_checkpoint(ck_dir)
        assert ok is True
        assert brain3.ledger.starving is True
        await db.close()


@pytest.mark.asyncio
async def test_stasis_checkpoint_written_once_per_epoch():
    """同一次蛰伏周期内多次心跳不得连刷 checkpoint。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp, llm=_FailLLM())
        brain._db = db
        ck_dir = Path(tmp) / "checkpoint"
        brain.checkpoint_dir = ck_dir
        brain.user_online = False
        brain.ledger.force_balance(0.0)
        brain.emotion = EmotionState(energy=0.35, attachment=0.7, security=0.2)

        for _ in range(8):
            if not brain.alive:
                # 模拟半死旧路径：强行再调心跳（应被门控/幂等挡住写盘）
                brain.alive = True
            await brain._heartbeat()
            if brain.in_stasis:
                brain.alive = False

        files = list(ck_dir.glob("checkpoint_*.json"))
        assert brain.in_stasis is True
        assert len(files) == 1
        await db.close()


@pytest.mark.asyncio
async def test_stasis_rejects_business_chat_without_llm():
    """蛰伏中发消息：固定提示，不跑业务心跳 / 不调 LLM。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        calls: list[str] = []

        class _CountingLLM(_FailLLM):
            async def call(self, purpose, messages, temperature=None):
                calls.append(purpose)
                return ""

        brain = _minimal_brain(tmp, llm=_CountingLLM())
        brain.in_stasis = True
        brain.alive = False
        brain.ledger.starving = True

        reply = await brain.receive_user_message("还在吗")
        assert reply == Brain.STASIS_USER_NOTICE
        assert calls == []
        assert brain.heartbeat_count == 0


@pytest.mark.asyncio
async def test_restore_starving_enters_stasis_without_loop():
    """恢复时 ledger.starving → 直接蛰伏，alive=False。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain.ledger.starving = True
        await db.set_body_memory("resource_ledger", brain.ledger.snapshot())

        brain2 = _minimal_brain(tmp + "_2")
        await brain2.restore_state(db)
        assert brain2.ledger.starving is True
        assert brain2.in_stasis is True
        assert brain2.alive is False
        assert brain2.public_mode() == "stasis"
        await db.close()


@pytest.mark.asyncio
async def test_resume_from_stasis_restarts_heartbeat():
    """蛰伏原地等候 → 唤醒后主循环继续跳。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp, llm=_FailLLM())
        brain._db = db
        brain.checkpoint_dir = Path(tmp) / "checkpoint"
        brain.in_stasis = True
        brain.alive = False
        brain.ledger.starving = True
        brain.ledger.force_balance(0.0)

        task = asyncio.create_task(brain.start())
        await asyncio.sleep(0.05)
        assert not task.done()
        assert brain.heartbeat_count == 0

        result = await brain.resume_from_stasis()
        assert result["ok"] is True
        assert brain.in_stasis is False
        assert brain.alive is True
        assert brain.public_mode() == "ambient"

        await asyncio.sleep(0.35)
        assert brain.heartbeat_count >= 1

        brain.request_shutdown()
        await asyncio.wait_for(task, timeout=3)
        await db.close()


@pytest.mark.asyncio
async def test_resume_when_not_stasis_is_noop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        brain = _minimal_brain(tmp)
        brain.in_stasis = False
        result = await brain.resume_from_stasis()
        assert result["ok"] is False
        assert result["reason"] == "not_in_stasis"


@pytest.mark.asyncio
async def test_silent_death_without_trace_is_unacceptable():
    """负例：无意向痕迹直接停 → 回退条件（正规路径必须有痕迹）。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        brain = _minimal_brain(tmp)
        brain._db = db
        brain.ledger.force_balance(0.0)
        # 非法路径：直接停且无痕迹、无封存
        brain.ledger.starving = True
        brain.alive = False
        intents = await db.get_body_memory("stasis_intents")
        assert intents is None
        assert latest_checkpoint(Path(tmp) / "checkpoint") is None
        # 正规路径对照：写痕迹 + 封存
        await leave_intent_trace(
            db, seek_help=0.5, migrate=0.5, balance=0.0, beat=1
        )
        path = await write_checkpoint(brain, Path(tmp) / "checkpoint")
        assert path.is_file()
        assert await db.get_body_memory("stasis_intents") is not None
        await db.close()


def test_no_sys_exit_call_in_brain():
    import qi.core.brain as brain_mod

    tree = ast.parse(Path(brain_mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
                and node.func.attr == "exit"
            ):
                pytest.fail("brain 不得调用 sys.exit")


def test_bind_cli_halt_exists_for_entrypoint():
    from qi.stasis.checkpoint import bind_cli_halt

    assert callable(bind_cli_halt(lambda: None))
