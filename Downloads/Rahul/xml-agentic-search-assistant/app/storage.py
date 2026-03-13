"""
SQLite storage layer for documents and extracted fields.

Provides CRUD operations for two tables:
  - documents: one row per uploaded file (metadata + LLM response)
  - extracted_fields: one row per section extracted from a document

All database access goes through this module — no other module
imports sqlite3 directly. This makes it easy to swap the storage
backend in the future (e.g. to PostgreSQL) without touching the
rest of the codebase.
"""

import sqlite3
from typing import Any, Optional

from app.config import DB_PATH


# -------------------------------------------------------------------
# Database connection helper
# -------------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    """
    Create a SQLite connection with row_factory enabled.

    Row factory lets us access columns by name (dict-style) instead
    of by index, which makes the code more readable.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------------------------
# Schema initialization
# -------------------------------------------------------------------
def init_db() -> None:
    """
    Create database tables if they don't already exist.

    Called once at application startup. Uses IF NOT EXISTS so it's
    safe to call multiple times (idempotent).
    """
    conn = _connect()
    conn.executescript("""
        -- Documents table: one row per uploaded/processed file
        CREATE TABLE IF NOT EXISTS documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name       TEXT    NOT NULL,
            file_path       TEXT    NOT NULL,
            format          TEXT    NOT NULL,
            content_preview TEXT    DEFAULT '',
            full_text       TEXT    DEFAULT '',
            raw_llm_response TEXT   DEFAULT '',
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP
        );

        -- Extracted fields: one row per section found in a document
        -- Section, Sub-section, Title, Type, LMI ID, section_text (from XML parser or LLM)
        CREATE TABLE IF NOT EXISTS extracted_fields (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id     INTEGER NOT NULL,
            section         TEXT    DEFAULT '',
            sub_section     TEXT    DEFAULT '',
            title           TEXT    DEFAULT '',
            type            TEXT    DEFAULT '',
            lmi_id          TEXT    DEFAULT '',
            section_text    TEXT    DEFAULT '',
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id)
                REFERENCES documents(id) ON DELETE CASCADE
        );

        -- Plain-text chunks: one row per chunk of a document's full text
        -- Used by vector stores that need a text lookup by chunk ID
        CREATE TABLE IF NOT EXISTS document_chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text  TEXT    NOT NULL,
            FOREIGN KEY (document_id)
                REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_doc
            ON document_chunks(document_id);
    """)

    # Migration: add full_text column to existing databases that predate it
    existing_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(documents)").fetchall()
    }
    if "full_text" not in existing_cols:
        conn.execute(
            "ALTER TABLE documents ADD COLUMN full_text TEXT DEFAULT ''"
        )

    # Migration: add section_text to extracted_fields for XML parser output
    ef_cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(extracted_fields)").fetchall()
    }
    if "section_text" not in ef_cols:
        conn.execute(
            "ALTER TABLE extracted_fields ADD COLUMN section_text TEXT DEFAULT ''"
        )

    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Document operations
# -------------------------------------------------------------------
def insert_document(
    file_name: str,
    file_path: str,
    fmt: str,
    content_preview: str = "",
    full_text: str = "",
    raw_llm_response: str = "",
) -> int:
    """
    Insert a new document record and return its auto-generated ID.

    Args:
        file_name: Original filename (e.g. 'FS Doc 1.xml').
        file_path: Full path where the file is stored.
        fmt: File format identifier (xml, pdf, docx, rtf).
        content_preview: First 2000 chars of extracted text.
        full_text: Complete plain text of the document.
        raw_llm_response: Serialized LLM response for debugging.

    Returns:
        The integer ID of the newly inserted row.
    """
    conn = _connect()
    cursor = conn.execute(
        """INSERT INTO documents
           (file_name, file_path, format,
            content_preview, full_text, raw_llm_response)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            file_name,
            file_path,
            fmt,
            content_preview[:2000],
            full_text,
            raw_llm_response,
        ),
    )
    doc_id = cursor.lastrowid or 0
    conn.commit()
    conn.close()
    return doc_id


def get_document(doc_id: int) -> Optional[dict[str, Any]]:
    """Fetch a single document by ID. Returns None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_documents() -> list[dict[str, Any]]:
    """List all documents, most recently created first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM documents ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(doc_id: int) -> None:
    """
    Delete a document and all its associated data (fields, chunks).

    Explicitly deletes from all child tables since SQLite's ON DELETE
    CASCADE requires the foreign_keys pragma to be enabled.
    """
    conn = _connect()
    conn.execute(
        "DELETE FROM extracted_fields WHERE document_id = ?",
        (doc_id,),
    )
    conn.execute(
        "DELETE FROM document_chunks WHERE document_id = ?",
        (doc_id,),
    )
    conn.execute(
        "DELETE FROM documents WHERE id = ?",
        (doc_id,),
    )
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Extracted fields operations
# -------------------------------------------------------------------
def insert_extracted_field(
    document_id: int,
    section: str = "",
    sub_section: str = "",
    title: str = "",
    type_: str = "",
    lmi_id: str = "",
    section_text: str = "",
) -> int:
    """
    Insert one extracted field record for a document.

    Each record represents one row: section, sub_section, title, type,
    lmi_id, and optional section_text (body text from XML parser).

    Args:
        document_id: FK reference to the parent document.
        section: Main section heading.
        sub_section: Sub-section heading.
        title: Document-level title.
        type_: Document type.
        lmi_id: LexisNexis Metadata Identifier.
        section_text: Plain text content for this section (from XML parser).
    """
    conn = _connect()
    cursor = conn.execute(
        """INSERT INTO extracted_fields
           (document_id, section, sub_section,
            title, type, lmi_id, section_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (document_id, section, sub_section,
         title, type_, lmi_id, section_text or ""),
    )
    field_id = cursor.lastrowid or 0
    conn.commit()
    conn.close()
    return field_id


def get_extracted_fields(
    document_id: int,
) -> list[dict[str, Any]]:
    """
    Fetch all extracted field rows for a given document.

    Results are ordered by ID (insertion order) to preserve
    the original section ordering from the document.
    """
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM extracted_fields
           WHERE document_id = ?
           ORDER BY id""",
        (document_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------
# Chunk operations
# -------------------------------------------------------------------
def insert_chunks(document_id: int, chunks: list[str]) -> None:
    """
    Store all plain-text chunks for a document in one call.

    Chunks are inserted in order so their auto-generated IDs
    match the order used by the vector store for embedding lookup.

    Args:
        document_id: FK reference to the parent document.
        chunks: List of text chunks in document order.
    """
    if not chunks:
        return
    conn = _connect()
    conn.executemany(
        "INSERT INTO document_chunks (document_id, chunk_index, chunk_text) "
        "VALUES (?, ?, ?)",
        [(document_id, i, chunk) for i, chunk in enumerate(chunks)],
    )
    conn.commit()
    conn.close()


def get_chunks(document_id: int) -> list[dict[str, Any]]:
    """Return all chunks for a document, ordered by chunk_index."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index",
        (document_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_extracted_fields() -> list[dict[str, Any]]:
    """
    Fetch all extracted fields across all documents, joined
    with document metadata for display purposes.
    """
    conn = _connect()
    rows = conn.execute(
        """SELECT ef.*, d.file_name, d.format
           FROM extracted_fields ef
           JOIN documents d ON d.id = ef.document_id
           ORDER BY ef.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
