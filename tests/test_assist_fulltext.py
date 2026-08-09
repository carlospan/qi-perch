"""assist-7：全文分块 digest + narrative 内化。"""

from __future__ import annotations

from datetime import datetime

import pytest
from qi.action import assist as assist_mod
from qi.action.assist import AssistAction
from qi.action.permission import OUTCOME_FAILED_CAPABILITY, OUTCOME_SUCCESS


class _CountingLLM:
    def __init__(
        self, chunk_text: str = "这块有味道。", merge_text: str = "整体读完了。"
    ) -> None:
        self.chunk_text = chunk_text
        self.merge_text = merge_text
        self.calls: list[dict] = []

    async def call(
        self, purpose: str, messages: list[dict], temperature=None
    ) -> str:
        self.calls.append(
            {
                "purpose": purpose,
                "messages": messages,
                "temperature": temperature,
            }
        )
        user = ""
        for m in messages:
            if m.get("role") == "user":
                user = str(m.get("content") or "")
        if "片段感受" in user:
            return self.merge_text
        return self.chunk_text


class _FakeNarrative:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def save(
        self,
        content: str,
        importance: float,
        emotional_intensity: float = 0.5,
        source_event_ids: list[int] | None = None,
        tags: list[str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> int:
        self.saved.append(
            {
                "content": content,
                "importance": importance,
                "emotional_intensity": emotional_intensity,
                "tags": list(tags or []),
            }
        )
        return len(self.saved)


@pytest.mark.asyncio
async def test_assist_short_file_single_digest(db, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("短短一封信。", encoding="utf-8")
    llm = _CountingLLM("读到了那封短信。")
    narr = _FakeNarrative()
    assist = AssistAction(db, llm=llm, narrative=narr)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 22, 0),
    )
    assert result["outcome"] == OUTCOME_SUCCESS
    assert len(llm.calls) == 1
    assert llm.calls[0]["purpose"] == "consciousness"
    assert result["qi_line"] == "读到了那封短信。"
    assert "只读完了前面一部分" not in result["qi_line"]
    assert len(narr.saved) == 1
    assert "assist" in narr.saved[0]["tags"]
    assert "file_read" in narr.saved[0]["tags"]
    assert "note.txt" in narr.saved[0]["content"]


@pytest.mark.asyncio
async def test_assist_long_file_chunked(db, tmp_path):
    f = tmp_path / "long.txt"
    f.write_text("字" * 20_000, encoding="utf-8")
    llm = _CountingLLM("一块感受。", "合起来了。")
    narr = _FakeNarrative()
    assist = AssistAction(db, llm=llm, narrative=narr)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 22, 1),
    )
    assert result["outcome"] == OUTCOME_SUCCESS
    # 20_000 / 8000 = 3 块 + 1 合并
    assert len(llm.calls) == 4
    merge_calls = [
        c
        for c in llm.calls
        if any(
            "片段感受" in str(m.get("content") or "")
            for m in c["messages"]
            if m.get("role") == "user"
        )
    ]
    assert len(merge_calls) == 1
    assert result["qi_line"] == "合起来了。"
    assert len(narr.saved) == 3


@pytest.mark.asyncio
async def test_assist_oversize_chunks_truncated(db, tmp_path):
    f = tmp_path / "huge_text.txt"
    # 7 块：7 * 8000 = 56000 字符
    f.write_text("长" * (assist_mod._DIGEST_CHUNK_LEN * 7), encoding="utf-8")
    llm = _CountingLLM("块。", "总。")
    narr = _FakeNarrative()
    assist = AssistAction(db, llm=llm, narrative=narr)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 22, 2),
    )
    assert result["outcome"] == OUTCOME_SUCCESS
    # 6 块 + 1 合并
    assert len(llm.calls) == 7
    assert len(narr.saved) == 6
    assert "只读完了前面一部分" in result["qi_line"]


@pytest.mark.asyncio
async def test_assist_huge_file_fails_honest(db, tmp_path, monkeypatch):
    # 任意非空文件在 _MAX_FILE_BYTES=0 时都会触发 1MB 保护
    monkeypatch.setattr(assist_mod, "_MAX_FILE_BYTES", 0)
    f = tmp_path / "big.bin"
    f.write_text("x", encoding="utf-8")
    llm = _CountingLLM("不该走到 digest")
    narr = _FakeNarrative()
    assist = AssistAction(db, llm=llm, narrative=narr)
    result = await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 22, 3),
    )
    assert result["outcome"] == OUTCOME_FAILED_CAPABILITY
    assert "太大了" in result["qi_line"]
    assert len(llm.calls) == 0
    assert narr.saved == []
    rows = await db.list_recent_actions(limit=5)
    assist_rows = [r for r in rows if r.get("kind") == "assist"]
    assert assist_rows
    assert assist_rows[0]["outcome"] == OUTCOME_FAILED_CAPABILITY


@pytest.mark.asyncio
async def test_assist_narrative_not_fulltext(db, tmp_path):
    f = tmp_path / "secret.txt"
    full = "绝密正文ABCDEFG" * 100
    f.write_text(full, encoding="utf-8")
    llm = _CountingLLM("心里暖了一下。")
    narr = _FakeNarrative()
    assist = AssistAction(db, llm=llm, narrative=narr)
    await assist.execute(
        "read_file",
        str(f),
        relationship_stage="friend",
        trust=0.7,
        confirmed=True,
        season="spring",
        now=datetime(2026, 8, 9, 22, 4),
    )
    assert narr.saved
    blob = narr.saved[0]["content"]
    assert "心里暖了一下" in blob
    assert full not in blob
    assert "绝密正文ABCDEFG" * 20 not in blob
