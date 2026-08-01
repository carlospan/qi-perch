"""真实 BGE ONNX：同义改写命中（模型文件缺失则跳过）。"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path

import pytest
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import (
    DEFAULT_BGE_DIR,
    EMBEDDING_ID_BGE,
    VectorStore,
    bge_model_files_present,
)
from qi.storage.database import Database

pytestmark = pytest.mark.skipif(
    not bge_model_files_present(DEFAULT_BGE_DIR),
    reason="本地无 BGE ONNX（data/models/bge-small-zh-v1.5/），跳过语义检索",
)


@pytest.mark.asyncio
async def test_paraphrase_retrieval_hits():
    """「你教我的助眠方法」↔「睡不着时教的方法」。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        chroma = str(Path(tmp) / "chroma")
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()
        vs = VectorStore(
            persist_dir=chroma,
            model_dir=DEFAULT_BGE_DIR,
            prefer_bge=True,
        )
        assert vs.embedding_id == EMBEDDING_ID_BGE
        narrative = NarrativeMemory(db, vs)
        await narrative.save(
            content="那天你教我的助眠方法，后来夜里睡不着就用",
            importance=0.9,
            emotional_intensity=0.6,
        )
        await narrative.save(
            content="一起去看了场电影，喜剧片",
            importance=0.5,
            emotional_intensity=0.3,
        )
        found = await narrative.search("睡不着时教的方法", top_k=3)
        assert found, "语义检索应命中助眠相关记忆"
        assert any("助眠" in m["content"] for m in found)
        vs.close()
        await db.close()
        gc.collect()
