"""
Vector store factory — returns the configured backend.

Set VECTOR_BACKEND in .env to select the backend:
  sqlite  (default) — stores vectors as JSON BLOBs in SQLite,
                      cosine similarity computed in Python/numpy.
  chroma            — uses ChromaDB with a persistent local collection.
  faiss             — uses FAISS IndexFlatIP with a JSON metadata file.
"""

from app.config import VECTOR_BACKEND
from app.vector_store.base import BaseVectorStore

_store: "BaseVectorStore | None" = None


def get_vector_store() -> BaseVectorStore:
    """
    Return the singleton vector store for the configured backend.
    Lazily initialised on first call.
    """
    global _store
    if _store is not None:
        return _store

    if VECTOR_BACKEND == "chroma":
        from app.vector_store.chroma_store import ChromaVectorStore
        _store = ChromaVectorStore()
    elif VECTOR_BACKEND == "faiss":
        from app.vector_store.faiss_store import FAISSVectorStore
        _store = FAISSVectorStore()
    else:
        from app.vector_store.sqlite_store import SQLiteVectorStore
        _store = SQLiteVectorStore()
        _store.init()

    return _store
