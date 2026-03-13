"""
Embedding generation using sentence-transformers.

Uses the lightweight all-MiniLM-L6-v2 model (384 dimensions).
The model is downloaded on first use (~80 MB from HuggingFace)
and cached locally by sentence-transformers.

All embeddings are L2-normalized so that cosine similarity
equals the dot product — which simplifies both SQLite and
FAISS inner-product search.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: "SentenceTransformer | None" = None
EMBEDDING_DIM = 384


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts and return normalized float vectors.

    Args:
        texts: List of strings to embed.

    Returns:
        List of 384-dim float lists, one per input string.
    """
    if not texts:
        return []
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()


def embed_one(text: str) -> list[float]:
    """Embed a single string and return its normalized vector."""
    return embed([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two normalized vectors.
    Since vectors are already L2-normalized, this is just the dot product.
    """
    return float(np.dot(np.array(a), np.array(b)))
