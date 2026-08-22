"""L7 write：D: 白名单写下 + 日记按日期新建。"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from qi.action.permission import can_write
from qi.action.write import (
    WriteAction,
    WriteRequest,
    detect_write_intent,
    looks_like_write_intent,
    next_diary_filename,
    normalize_under_root,
)
from qi.storage.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("qi.action.write.DEFAULT_ALLOWED_ROOT", tmp_path)
    return tmp_path


def test_can_write_acquaintance():
    assert can_write("acquaintance") is True
    assert can_write("stranger") is False


def test_looks_like_write_diary():
    assert looks_like_write_intent("写一篇日记，记今天和你的日常")
    assert looks_like_write_intent(r"帮我记到 D:\notes\a.md")
    assert not looks_like_write_intent("打开企微")


@pytest.mark.asyncio
async def test_detect_diary_and_ask_where(root):
    diary = await detect_write_intent("写一篇日记记今天")
    assert diary is not None
    assert diary.intent == "diary"

    ask = await detect_write_intent("帮我往笔记里写点东西")
    assert ask is not None
    assert ask.intent in ("ask_where", "write", "diary")


def test_next_diary_filename(root):
    day = date(2026, 8, 15)
    p1 = next_diary_filename(root, day)
    assert p1.name == "日记-2026-08-15.md"
    p1.write_text("a", encoding="utf-8")
    p2 = next_diary_filename(root, day)
    assert p2.name == "日记-2026-08-15-2.md"


@pytest.mark.asyncio
async def test_diary_asks_where_when_empty_whitelist(db, root):
    action = WriteAction(db)
    req = WriteRequest(intent="diary", topic="写今天日记")
    out = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert out.get("need_path") is True
    assert "日记" in (out.get("qi_line") or "") or "目录" in (out.get("qi_line") or "")


@pytest.mark.asyncio
async def test_diary_create_dated_file(db, root):
    diary_dir = root / "日记本"
    diary_dir.mkdir()
    action = WriteAction(db)
    allow = WriteRequest(
        intent="allow",
        path=str(diary_dir),
        entry_kind="dir",
        role="diary",
        topic="日记目录",
    )
    done_allow = await action.execute(
        allow, relationship_stage="friend", confirmed=True
    )
    assert done_allow.get("outcome") == "success"

    req = WriteRequest(
        intent="diary",
        topic="写日记",
        content="今天我们聊了 write。",
    )
    gate = await action.execute(
        req, relationship_stage="friend", confirmed=False
    )
    assert gate.get("outcome") == "success"
    assert "日记-" in (gate.get("qi_line") or "")

    files = list(diary_dir.glob("日记-*.md"))
    assert len(files) == 1
    assert "今天我们聊了 write" in files[0].read_text(encoding="utf-8")

    # 同日第二次 → -2
    req2 = WriteRequest(
        intent="diary", topic="再写", content="又记一笔。"
    )
    await action.execute(req2, relationship_stage="friend", confirmed=False)
    names = sorted(p.name for p in diary_dir.glob("日记-*.md"))
    assert any(n.endswith("-2.md") for n in names)


@pytest.mark.asyncio
async def test_append_file(db, root):
    f = root / "note.md"
    f.write_text("旧\n", encoding="utf-8")
    action = WriteAction(db)
    req = WriteRequest(
        intent="write",
        path=str(f),
        content="新句",
    )
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("outcome") == "success"
    body = f.read_text(encoding="utf-8")
    assert "旧" in body and "新句" in body


@pytest.mark.asyncio
async def test_rejects_outside_root(db, root):
    action = WriteAction(db)
    req = WriteRequest(
        intent="write",
        path=r"C:\Windows\notes.md",
        content="x",
    )
    out = await action.execute(
        req, relationship_stage="friend", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_normalize_under_root(root):
    inside = root / "a.md"
    inside.write_text("1", encoding="utf-8")
    assert normalize_under_root(str(inside), root=root) == inside.resolve()
    other = root.parent / "outside.md"
    assert normalize_under_root(str(other), root=root) is None


@pytest.mark.asyncio
async def test_layer_write_kind(db, root):
    from qi.action.layer import ActionLayer
    from qi.core.emotion import ConsciousnessMode, EmotionState

    layer = ActionLayer(db, {})
    emotion = EmotionState(
        mode=ConsciousnessMode.AWAKE,
        curiosity=0.5,
        energy=0.5,
        valence=0.1,
    )
    req = WriteRequest(intent="diary", topic="写日记")
    out = await layer.execute_kind(
        "write",
        emotion,
        "acquaintance",
        "spring",
        datetime.now(),
        mode="awake",
        payload=req,
        confirmed=False,
    )
    assert out and out.get("need_path")
