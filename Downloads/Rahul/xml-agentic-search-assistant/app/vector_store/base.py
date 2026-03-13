"""
Abstract base class for vector store backends.

All backends must implement three operations:
  add_chunks      — index chunks + embeddings for a document
  search          — find top-K chunks by cosine similarity
  delete_document — remove all data for a given document ID
"""

from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    @abstractmethod
    def add_chunks(
        self,
        doc_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        """Store chunks and their embeddings for doc_id."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """
        Find the top_k most similar chunks to query_embedding.

        Returns:
            List of dicts with keys: chunk_text, doc_id, score.
            Sorted by score descending.
        """

    @abstractmethod
    def delete_document(self, doc_id: int) -> None:
        """Remove all chunks and embeddings for doc_id."""
