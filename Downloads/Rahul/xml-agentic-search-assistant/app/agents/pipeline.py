"""
Main processing pipeline — orchestrates the full document analysis.

This is the single entry point called when a user uploads a document.
It coordinates three layers:
  1. PARSE   — extract raw text from the file (XML, PDF, DOCX, RTF)
  2. ANALYZE — send text to Gemini LLM for field extraction
  3. STORE   — persist the document and extracted fields in SQLite

No business logic lives here — this module only orchestrates the
flow between the parser layer, the LLM agent layer, and storage.
"""

from app.agents.analyzer import analyze_document
from app.chunker import chunk_document
from app.embedder import embed
from app.models import DocumentRecord, ExtractedField, ParsedDocument
from app.parsers import parse_document
from app.vector_store import get_vector_store
from app import storage


def run_pipeline(file_path: str) -> DocumentRecord:
    """
    Execute the full document processing pipeline.

    Flow:
      1. Parse the file to extract raw text content
      2. Send the text to the LLM analyzer for field extraction
      3. Store the document record and extracted fields in the DB
      4. Return a DocumentRecord with all results

    Args:
        file_path: Absolute path to the uploaded document file.

    Returns:
        A DocumentRecord containing document metadata and all
        extracted fields. The record's id field is set to the
        database row ID for use in URL routing.
    """
    parsed: ParsedDocument = parse_document(file_path)
    if parsed.error:
        raise ValueError(parsed.error)

    # Structured fields: from XML parser (title, section, sub_section, section_text) or from LLM
    structured = parsed.metadata.get("structured_sections") or []
    if structured:
        doc_title = parsed.metadata.get("document_title") or ""
        extracted_fields = [
            ExtractedField(
                title=doc_title or (s.get("title") or ""),
                section=s.get("section") or "",
                sub_section=s.get("sub_section") or "",
                section_text=s.get("section_text") or "",
                type="",
                lmi_id="",
            )
            for s in structured
        ]
    else:
        extracted_fields = analyze_document(parsed)

    raw_response = str([f.model_dump() for f in extracted_fields])
    full_text = parsed.text or ""

    doc_id = storage.insert_document(
        file_name=parsed.file_name,
        file_path=parsed.file_path,
        fmt=parsed.format,
        content_preview=full_text[:2000],
        full_text=full_text,
        raw_llm_response=raw_response,
    )

    for field in extracted_fields:
        storage.insert_extracted_field(
            document_id=doc_id,
            section=field.section,
            sub_section=field.sub_section,
            title=field.title,
            type_=field.type,
            lmi_id=field.lmi_id,
            section_text=getattr(field, "section_text", "") or "",
        )

    # Chunks + embeddings: plain text in document_chunks (SQLite), vectors in vector store
    chunks = chunk_document(full_text)
    if chunks:
        storage.insert_chunks(doc_id, chunks)
        embeddings = embed(chunks)
        get_vector_store().add_chunks(doc_id, chunks, embeddings)

    # Step 6: Build and return the complete result
    return DocumentRecord(
        id=doc_id,
        file_name=parsed.file_name,
        file_path=parsed.file_path,
        format=parsed.format,
        content_preview=(parsed.text or "")[:500],
        extracted_fields=extracted_fields,
        raw_llm_response=raw_response,
    )
