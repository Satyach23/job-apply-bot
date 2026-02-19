"""ACE POC - Simple RAG service (ChromaDB + sentence-transformers)."""
from __future__ import annotations

import os
from typing import Any

from config import settings

# Lazy init to avoid loading models at import
_chroma_client = None
_collection = None
_embedding_model = None

COLLECTION_NAME = "ace_sections"


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def _get_chroma():
    global _chroma_client, _collection
    if _chroma_client is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "ACE analytical sections"},
        )
    return _chroma_client, _collection


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_embedding_model()
    return model.encode(texts, convert_to_numpy=True).tolist()


def add_sections(sections: list[dict[str, Any]]) -> None:
    """
    Add sections to the vector store.
    Each section: {id, title, content, title_path, publication_id}
    """
    client, coll = _get_chroma()
    if not sections:
        return

    ids = [str(s["id"]) for s in sections]
    texts = [
        f"{s.get('title', '')} {s.get('content', '')}"[:8000]
        for s in sections
    ]
    embeddings = _embed(texts)
    meta = [
        {
            "title": s.get("title", "")[:200],
            "title_path": s.get("title_path", "")[:200],
            "publication_id": str(s.get("publication_id", "")),
        }
        for s in sections
    ]
    coll.upsert(ids=ids, embeddings=embeddings, metadatas=meta)


def search_sections(
    query: str,
    top_k: int | None = None,
    publication_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Semantic search for sections relevant to query.
    Returns list of {id, title, title_path, publication_id, distance}.
    """
    coll = _get_chroma()[1]
    k = top_k or settings.rag_top_k
    query_emb = _embed([query])

    where = None
    if publication_ids:
        where = {"publication_id": [str(pid) for pid in publication_ids]}

    results = coll.query(
        query_embeddings=query_emb,
        n_results=min(k * 2, 20),  # Fetch extra in case of filter
        where=where,
    )

    out = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            meta = (results["metadatas"] or [[]])[0]
            m = meta[i] if i < len(meta) else {}
            dists = results["distances"][0] if results.get("distances") else [0] * len(results["ids"][0])
            dist = dists[i] if i < len(dists) else 0
            out.append({
                "id": int(doc_id),
                "title": m.get("title", ""),
                "title_path": m.get("title_path", ""),
                "publication_id": int(m.get("publication_id", 0)) if m.get("publication_id") else 0,
                "distance": float(dist),
            })
        out = out[:k]

    return out


def clear_collection() -> None:
    """Clear all sections (for reseeding)."""
    client, _ = _get_chroma()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
