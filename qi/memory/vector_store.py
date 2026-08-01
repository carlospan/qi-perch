"""向量记忆库——用语义距离找回「那天」的感觉。"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger("qi.memory.vector")

# collection metadata 中的 embedding 标识——维数/算法变了必须重建
EMBEDDING_ID_NGRAM = "char_ngram-384"
EMBEDDING_ID_BGE = "bge-small-zh-v1.5-onnx-v1"

DEFAULT_BGE_DIR = Path("data/models/bge-small-zh-v1.5")
# BAAI 主库无 onnx/；实测改用 onnx-community（见换机搭建.md）
BGE_HF_REPO = "onnx-community/bge-small-zh-v1.5-ONNX"
BGE_HF_FILES = (
    "onnx/model.onnx",
    "onnx/model.onnx_data",
    "tokenizer.json",
    "tokenizer_config.json",
    "config.json",
)


class BgeLoadError(Exception):
    """BGE ONNX 模型不可用（缺文件或加载失败）。"""


class CharNgramEmbeddingFunction(EmbeddingFunction):
    """
    离线字符 n-gram 嵌入。
    不依赖模型下载；BGE 不可用时的回退路径。
    """

    def __init__(self, dim: int = 384, n: int = 2):
        self.dim = dim
        self.n = n

    @staticmethod
    def name() -> str:
        return "char_ngram"

    def get_config(self) -> dict:
        return {"dim": self.dim, "n": self.n}

    @staticmethod
    def build_from_config(config: dict) -> CharNgramEmbeddingFunction:
        return CharNgramEmbeddingFunction(
            dim=int(config.get("dim", 384)),
            n=int(config.get("n", 2)),
        )

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", "", text)
        vec = [0.0] * self.dim
        if not text:
            return vec
        grams = list(text)
        for i in range(len(text) - self.n + 1):
            grams.append(text[i : i + self.n])
        for g in grams:
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def bge_model_files_present(model_dir: Path | str | None = None) -> bool:
    """同义改写等真实模型测试的 skipif 条件。"""
    root = Path(model_dir) if model_dir else DEFAULT_BGE_DIR
    return (root / "onnx" / "model.onnx").is_file() and (
        root / "tokenizer.json"
    ).is_file()


def ensure_bge_model(model_dir: Path | str | None = None) -> Path:
    """
    下载 BGE ONNX 到本地缓存（尊重 HF_ENDPOINT 镜像）。
    BAAI/bge-small-zh-v1.5 无 onnx/ 目录，改用 onnx-community 同源权重。
    """
    root = Path(model_dir) if model_dir else DEFAULT_BGE_DIR
    root.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as e:
        raise BgeLoadError("缺少 huggingface_hub，无法下载模型") from e

    for rel in BGE_HF_FILES:
        hf_hub_download(
            repo_id=BGE_HF_REPO,
            filename=rel,
            local_dir=str(root),
        )
    if not bge_model_files_present(root):
        raise BgeLoadError(f"下载后仍缺模型文件：{root}")
    return root


class BgeOnnxEmbeddingFunction(EmbeddingFunction):
    """
    BAAI/bge-small-zh-v1.5 的本地 ONNX 嵌入（512 维）。
    池化：官方 CLS；归一化：L2（本 ONNX 的 sentence_embedding 输出已是该结果）。
    """

    def __init__(self, model_dir: Path | str | None = None):
        root = Path(model_dir) if model_dir else DEFAULT_BGE_DIR
        if not bge_model_files_present(root):
            raise BgeLoadError(f"BGE 模型文件缺失：{root}")
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            raise BgeLoadError(f"缺少运行依赖：{e}") from e

        self._np = np
        self.model_dir = root
        self.dim = 512
        try:
            self._tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
            self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
            self._tokenizer.enable_truncation(max_length=512)
            self._session = ort.InferenceSession(
                str(root / "onnx" / "model.onnx"),
                providers=["CPUExecutionProvider"],
            )
        except Exception as e:
            raise BgeLoadError(f"BGE ONNX 加载失败：{e}") from e

        outs = {o.name for o in self._session.get_outputs()}
        self._use_sentence = "sentence_embedding" in outs
        self._out_names = (
            ["sentence_embedding"]
            if self._use_sentence
            else ["last_hidden_state"]
        )

    @staticmethod
    def name() -> str:
        return "bge-small-zh-v1.5-onnx"

    def get_config(self) -> dict:
        return {
            "model_id": "BAAI/bge-small-zh-v1.5",
            "onnx_repo": BGE_HF_REPO,
            "dim": self.dim,
            "path": str(self.model_dir),
            "pooling": "cls",
            "normalize": "l2",
        }

    @staticmethod
    def build_from_config(config: dict) -> BgeOnnxEmbeddingFunction:
        return BgeOnnxEmbeddingFunction(model_dir=config.get("path"))

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        np = self._np
        enc = self._tokenizer.encode(text or "")
        ids = np.array([enc.ids], dtype=np.int64)
        mask = np.array([enc.attention_mask], dtype=np.int64)
        token_types = np.zeros_like(ids)
        feeds = {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": token_types,
        }
        outputs = self._session.run(self._out_names, feeds)
        if self._use_sentence:
            vec = outputs[0][0]
        else:
            # CLS + L2（官方用法）
            cls = outputs[0][0, 0]
            norm = float(np.linalg.norm(cls)) or 1.0
            vec = cls / norm
        return [float(x) for x in vec]


class VectorStore:
    """ChromaDB 封装。嵌入式，不另起服务。"""

    COLLECTION_NAME = "narrative_memories"

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        *,
        model_dir: str | Path | None = None,
        prefer_bge: bool = True,
    ):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.needs_reindex = False
        self.embedding_id = EMBEDDING_ID_NGRAM
        self._ef: EmbeddingFunction = CharNgramEmbeddingFunction()

        if prefer_bge:
            try:
                self._ef = BgeOnnxEmbeddingFunction(model_dir=model_dir)
                self.embedding_id = EMBEDDING_ID_BGE
            except BgeLoadError as e:
                logger.warning("BGE 不可用，回退字符 n-gram：%s", e)
                self._ef = CharNgramEmbeddingFunction()
                self.embedding_id = EMBEDDING_ID_NGRAM

        self.collection = self._open_or_migrate_collection()

    def _collection_embedding_id(self, name: str) -> str | None:
        try:
            col = self.client.get_collection(name=name)
        except Exception:
            return None
        meta = col.metadata or {}
        return meta.get("qi_embedding")

    def _open_or_migrate_collection(self):
        """标识不匹配则删旧 collection，标记 needs_reindex 供 restore 回灌。"""
        existing_id = None
        had_rows = False
        try:
            old = self.client.get_collection(name=self.COLLECTION_NAME)
            existing_id = (old.metadata or {}).get("qi_embedding")
            had_rows = old.count() > 0
        except Exception:
            old = None

        if old is not None and existing_id == self.embedding_id:
            return self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    "qi_embedding": self.embedding_id,
                },
                embedding_function=self._ef,
            )

        if old is not None:
            logger.warning(
                "向量索引 embedding 不匹配（旧=%s 新=%s），删除旧 collection 待回灌",
                existing_id,
                self.embedding_id,
            )
            try:
                self.client.delete_collection(self.COLLECTION_NAME)
            except Exception:
                logger.exception("删除旧向量 collection 失败")
            if had_rows:
                self.needs_reindex = True

        return self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine",
                "qi_embedding": self.embedding_id,
            },
            embedding_function=self._ef,
        )

    def add(self, memory_id: int, content: str, metadata: dict | None = None) -> None:
        meta = metadata or {}
        clean = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            else:
                clean[k] = str(v)
        # Chroma 拒收空 metadata dict
        if not clean:
            clean = {"kind": "narrative"}
        try:
            self.collection.upsert(
                ids=[str(memory_id)],
                documents=[content],
                metadatas=[clean],
            )
        except Exception:
            # 正文在 SQLite；索引漏一条不丢记忆、不炸调用方
            logger.warning(
                "向量索引写入失败 id=%s", memory_id, exc_info=True
            )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        try:
            if self.needs_reindex:
                logger.debug("向量索引待回灌，本次检索返回空")
                return []
            count = self.collection.count()
            if count == 0:
                return []
            n = min(top_k, count)
            results = self.collection.query(query_texts=[query], n_results=n)
            memories: list[dict] = []
            ids = results.get("ids") or [[]]
            docs = results.get("documents") or [[]]
            dists = results.get("distances") or [[]]
            metas = results.get("metadatas") or [[]]
            if not ids[0]:
                return []
            for i in range(len(ids[0])):
                memories.append(
                    {
                        "id": int(ids[0][i]),
                        "content": docs[0][i],
                        "distance": dists[0][i] if dists[0] else 0.0,
                        "metadata": metas[0][i] if metas[0] else {},
                    }
                )
            return memories
        except Exception:
            logger.warning("向量检索失败，返回空", exc_info=True)
            return []

    def delete(self, memory_id: int) -> None:
        try:
            self.collection.delete(ids=[str(memory_id)])
        except Exception:
            pass

    def reindex_documents(self, rows: list[dict]) -> int:
        """
        从权威源（SQLite 叙事行）全量回灌。
        每行需含 id、content；可选 importance / emotional_intensity。
        """
        n = 0
        for row in rows:
            mid = int(row["id"])
            content = str(row.get("content") or "")
            if not content:
                continue
            self.add(
                mid,
                content,
                metadata={
                    "importance": float(row.get("importance") or 0.5),
                    "emotional_intensity": float(
                        row.get("emotional_intensity") or 0.5
                    ),
                },
            )
            n += 1
        self.needs_reindex = False
        return n

    def close(self) -> None:
        """释放底层文件句柄（Windows 上尤为重要）。"""
        try:
            if hasattr(self.client, "clear_system_cache"):
                self.client.clear_system_cache()
        except Exception:
            pass
        self.collection = None  # type: ignore
        self.client = None  # type: ignore
