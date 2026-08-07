"""BGE / n-gram 回退与向量重建（不依赖真实 100MB 下载）。"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from qi.memory.narrative import NarrativeMemory
from qi.memory.vector_store import (
    EMBEDDING_ID_BGE,
    EMBEDDING_ID_NGRAM,
    BgeLoadError,
    BgeOnnxEmbeddingFunction,
    CharNgramEmbeddingFunction,
    VectorStore,
    bge_model_files_present,
)
from qi.storage.database import Database


def test_bge_load_missing_falls_back_to_ngram():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        vs = VectorStore(
            persist_dir=str(Path(tmp) / "chroma"),
            model_dir=str(Path(tmp) / "no-model"),
            prefer_bge=True,
        )
        assert isinstance(vs._ef, CharNgramEmbeddingFunction)
        assert vs.embedding_id == EMBEDDING_ID_NGRAM
        vs.add(1, "记得他说他最近在学吉他")
        found = vs.search("吉他", top_k=3)
        assert any("吉他" in m["content"] for m in found)
        vs.close()
        gc.collect()


def test_search_swallows_exceptions():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        vs = VectorStore(
            persist_dir=str(Path(tmp) / "chroma"),
            prefer_bge=False,
        )
        vs.collection.query = lambda **kwargs: (_ for _ in ()).throw(  # type: ignore
            RuntimeError("boom")
        )
        assert vs.search("任意") == []
        vs.close()
        gc.collect()


def test_add_failure_does_not_raise():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        vs = VectorStore(
            persist_dir=str(Path(tmp) / "chroma"),
            prefer_bge=False,
        )

        def boom(**kwargs):
            raise RuntimeError("upsert failed")

        vs.collection.upsert = boom  # type: ignore[method-assign]
        vs.add(9, "正文在 sqlite")  # 不得抛
        vs.close()
        gc.collect()


def test_search_empty_while_needs_reindex():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        vs = VectorStore(
            persist_dir=str(Path(tmp) / "chroma"),
            prefer_bge=False,
        )
        vs.add(1, "一条记忆")
        vs.needs_reindex = True
        assert vs.search("记忆") == []
        vs.close()
        gc.collect()


@pytest.mark.asyncio
async def test_embedding_mismatch_triggers_reindex_from_sqlite():
    """旧 collection 标识不符 → 删库 → 从 SQLite 回灌。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        chroma = str(Path(tmp) / "chroma")
        db = Database(str(Path(tmp) / "qi.db"))
        await db.initialize()

        vs1 = VectorStore(persist_dir=chroma, prefer_bge=False)
        narrative = NarrativeMemory(db, vs1)
        mid = await narrative.save(
            content="你教我的助眠方法，夜里很管用",
            importance=0.9,
            emotional_intensity=0.5,
        )
        assert vs1.embedding_id == EMBEDDING_ID_NGRAM
        vs1.close()

        # 模拟升级到 BGE：加载「成功」但 EF 仍用 n-gram 实现（只测重建流程）
        with patch(
            "qi.memory.vector_store.BgeOnnxEmbeddingFunction",
            side_effect=lambda model_dir=None: CharNgramEmbeddingFunction(),
        ):
            vs2 = VectorStore(persist_dir=chroma, prefer_bge=True)

        assert vs2.embedding_id == EMBEDDING_ID_BGE
        assert vs2.needs_reindex is True
        assert vs2.collection.count() == 0

        narrative2 = NarrativeMemory(db, vs2)
        n = await narrative2.reindex_vectors()
        assert n >= 1
        assert vs2.needs_reindex is False
        found = vs2.search("助眠", top_k=3)
        assert any(m["id"] == mid for m in found)

        # 同标识再开：不应再次要求回灌
        vs2.close()
        with patch(
            "qi.memory.vector_store.BgeOnnxEmbeddingFunction",
            side_effect=lambda model_dir=None: CharNgramEmbeddingFunction(),
        ):
            vs3 = VectorStore(persist_dir=chroma, prefer_bge=True)
        assert vs3.needs_reindex is False
        assert vs3.collection.count() >= 1
        vs3.close()

        await db.close()
        gc.collect()


def test_bge_load_error_message():
    with pytest.raises(BgeLoadError):
        BgeOnnxEmbeddingFunction(model_dir="definitely/missing/path")


def test_bge_init_is_lazy_until_embed():
    """构造不拉 ORT；缺文件仍在 __init__ 失败。有文件时 session 延后到首次嵌入。"""
    root = Path("data/models/bge-small-zh-v1.5")
    if not bge_model_files_present(root):
        pytest.skip("本机无 BGE 模型文件")
    ef = BgeOnnxEmbeddingFunction(model_dir=root)
    assert ef._session is None
    vec = ef(["你好"])[0]
    assert ef._session is not None
    assert len(vec) == 512


def test_bge_files_helper():
    assert bge_model_files_present("no/such/dir") is False


def test_prefer_bge_false_skips_model():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        vs = VectorStore(
            persist_dir=str(Path(tmp) / "chroma"),
            prefer_bge=False,
        )
        assert vs.embedding_id == EMBEDDING_ID_NGRAM
        meta = vs.collection.metadata or {}
        assert meta.get("qi_embedding") == EMBEDDING_ID_NGRAM
        vs.close()
        gc.collect()
