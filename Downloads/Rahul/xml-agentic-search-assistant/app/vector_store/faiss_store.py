"""
FAISS vector store backend.

Persists the FAISS index at data/faiss/index.faiss and a companion
metadata file at data/faiss/metadata.json that maps vector positions
to (chunk_text, doc_id) pairs.

Uses IndexFlatIP (inner-product) — cosine similarity when input
vectors are L2-normalised, which the embedder guarantees.

Note: FAISS does not support in-place deletion. Removing a document
rebuilds the index from the remaining vectors (O(n) but acceptable
for moderate document counts).

Requires: pip install faiss-cpu
"""

import json

import numpy as np

from app.config import DATA_DIR
from app.vector_store.base import BaseVectorStore

FAISS_DIR = DATA_DIR / "faiss"
INDEX_PATH = FAISS_DIR / "index.faiss"
META_PATH = FAISS_DIR / "metadata.json"
DIM = 384  # must match embedder.EMBEDDING_DIM


class FAISSVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        import faiss

        self._faiss = faiss
        FAISS_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if INDEX_PATH.exists() and META_PATH.exists():
            self._index = self._faiss.read_index(str(INDEX_PATH))
            with open(META_PATH) as f:
                self._meta: list[dict] = json.load(f)
        else:
            self._index = self._faiss.IndexFlatIP(DIM)
            self._meta = []

    def _save(self) -> None:
        self._faiss.write_index(self._index, str(INDEX_PATH))
        with open(META_PATH, "w") as f:
            json.dump(self._meta, f)

    def add_chunks(
        self,
        doc_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        vecs = np.array(embeddings, dtype=np.float32)
        self._index.add(vecs)
        for chunk in chunks:
            self._meta.append({"chunk_text": chunk, "doc_id": doc_id})
        self._save()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        if self._index.ntotal == 0:
            return []

        q = np.array([query_embedding], dtype=np.float32)
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(q, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._meta):
                results.append(
                    {
                        "chunk_text": self._meta[idx]["chunk_text"],
                        "doc_id": self._meta[idx]["doc_id"],
                        "score": float(score),
                    }
                )
        return results

    def delete_document(self, doc_id: int) -> None:
        keep = [i for i, m in enumerate(self._meta) if m["doc_id"] != doc_id]
        if len(keep) == len(self._meta):
            return  # nothing to remove

        if not keep:
            self._index = self._faiss.IndexFlatIP(DIM)
            self._meta = []
        else:
            # Reconstruct all stored vectors, keep only the surviving ones
            all_vecs = np.zeros((self._index.ntotal, DIM), dtype=np.float32)
            self._index.reconstruct_n(0, self._index.ntotal, all_vecs)
            kept_vecs = all_vecs[keep]
            self._index = self._faiss.IndexFlatIP(DIM)
            self._index.add(kept_vecs)
            self._meta = [self._meta[i] for i in keep]

        self._save()
