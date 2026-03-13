"""
RAG search tools — called by the RAG agent to retrieve information.

Three tools:
  search_metadata — full-text keyword search on SQLite extracted_fields
  search_content  — semantic similarity search on the vector store
  no_info_found   — sentinel when neither tool returns results
"""

from typing import Optional

from app import storage
from app.embedder import embed_one
from app.vector_store import get_vector_store


def search_metadata(
    query: str,
    doc_id: Optional[int] = None,
) -> list[dict]:
    """
    Search the SQLite extracted_fields table for keyword matches.

    Checks all text columns (section, sub_section, title, type,
    lmi_id, file_name) case-insensitively against the query.

    Args:
        query: Keywords to search for.
        doc_id: If given, restrict search to that document.

    Returns:
        Matching extracted_field rows as dicts (up to 20).
    """
    if doc_id:
        fields = storage.get_extracted_fields(doc_id)
    else:
        fields = storage.get_all_extracted_fields()

    q = query.lower()
    matches = []
    for f in fields:
        haystack = " ".join(
            str(f.get(col, ""))
            for col in ("section", "sub_section", "title", "type", "lmi_id", "file_name", "section_text")
        ).lower()
        if q in haystack:
            matches.append(f)

    return matches[:20]


def search_content(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic similarity search over document chunks in the vector store.

    Embeds the query, then retrieves the top_k most similar chunks.

    Args:
        query: Natural language question or keywords.
        top_k: Number of results to return.

    Returns:
        List of dicts with chunk_text, doc_id, score.
    """
    q_emb = embed_one(query)
    store = get_vector_store()
    return store.search(q_emb, top_k=top_k)


def no_info_found() -> str:
    """Triggered when neither metadata nor content search returns results."""
    return "No information found"
