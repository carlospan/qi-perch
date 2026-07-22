"""共享测试夹具。"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from qi.storage.database import Database


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    """临时 SQLite Database，测完关闭。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        database = Database(str(Path(tmp) / "qi.db"))
        await database.initialize()
        try:
            yield database
        finally:
            await database.close()
