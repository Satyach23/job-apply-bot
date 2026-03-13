"""
ChromaDB vector store backend.

Stores document chunks in a persistent ChromaDB collection at
data/chroma/. ChromaDB handles its own similarity index so
no manual vector math is needed.

Requires: pip install chromadb
"""

from app.config import DATA_DIR
from app.vector_store.base import BaseVectorStore

CHROMA_DIR = DATA_DIR / "chroma"


class ChromaVectorStore(BaseVectorStore):
    def __init__(self) -> None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        # cosine distance so closer = more similar
        self._col = self._client.get_or_create_collection(
            name="document_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        doc_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        ids = [f"doc{doc_id}_chunk{i}" for i in range(len(chunks))]
        self._col.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"doc_id": doc_id} for _ in chunks],
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        total = self._col.count()
        if total == 0:
            return []

        k = min(top_k, total)
        res = self._col.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        if not res["documents"] or not res["documents"][0]:
            return []

        output = []
        for doc, meta, dist in zip(
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0],
        ):
            output.append(
                {
                    "chunk_text": doc,
                    "doc_id": meta["doc_id"],
                    "score": 1.0 - dist,  # cosine distance → similarity
                }
            )
        return output

    def delete_document(self, doc_id: int) -> None:
        existing = self._col.get(where={"doc_id": doc_id})
        if existing["ids"]:
            self._col.delete(ids=existing["ids"])
