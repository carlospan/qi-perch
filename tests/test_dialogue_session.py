"""DialogueSessionContext 单测（架构整顿 Phase 2）。"""

from datetime import datetime, timedelta

from qi.core.dialogue_session import DialogueSessionContext


def test_clear_pending_assist():
    ctx = DialogueSessionContext()
    ctx.pending_assist_confirmation = object()
    ctx.pending_assist_confirmation_at = datetime.now()
    ctx.pending_assist_heartbeats = 2
    ctx.clear_pending_assist()
    assert ctx.pending_assist_confirmation is None
    assert ctx.pending_assist_heartbeats == 0


def test_disk_listing_fresh_within_window():
    ctx = DialogueSessionContext()
    now = datetime.now()
    ctx.last_disk_listing = {
        "dir": "D:\\docs",
        "entries": [{"name": "a.txt"}],
        "at": now - timedelta(minutes=2),
    }
    assert ctx.disk_listing_fresh(now) is True


def test_write_desire_expires():
    ctx = DialogueSessionContext()
    ctx.write_desire = {
        "intent": "diary",
        "topic": "今天",
        "at": datetime.now() - timedelta(minutes=11),
    }
    assert ctx.write_desire_fresh() is False


def test_tick_pending_timeout_clears_target():
    ctx = DialogueSessionContext()
    ctx.pending_assist_confirmation = object()
    ctx.pending_assist_confirmation_at = datetime.now() - timedelta(minutes=6)
    ctx.last_assist_target = "note.txt"
    ctx.last_assist_target_at = datetime.now()
    ctx.tick_pending_timeout(datetime.now())
    assert ctx.pending_assist_confirmation is None
    assert ctx.last_assist_target is None
