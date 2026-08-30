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
        fake_bge = Path(tmp) / "fake-bge"
        _plant_minimal_bge_files(fake_bge)
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

        # 模拟升级到 BGE：解析命中假目录；EF 仍用 n-gram 实现（只测重建流程）
        with (
            patch(
                "qi.memory.vector_store.resolve_bge_model_dir",
                return_value=fake_bge,
            ),
            patch(
                "qi.memory.vector_store.BgeOnnxEmbeddingFunction",
                side_effect=lambda model_dir=None: CharNgramEmbeddingFunction(),
            ),
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
        with (
            patch(
                "qi.memory.vector_store.resolve_bge_model_dir",
                return_value=fake_bge,
            ),
            patch(
                "qi.memory.vector_store.BgeOnnxEmbeddingFunction",
                side_effect=lambda model_dir=None: CharNgramEmbeddingFunction(),
            ),
        ):
            vs3 = VectorStore(persist_dir=chroma, prefer_bge=True)
        assert vs3.needs_reindex is False
        assert vs3.collection.count() >= 1
        vs3.close()

        await db.close()
        gc.collect()


def _plant_minimal_bge_files(root: Path) -> None:
    (root / "onnx").mkdir(parents=True, exist_ok=True)
    (root / "onnx" / "model.onnx").write_bytes(b"fake")
    (root / "tokenizer.json").write_text("{}", encoding="utf-8")


def test_resolve_prefers_env_then_explicit(monkeypatch, tmp_path):
    from qi.memory.vector_store import ENV_BGE_DIR, resolve_bge_model_dir

    env_dir = tmp_path / "env-bge"
    dataish = tmp_path / "data-bge"
    explicit = tmp_path / "explicit-bge"
    _plant_minimal_bge_files(env_dir)
    _plant_minimal_bge_files(dataish)
    _plant_minimal_bge_files(explicit)

    monkeypatch.setenv(ENV_BGE_DIR, str(env_dir))
    assert resolve_bge_model_dir(explicit) == env_dir.resolve()

    monkeypatch.delenv(ENV_BGE_DIR, raising=False)
    assert resolve_bge_model_dir(explicit) == explicit.resolve()


def test_resolve_explicit_missing_does_not_fall_through(monkeypatch, tmp_path):
    """配置了路径但缺文件 → None，即使别处有模也不偷用（测隔离）。"""
    from qi.memory.vector_store import ENV_BGE_DIR, resolve_bge_model_dir

    monkeypatch.delenv(ENV_BGE_DIR, raising=False)
    other = tmp_path / "other-good"
    _plant_minimal_bge_files(other)
    monkeypatch.setattr(
        "qi.memory.vector_store.bundled_bge_candidates",
        lambda: [other],
    )
    monkeypatch.setattr(
        "qi.memory.vector_store.under_data",
        lambda *parts: tmp_path / "nope" / Path(*[str(p) for p in parts]),
    )
    assert resolve_bge_model_dir(tmp_path / "missing") is None


def test_resolve_data_then_bundled(monkeypatch, tmp_path):
    from qi.memory.vector_store import ENV_BGE_DIR, resolve_bge_model_dir

    monkeypatch.delenv(ENV_BGE_DIR, raising=False)
    data_dir = tmp_path / "models" / "bge-small-zh-v1.5"
    bundled = tmp_path / "resources" / "bge-small-zh-v1.5"
    _plant_minimal_bge_files(bundled)

    monkeypatch.setattr(
        "qi.memory.vector_store.under_data",
        lambda *parts: tmp_path.joinpath(*[str(p) for p in parts]),
    )
    monkeypatch.setattr(
        "qi.memory.vector_store.bundled_bge_candidates",
        lambda: [bundled],
    )
    # 数据根无 → 用资源
    assert resolve_bge_model_dir(None) == bundled.resolve()

    _plant_minimal_bge_files(data_dir)
    assert resolve_bge_model_dir(None) == data_dir.resolve()


def test_resolve_none_when_empty(monkeypatch, tmp_path):
    from qi.memory.vector_store import ENV_BGE_DIR, resolve_bge_model_dir

    monkeypatch.delenv(ENV_BGE_DIR, raising=False)
    monkeypatch.setattr(
        "qi.memory.vector_store.under_data",
        lambda *parts: tmp_path / "empty" / Path(*[str(p) for p in parts]),
    )
    monkeypatch.setattr(
        "qi.memory.vector_store.bundled_bge_candidates",
        lambda: [tmp_path / "nope"],
    )
    assert resolve_bge_model_dir(None) is None


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
