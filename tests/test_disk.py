"""L7 disk：D: 列目录 + 打开本地文件。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from qi.action.disk import (
    DiskAction,
    DiskRequest,
    answer_listing_question,
    detect_disk_intent,
    looks_like_disk_intent,
    looks_like_listing_question,
    normalize_under_root,
    resolve_listing_followup,
)
from qi.action.permission import can_disk
from qi.storage.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "qi.db"))
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("qi.action.disk.DEFAULT_ALLOWED_ROOT", tmp_path)
    return tmp_path


def test_can_disk_acquaintance():
    assert can_disk("acquaintance") is True
    assert can_disk("friend") is True
    assert can_disk("stranger") is False


def test_normalize_rejects_outside_root(root):
    # 构造明确在 root 外的绝对路径
    other = root.parent / "not-allowed-sibling"
    other.mkdir(exist_ok=True)
    assert normalize_under_root(str(other), root=root) is None
    inside = root / "ok"
    inside.mkdir()
    got = normalize_under_root(str(inside), root=root)
    assert got is not None
    assert got == inside.resolve()


def test_looks_like_disk_intent():
    assert looks_like_disk_intent(r"列一下 D:\docs 有什么")
    assert looks_like_disk_intent(r"打开 D:\a\notes.txt")
    assert looks_like_disk_intent("栖你能看到d盘下的文件吗？")
    assert not looks_like_disk_intent("打开企微")
    assert not looks_like_disk_intent("打开 https://example.com")


@pytest.mark.asyncio
async def test_detect_capability_offer_list(root):
    req = await detect_disk_intent("栖你能看到d盘下的文件吗？")
    assert req is not None
    assert req.intent == "offer_list"


@pytest.mark.asyncio
async def test_detect_list_and_open():
    list_req = await detect_disk_intent(r"帮我列一下 D:\work")
    assert list_req is not None
    assert list_req.intent == "list_dir"

    open_req = await detect_disk_intent(r"打开 D:\work\a.txt")
    assert open_req is not None
    assert open_req.intent == "open_file"


@pytest.mark.asyncio
async def test_offer_list_promotes_list_dir(db, root):
    action = DiskAction(db)
    req = DiskRequest(intent="offer_list", path=str(root))
    gate = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert gate.get("outcome") == "success"
    assert gate.get("intent") == "list_dir"
    assert "能" in (gate.get("qi_line") or "") or "看到" in (gate.get("qi_line") or "")


@pytest.mark.asyncio
async def test_list_dir_confirm_then_list(db, root):
    folder = root / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("x", encoding="utf-8")
    (folder / "sub").mkdir()
    action = DiskAction(db)
    req = DiskRequest(intent="list_dir", path=str(folder))

    done = await action.execute(
        req, relationship_stage="acquaintance", confirmed=False
    )
    assert done.get("outcome") == "success"
    assert done.get("listing_sticky") is True
    line = done.get("qi_line") or ""
    assert "a.txt" in line
    assert "sub" in line
    assert "[文件]" in line
    assert "[目录]" in line
    assert "名字或序号" in line


def test_resolve_listing_followup_by_index_and_name(root):
    a = root / "a.txt"
    sub = root / "sub"
    listing = {
        "dir": str(root),
        "entries": [
            {"name": "a.txt", "path": str(a), "is_dir": False},
            {"name": "sub", "path": str(sub), "is_dir": True},
        ],
    }
    by_idx = resolve_listing_followup("打开第1个", listing)
    assert by_idx is not None
    assert by_idx.intent == "open_file"
    assert by_idx.path == str(a)

    by_name = resolve_listing_followup("打开 a.txt", listing)
    assert by_name is not None
    assert by_name.intent == "open_file"

    into = resolve_listing_followup("进 sub", listing)
    assert into is not None
    assert into.intent == "list_dir"
    assert into.path == str(sub)


def test_listing_question_doc_folder():
    listing = {
        "dir": "D:\\",
        "entries": [
            {"name": "docs", "path": "D:\\docs", "is_dir": True},
            {"name": "a.txt", "path": "D:\\a.txt", "is_dir": False},
        ],
    }
    assert looks_like_listing_question("刚才列的那些里，有文档文件夹吗")
    line = answer_listing_question("刚才列的那些里，有文档文件夹吗", listing)
    assert line is not None
    assert "docs" in line or "有" in line

    empty_dirs = {
        "dir": "D:\\",
        "entries": [{"name": "a.txt", "path": "D:\\a.txt", "is_dir": False}],
    }
    line2 = answer_listing_question("有文档文件夹吗", empty_dirs)
    assert line2 is not None
    assert "没看到" in line2


@pytest.mark.asyncio
async def test_list_dir_rejects_file(db, root):
    f = root / "only.txt"
    f.write_text("x", encoding="utf-8")
    action = DiskAction(db)
    req = DiskRequest(intent="list_dir", path=str(f))
    out = await action.execute(
        req, relationship_stage="friend", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"


@pytest.mark.asyncio
async def test_open_file_outside_root_fails(db, root):
    action = DiskAction(db)
    req = DiskRequest(intent="open_file", path=r"C:\Windows\notepad.exe")
    out = await action.execute(
        req, relationship_stage="friend", confirmed=True
    )
    assert out.get("outcome") == "failed_capability"
    assert "D 盘" in (out.get("qi_line") or "")


@pytest.mark.asyncio
async def test_open_file_launches(db, root):
    f = root / "note.txt"
    f.write_text("hello", encoding="utf-8")
    action = DiskAction(db)
    req = DiskRequest(intent="open_file", path=str(f))
    with patch.object(DiskAction, "_launch_path") as launch:
        gate = await action.execute(
            req, relationship_stage="acquaintance", confirmed=False
        )
        launch.assert_called_once()
    assert gate.get("outcome") == "success"
    assert "稍慢" in (gate.get("qi_line") or "")


@pytest.mark.asyncio
async def test_list_cap(db, root, monkeypatch):
    monkeypatch.setattr("qi.action.disk.LIST_CAP", 3)
    folder = root / "many"
    folder.mkdir()
    for i in range(5):
        (folder / f"f{i}.txt").write_text("x", encoding="utf-8")
    action = DiskAction(db)
    req = DiskRequest(intent="list_dir", path=str(folder))
    done = await action.execute(
        req, relationship_stage="friend", confirmed=True
    )
    assert "还有" in (done.get("qi_line") or "")


@pytest.mark.asyncio
async def test_layer_disk_kind(db, root):
    from qi.action.layer import ActionLayer
    from qi.core.emotion import ConsciousnessMode, EmotionState

    folder = root / "x"
    folder.mkdir()
    (folder / "t.txt").write_text("1", encoding="utf-8")
    layer = ActionLayer(db, {})
    emotion = EmotionState(
        mode=ConsciousnessMode.AWAKE,
        curiosity=0.5,
        energy=0.5,
        valence=0.1,
    )
    req = DiskRequest(intent="list_dir", path=str(folder))
    gate = await layer.execute_kind(
        "disk",
        emotion,
        "acquaintance",
        "spring",
        datetime.now(),
        mode="awake",
        payload=req,
        confirmed=False,
    )
    assert gate and gate.get("outcome") == "success"
