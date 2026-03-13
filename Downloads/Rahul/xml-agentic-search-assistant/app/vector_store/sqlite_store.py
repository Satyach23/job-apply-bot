"""
SQLite vector store — stores embeddings as JSON in a dedicated table
and performs cosine similarity search in Python using numpy.

This backend requires no native extensions and works out-of-the-box
with any standard Python/SQLite installation.

Tables managed here (separate from the main app tables):
  document_embeddings  — (chunk_id, document_id, embedding JSON)
"""

import json
import sqlite3

import numpy as np

from app.config import DB_PATH
from app.vector_store.base import BaseVectorStore


class SQLiteVectorStore(BaseVectorStore):
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        """Create the embeddings table if it doesn't exist."""
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id    INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                embedding   TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_emb_doc
                ON document_embeddings(document_id);
        """)
        conn.commit()
        conn.close()

    def add_chunks(
        self,
        doc_id: int,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        conn = self._connect()
        # Fetch the chunk IDs we inserted in storage.insert_chunks
        rows = conn.execute(
            "SELECT id FROM document_chunks WHERE document_id = ? ORDER BY chunk_index",
            (doc_id,),
        ).fetchall()
        chunk_ids = [r["id"] for r in rows]

        for chunk_id, emb in zip(chunk_ids, embeddings):
            conn.execute(
                "INSERT INTO document_embeddings (chunk_id, document_id, embedding) "
                "VALUES (?, ?, ?)",
                (chunk_id, doc_id, json.dumps(emb)),
            )
        conn.commit()
        conn.close()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            """SELECT de.document_id, de.embedding, dc.chunk_text
               FROM document_embeddings de
               JOIN document_chunks dc ON dc.id = de.chunk_id"""
        ).fetchall()
        conn.close()

        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        results = []
        for row in rows:
            emb = np.array(json.loads(row["embedding"]), dtype=np.float32)
            score = float(np.dot(q, emb))
            results.append(
                {
                    "chunk_text": row["chunk_text"],
                    "doc_id": row["document_id"],
                    "score": score,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def delete_document(self, doc_id: int) -> None:
        conn = self._connect()
        conn.execute(
            "DELETE FROM document_embeddings WHERE document_id = ?",
            (doc_id,),
        )
        conn.commit()
        conn.close()
