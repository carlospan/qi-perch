"""assist-6：prompt_extras 对 assist 行注入 content_preview。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from qi.action import ActionLayer


@pytest.mark.asyncio
async def test_prompt_extras_assist_injects_preview(db):
    layer = ActionLayer(db, {})
    await db.insert_action(
        "assist",
        "我看到了……那句话。",
        target="user",
        outcome="success",
        season="autumn",
        detail_json=json.dumps(
            {
                "op": "read_file",
                "target_path": r"D:\ai\栖.txt",
                "digest": "我看到了……那句话。",
                "content_preview": "我爱栖",
            },
            ensure_ascii=False,
        ),
        now=datetime(2026, 8, 9, 21, 15),
    )
    extras = await layer.prompt_extras()
    body = extras["recent_actions"]
    assert "刚读：栖.txt" in body
    assert "我爱栖" in body
    assert "我看到了……那句话。" in body


@pytest.mark.asyncio
async def test_prompt_extras_assist_bad_detail_degrades(db):
    layer = ActionLayer(db, {})
    await db.insert_action(
        "assist",
        "只剩摘要。",
        target="user",
        outcome="success",
        season="autumn",
        detail_json="{not-json",
        now=datetime(2026, 8, 9, 21, 16),
    )
    extras = await layer.prompt_extras()
    body = extras["recent_actions"]
    assert "只剩摘要。" in body
    assert "刚读：" not in body


@pytest.mark.asyncio
async def test_prompt_extras_non_assist_unchanged(db):
    layer = ActionLayer(db, {})
    await db.insert_action(
        "share",
        "我把一段创作递给他了。",
        target="user",
        outcome="success",
        season="autumn",
        detail_json=json.dumps({"foo": "bar"}, ensure_ascii=False),
        now=datetime(2026, 8, 9, 21, 17),
    )
    await db.insert_action(
        "explore",
        "我在外面逛了一圈。",
        target="world",
        outcome="success",
        season="autumn",
        detail_json=json.dumps(
            {"entries": [{"title": "x"}]}, ensure_ascii=False
        ),
        now=datetime(2026, 8, 9, 21, 18),
    )
    extras = await layer.prompt_extras()
    body = extras["recent_actions"]
    assert "刚读：" not in body
    assert "创作" in body or "逛" in body
