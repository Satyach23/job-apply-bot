# Requirements Mapping

This document maps the project requirements to the implementation (files and behavior).

---

## 1. XML document → store as title, section, subsections (XML parser) → SQLite

| Requirement | Implementation |
|-------------|----------------|
| Get XML document | Upload via UI or API; file path to parser. |
| Store **not** direct (structured) | XML is parsed into **title**, **section**, **sub_section**, **section_text** (not raw dump). |
| Use XML parser | `app/parsers/xml_parser.py` — extracts `document-title`/`title`, `section`/`secmain`, `heading`, `para` (supports simple XML and LexisNexis KnowHow). |
| Save to SQLite | `app/storage.py` — tables `documents`, `extracted_fields` (columns: title, section, sub_section, section_text, type, lmi_id). |
| Pipeline | `app/agents/pipeline.py` — when parser returns `metadata["structured_sections"]`, those are written to SQLite; otherwise LLM extraction is used. |

---

## 2. Plain text and embeddings in different tables

| Requirement | Implementation |
|-------------|----------------|
| Plain text storage | **SQLite**: `documents.full_text`, `document_chunks` (one row per chunk). `app/storage.py`. |
| Embedding storage | **Separate**: SQLite table `document_embeddings` **or** ChromaDB **or** FAISS (see below). |

---

## 3. SQLite for regular storage; SQLite-vector / Chroma / FAISS for vector storage

| Storage type | Implementation |
|--------------|-----------------|
| **Regular (SQLite)** | Single SQLite DB: `documents`, `extracted_fields`, `document_chunks`. `app/storage.py`, `app/config.py` (DB_PATH). |
| **Vector (choose one)** | Set `VECTOR_BACKEND` in `.env`: |
| | • **sqlite** (default) — `app/vector_store/sqlite_store.py` — table `document_embeddings`, cosine similarity in Python. |
| | • **chroma** — `app/vector_store/chroma_store.py` — ChromaDB under `data/chroma`. |
| | • **faiss** — `app/vector_store/faiss_store.py` — FAISS index under `data/faiss`. |
| Factory | `app/vector_store/__init__.py` — `get_vector_store()` returns the configured backend. |

---

## 4. Simple RAG agent: talk to both stores based on question

| Requirement | Implementation |
|-------------|----------------|
| Agent talks to tables by question type | `app/agents/rag_agent.py` — classifies question, then queries SQLite and/or vector store. |
| **Metadata questions** (structure, titles, sections, types, LMI IDs) | → **SQLite only**: `app/agents/tools.py` → `search_metadata()` → `extracted_fields`. |
| **Content questions** (what a section says, facts, legal guidance) | → **Vector store**: `search_content()` → embed query → vector store search. |
| **Factual / law questions** (e.g. “What does the law say about X?”) | → **Both**: RAG classifies as `"both"`, calls `search_metadata()` and `search_content()`, combines context, returns **one factual answer** using both SQLite and vector DB. |

---

## 5. Simple tool: if no data found → “No information found”

| Requirement | Implementation |
|-------------|----------------|
| Tool when no data | `app/agents/tools.py` — `no_info_found()` returns `"No information found"`. |
| When it runs | `app/agents/rag_agent.py` — if neither metadata nor content search returns results, response is `no_info_found()`. |
| Prompt | `_ANSWER_PROMPT` in `rag_agent.py` tells the LLM to say “No information found” when context is insufficient. |

---

## 6. Simple directory workflow, prompts where needed

| Requirement | Implementation |
|-------------|----------------|
| Simple workflow | `app/agents/pipeline.py`: Parse → (XML structure or LLM extraction) → Store in SQLite → Chunk → Embed → Store in vector backend. |
| Prompts | • Routing: `_CLASSIFY_PROMPT` in `rag_agent.py` (metadata / content / both). |
| | • Answer: `_ANSWER_PROMPT` in `rag_agent.py` (factual answer from context). |
| | • Extraction (when no XML structure): `app/agents/analyzer.py` — EXTRACTION_PROMPT. |

---

## Summary: where both SQLite and vector DB are used together

- **Factual / law questions** are the case where **both** SQLite and the vector DB are used:
  - **SQLite** supplies document metadata and section/subsection text (from `extracted_fields`).
  - **Vector DB** supplies semantically similar chunks (from `document_chunks` via embeddings).
- Combined context is passed to the LLM in a single prompt so you get **one factual answer** that can use both structure and content.

File that wires this: **`app/agents/rag_agent.py`** (question type `"both"`).
