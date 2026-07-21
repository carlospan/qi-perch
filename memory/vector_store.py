"""向量记忆库——用语义距离找回「那天」的感觉。"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class CharNgramEmbeddingFunction(EmbeddingFunction):
    """
    离线字符 n-gram 嵌入。
    不依赖 HuggingFace 下载，中文短文本够用；后续可换成 MiniLM。
    """

    def __init__(self, dim: int = 384, n: int = 2):
        self.dim = dim
        self.n = n

    def name(self) -> str:
        return "char_ngram"

    def get_config(self) -> dict:
        return {"dim": self.dim, "n": self.n}

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", "", text)
        vec = [0.0] * self.dim
        if not text:
            return vec
        # 单字 + n-gram
        grams = list(text)
        for i in range(len(text) - self.n + 1):
            grams.append(text[i : i + self.n])
        for g in grams:
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class VectorStore:
    """ChromaDB 封装。嵌入式，不另起服务。"""

    COLLECTION_NAME = "narrative_memories"

    def __init__(self, persist_dir: str = "data/chroma"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self._ef = CharNgramEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
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
        self.collection.upsert(
            ids=[str(memory_id)],
            documents=[content],
            metadatas=[clean],
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
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

    def delete(self, memory_id: int) -> None:
        try:
            self.collection.delete(ids=[str(memory_id)])
        except Exception:
            pass

    def close(self) -> None:
        """释放底层文件句柄（Windows 上尤为重要）。"""
        try:
            if hasattr(self.client, "clear_system_cache"):
                self.client.clear_system_cache()
        except Exception:
            pass
        self.collection = None  # type: ignore
        self.client = None  # type: ignore
