# AI Chatbot — Architecture & Behaviour

**Company:** LexisNexis  
**Project:** ACP (Agentic Content Processing)  
**Purpose:** Provide an AI chatbot that answers questions about uploaded documents by routing to SQLite (metadata) and/or the vector store (content), and returning a single factual answer. The primary chatbot appears beside the Document Analyzer in the FastAPI UI, with an optional separate Streamlit chat UI.

---

## High-Level Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐
│  User Question  │────>│  Classify (LLM)   │────>│  metadata | content | both       │
│  (Chatbot UI)   │     │  One word only    │     └─────────────┬───────────────────┘
└─────────────────┘     └──────────────────┘                   │
                                                                 │
         ┌────────────────────────┬──────────────────────────────┼──────────────────────────────┐
         │                        │                              │                              │
         v                        v                              v                              v
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│  metadata       │     │  content        │     │  both                    │     │  (no results)           │
│  SQLite only    │     │  Vector store   │     │  SQLite + Vector store   │     │  → "No information       │
│  extracted_     │     │  semantic      │     │  combine context         │     │    found"                │
│  fields         │     │  search        │     │  one answer              │     └─────────────────────────┘
└────────┬────────┘     └────────┬────────┘     └─────────────┬───────────┘
         │                        │                            │
         └────────────────────────┴────────────────────────────┘
                                          │
                                          v
                                ┌──────────────────┐
                                │  Synthesise      │
                                │  Answer (LLM)    │
                                │  + source badge  │
                                └────────┬─────────┘
                                         │
                                         v
                                ┌──────────────────┐
                                │  Show in         │
                                │  Chatbot panel   │
                                └──────────────────┘
```

1. **User question** — Entered in the AI Chatbot panel (right side of the screen) or on the full “Ask Documents” page.
2. **Classify** — An LLM classifies the question into one of: **metadata**, **content**, or **both**.
3. **Retrieve** — Depending on the class:
   - **metadata** → query SQLite `extracted_fields` only.
   - **content** → embed the question and run semantic search on the vector store only.
   - **both** → run both; combine metadata rows and vector chunks into one context.
4. **No results** — If the chosen source(s) return nothing, the tool returns **"No information found"** (no LLM call).
5. **Synthesise** — Retrieved context is passed to the LLM with a fixed prompt to produce a short, factual answer.
6. **Show** — The answer is shown in the chatbot with an optional source badge (SQLite / Vector / Both).

---

## UI Layout: Analyzer + Chatbot

The FastAPI application uses a **two-column layout** on every page:

| Area | Location | Purpose |
|------|----------|---------|
| **Sidebar** | Left, fixed | Navigation: Upload & Analyze, Documents, Ask Documents. |
| **Analyzer content** | Centre (flex) | Page-specific: upload form, results table, document list, or full ask form. |
| **AI Chatbot panel** | Right, fixed width | Persistent chat: message history, document filter, question input, send. |

- The **Analyzer** (upload, results, documents) is unchanged and always on the **left** (main content).
- The **AI Chatbot** is always visible on the **right** on all pages (Home, Documents, Results, Ask Documents).
- On small screens (e.g. &lt; 768px), the chatbot moves **below** the analyzer content.

---

## Document Ingestion (Single and All XMLs)

The chatbot only answers from documents that have been processed by the **pipeline** (parse → analyze → store → embed). There are two ways to ingest documents:

| Ingestion path | How | What it does | When to use |
|----------------|-----|--------------|-------------|
| **Single upload** | Home page → **Upload & Analyze** card → upload `.xml/.pdf/.docx/.rtf` | Saves the file under `data/uploads/`, runs `run_pipeline()`, inserts into `documents`, `extracted_fields`, `document_chunks`, and the vector store. | When testing one document at a time. |
| **All sample XMLs** | Home page → **Load all sample XML documents** button | Calls `POST /load_samples`, which scans `PROJECT_ROOT` for `*.xml` (BF / FS / DR docs), runs `run_pipeline()` on each, and populates SQLite + vector store for **all** sample XMLs. | When you want the chatbot to talk about all built-in XML documents at once. |

Once documents are loaded, the chatbot’s **document filter** can be set to:

- **All documents** — search across all ingested documents.
- A specific document — restrict metadata search to that document (vector search remains global).

Paths involved:

| File | Role |
|------|------|
| `app/main.py` | `POST /upload` (single file) and `POST /load_samples` (bulk sample XML ingest). |
| `app/agents/pipeline.py` | `run_pipeline(file_path)` — parse → (XML structure or LLM extraction) → store → chunk → embed. |

---

## Question Routing (Classification)

The LLM returns exactly one word. Routing is then deterministic.

| Classification | Meaning | Data source(s) | When to use |
|----------------|---------|----------------|-------------|
| **metadata** | Question is about document structure, titles, section names, types, LMI IDs. | SQLite `extracted_fields` only. | “What is the document title?”, “List sections”, “What is the LMI ID?” |
| **content** | Question is about what the text says (facts, guidance, body content). | Vector store only (semantic search over chunk embeddings). | “What does section 3 say?”, “Explain Part 36 offers.” |
| **both** | Factual/legal answer where both structure and content help. | SQLite **and** vector store; context combined. | “What does the law say about Part 36?”, “What are the requirements for a valid offer?” |

- **metadata** → `search_metadata(question, doc_id)` → SQLite.
- **content** → `search_content(question)` → embed query, then vector store search.
- **both** → both of the above; results merged into one context string for the answer LLM.

---

## Data Sources

| Source | Backend | Table / store | Used for |
|--------|---------|----------------|----------|
| **SQLite (regular)** | Single SQLite DB (`data/acp.db`) | `documents`, `extracted_fields`, `document_chunks` | Document metadata, section/subsection/title/type/LMI ID, and (for SQLite vector backend) chunk text. |
| **Vector store** | Chosen by `VECTOR_BACKEND` in `.env` | See below | Semantic similarity search over document content. |

**Vector backend options:**

| `VECTOR_BACKEND` | Implementation | Storage location |
|------------------|----------------|------------------|
| `sqlite` (default) | `SQLiteVectorStore` | Table `document_embeddings` in same SQLite DB. |
| `chroma` | `ChromaVectorStore` | Directory `data/chroma`. |
| `faiss` | `FAISSVectorStore` | `data/faiss/index.faiss` + `metadata.json`. |

The chatbot does **not** care which vector backend is used; it always calls the same RAG API.

---

## API Endpoints (Chatbot)

The right-hand chatbot panel uses **JSON APIs** so it can update the conversation without a full page reload.

| Method | Path | Purpose | Request | Response |
|--------|------|---------|---------|----------|
| **GET** | `/api/documents` | List documents for the “filter by document” dropdown. | None | `[{ "id": 1, "file_name": "Doc.xml" }, ...]` |
| **POST** | `/api/ask` | Run RAG: classify → retrieve → synthesise. | `{ "question": "...", "doc_id": null \| number }` | `{ "answer": "...", "source_type": "metadata" \| "content" \| "both" \| "none", "sources": ["..."] }` |

- **doc_id** optional. If set, metadata search is restricted to that document; vector search is still global (all indexed chunks).
- **source_type** is used in the UI to show a small badge (e.g. SQLite / Vector / Both).

---

## Prompts (Where They Live)

| Prompt | File | Role |
|--------|------|------|
| **Classification** | `app/agents/rag_agent.py` — `_CLASSIFY_PROMPT` | Asks the LLM to return exactly one word: **metadata**, **content**, or **both**. |
| **Answer synthesis** | `app/agents/rag_agent.py` — `_ANSWER_PROMPT` | “Use the retrieved context to answer; if not enough information, say ‘No information found’.” |
| **Extraction** (when no XML structure) | `app/agents/analyzer.py` — `EXTRACTION_PROMPT` | Used by the **pipeline** to extract section/title/type/LMI ID from raw text; not used by the chatbot directly. |

The chatbot flow uses only the **classification** and **answer** prompts in `rag_agent.py`.

---

## “No Information Found” Tool

| Requirement | Implementation |
|-------------|----------------|
| When to trigger | When **metadata** search returns no rows and/or **content** search returns no chunks (depending on question type). |
| Function | `app/agents/tools.py` — `no_info_found()` returns the string `"No information found"`. |
| Usage | `app/agents/rag_agent.py` — if, after retrieval, `context_parts` is empty, the handler returns `{ "answer": no_info_found(), "source_type": "none", "sources": [] }` and **does not** call the answer LLM. |
| User sees | The chatbot displays “No information found” in the message thread. |

---

## File Descriptions (Chatbot & RAG)

### 1. Backend (RAG, pipeline, storage, parsers)

#### `app/config.py`

- Defines paths:
  - `PROJECT_ROOT`, `DATA_DIR`, `UPLOADS_DIR`, `STATIC_DIR`, `TEMPLATES_DIR`.
- Loads environment variables from `.env`:
  - `AI_GATEWAY_ENDPOINT`, `AI_GATEWAY_TENANT_KEY`, `GOOGLE_API_KEY`.
- Application metadata:
  - `APP_NAME`, `COMPANY_NAME`, `PROJECT_NAME`.
- **Supported formats:** `SUPPORTED_EXTENSIONS = {".xml"}` (XML-only).
- LLM and DB settings:
  - `LLM_MODEL`, `LLM_MAX_CHARS`, `DB_PATH`.
- Vector backend selector:
  - `VECTOR_BACKEND` (`"sqlite"`, `"chroma"`, or `"faiss"`).
- `ensure_directories()` creates `data/`, `uploads/`, `static/` if missing.

#### `app/models.py`

- `ParsedDocument`:
  - Fields: `file_path`, `file_name`, `format`, `text`, `metadata`, `error`.
  - Output of parsers (including XML parser) before LLM analysis.
- `ExtractedField`:
  - Fields: `section`, `sub_section`, `title`, `type`, `lmi_id`, `section_text`.
  - Represents one row in `extracted_fields`.
- `DocumentRecord`:
  - Fields: `id`, `file_name`, `file_path`, `format`, `content_preview`, `extracted_fields`, `raw_llm_response`, `created_at`.
  - Returned by `run_pipeline()` and used in templates.

#### `app/parsers/base.py`

- Abstract `BaseParser` class:
  - `supported_extensions: list[str]`.
  - `can_handle(file_path)` — checks extension.
  - `parse(file_path)` — implemented by subclasses.
  - Helpers:
    - `_build_result(...)` → `ParsedDocument` on success.
    - `_build_error(...)` → `ParsedDocument` with `error` set.

#### `app/parsers/xml_parser.py`

- Responsible for **XML parsing only**.
- Main responsibilities:
  - Read XML file from disk.
  - Parse with `xml.etree.ElementTree`.
  - Extract:
    - Document title (e.g. `document-title`, `title` tags).
    - Sections and subsections from elements like `section`, `secmain`, `heading`, `para`.
    - `section_text` (body text for each section).
  - Build:
    - `metadata["structured_sections"]` — list of dicts:
      - `{"title", "section", "sub_section", "section_text"}`.
    - `metadata["document_title"]` — top-level title.
    - `text` — full plain text of the XML (for chunking/embedding).

#### `app/parsers/registry.py` and `app/parsers/__init__.py`

- XML-only registry:
  - `_PARSERS = [XMLParser()]`.
  - `parse_document(file_path)`:
    - Validates the file exists.
    - Checks extension is in `SUPPORTED_EXTENSIONS`.
    - Finds `XMLParser` and calls `parse()`.
- `__init__.py` re-exports:
  - `parse_document`, `list_supported_formats`.

#### `app/storage.py`

- Manages **SQLite** (`data/acp.db`) schema and CRUD.
- Tables:
  - `documents`:
    - Columns: `id`, `file_name`, `file_path`, `format`, `content_preview`, `full_text`, `raw_llm_response`, `created_at`.
  - `extracted_fields`:
    - Columns: `id`, `document_id`, `section`, `sub_section`, `title`, `type`, `lmi_id`, `section_text`, `created_at`.
  - `document_chunks`:
    - Columns: `id`, `document_id`, `chunk_index`, `chunk_text`.
- Key functions:
  - `init_db()` — creates tables and adds missing columns (migrations).
  - `insert_document(...)` → returns new `document_id`.
  - `get_document(doc_id)` and `list_documents()`.
  - `insert_extracted_field(...)` and `get_extracted_fields(doc_id)`.
  - `insert_chunks(document_id, chunks)` and `get_chunks(document_id)`.
  - `get_all_extracted_fields()` — join of `extracted_fields` + `documents` (for metadata search).
  - `delete_document(doc_id)` — deletes from all related tables.

#### `app/chunker.py`

- `chunk_document(text, chunk_size=400, overlap=1)`:
  - Splits text into paragraphs (`\n\n`).
  - Builds chunks up to `chunk_size` characters.
  - Carries over last `overlap` paragraphs between chunks for context.
  - Returns list of `chunk_text` strings.

#### `app/embedder.py`

- Uses `sentence-transformers` (`all-MiniLM-L6-v2`) to create embeddings.
- Functions:
  - `_get_model()` — lazy-loads the model.
  - `embed(texts: list[str])` — returns list of 384-dim normalized vectors.
  - `embed_one(text: str)` — convenience wrapper for a single string.
  - `cosine_similarity(a, b)` — dot product of normalized vectors.

#### `app/vector_store/base.py` and `app/vector_store/__init__.py`

- `BaseVectorStore` interface:
  - `add_chunks(doc_id, chunks, embeddings)`.
  - `search(query_embedding, top_k)`.
  - `delete_document(doc_id)`.
- `get_vector_store()`:
  - Reads `VECTOR_BACKEND` from config.
  - Returns singleton instance of:
    - `SQLiteVectorStore` (default),
    - or `ChromaVectorStore`,
    - or `FAISSVectorStore`.

#### `app/vector_store/sqlite_store.py`

- Uses same SQLite DB (`acp.db`) for embeddings.
- Table: `document_embeddings`:
  - `id`, `chunk_id`, `document_id`, `embedding` (JSON string).
- `init()` creates table and index.
- `add_chunks(doc_id, chunks, embeddings)`:
  - Looks up `document_chunks` IDs for that `doc_id`.
  - Inserts one embedding row per chunk.
- `search(query_embedding, top_k)`:
  - Loads all embeddings for all chunks.
  - Computes dot product with query vector.
  - Returns top-k results as:
    - `{"chunk_text", "doc_id", "score"}`.
- `delete_document(doc_id)`:
  - Deletes all `document_embeddings` rows for that `doc_id`.

#### `app/vector_store/chroma_store.py` and `app/vector_store/faiss_store.py`

- `ChromaVectorStore`:
  - Uses persistent ChromaDB at `data/chroma`.
  - Stores documents + embeddings + `doc_id` metadata.
  - `search()` returns chunks and scores (1 - distance).
- `FAISSVectorStore`:
  - Uses FAISS `IndexFlatIP` at `data/faiss/index.faiss` + `metadata.json`.
  - Maintains list of `{chunk_text, doc_id}` in memory.
  - Rebuilds index on delete (acceptable for small/mid-sized sets).

#### `app/agents/llm_client.py`

- Single place for talking to LLMs.
- Reads from config:
  - `AI_GATEWAY_ENDPOINT`, `AI_GATEWAY_TENANT_KEY`, `GOOGLE_API_KEY`, `LLM_MODEL`.
- Creates:
  - An OpenAI-compatible client to the AI Gateway (when endpoint + key present).
  - A direct Gemini client as fallback (when `GOOGLE_API_KEY` present).
- Exposed functions:
  - `call_llm(prompt: str)` — returns plain text.
  - `call_llm_json(prompt: str)` — expects JSON response and parses it safely.

#### `app/agents/analyzer.py`

- LLM-based **metadata extractor** when XML does not provide `structured_sections`.
- Uses `call_llm_json()` with `EXTRACTION_PROMPT` to fill:
  - `section`, `sub_section`, `title`, `type`, `lmi_id`.
- Returns list of `ExtractedField` models.

#### `app/agents/pipeline.py`

- Orchestrates **entire document processing**:
  1. `parse_document(file_path)` → `ParsedDocument`.
  2. If `parsed.metadata["structured_sections"]` exists (XML case):
     - Builds `ExtractedField` list directly from XML parser output
       (`title`, `section`, `sub_section`, `section_text`).
  3. Else:
     - Calls `analyze_document(parsed)` (LLM extraction).
  4. Inserts a row in `documents` via `storage.insert_document(...)`.
  5. Inserts each `ExtractedField` into `extracted_fields`.
  6. Chunks `full_text` with `chunk_document(...)`.
  7. Embeds chunks with `embed(...)`, calls `get_vector_store().add_chunks(...)`.
  8. Returns a `DocumentRecord` with `id`, `file_name`, `format`, `extracted_fields`, etc.

#### `app/agents/tools.py`

- `search_metadata(query, doc_id=None)`:
  - Gets fields from `storage.get_extracted_fields(doc_id)` or `get_all_extracted_fields()`.
  - Joins `section`, `sub_section`, `title`, `type`, `lmi_id`, `file_name`, `section_text` into a single lowercase string.
  - Returns rows where `query` is a substring (up to 20 results).
- `search_content(query, top_k=5)`:
  - Calls `embed_one(query)`.
  - Uses `get_vector_store().search(...)`.
- `no_info_found()`:
  - Returns `"No information found"`.

#### `app/agents/rag_agent.py`

- Main RAG agent function: `answer_question(question, doc_id=None)`.
- Steps:
  1. Classify question type:
     - Uses `_CLASSIFY_PROMPT` and `call_llm(...)` to get `metadata` / `content` / `both`.
  2. Retrieve context:
     - If `metadata` or `both`:
       - Calls `search_metadata(question, doc_id)`.
       - Builds context lines like:
         - `Section: ... | Sub-section: ... | Title: ... | Type: ... | LMI ID: ... | File: ...`
         - Optionally appends `section_text` preview.
     - If `content` or `both`:
       - Calls `search_content(question, top_k=5)`.
       - Adds a divider and chunk texts.
  3. If **no context**:
     - Returns `{"answer": "No information found", "source_type": "none", "sources": []}`.
  4. Else:
     - Calls `call_llm(_ANSWER_PROMPT.format(context=..., question=...))`.
     - Sets `source_type`:
       - `"metadata"`, `"content"`, or `"both"` depending on which paths had results.
     - Returns the answer and a few source strings for display.

#### `app/main.py`

- FastAPI application entry point:
  - Configures app, mounts `/static`, sets up Jinja2 templates, initializes DB.
- Routes:
  - `GET /`:
    - Renders `home.html` with recent documents.
  - `POST /upload`:
    - Receives a single XML file.
    - Validates extension (`.xml` only).
    - Saves to `data/uploads`.
    - Calls `run_pipeline(...)`.
    - Redirects to `/results/{id}`.
  - `POST /load_samples`:
    - Scans `PROJECT_ROOT.parent` and `PROJECT_ROOT` for original BF / FS / DR XMLs (excluding `data/`).
    - Groups by file name (`"fs doc"`, `"bf doc"`, `"dr doc"`).
    - Loads at most **5** from each group using `run_pipeline(...)`, skipping already-loaded `file_path`s.
    - Renders `home.html` with a success message.
  - `GET /results/{doc_id}`:
    - Shows extraction results in `results.html`.
  - `GET /documents`:
    - Shows all processed documents in `documents.html`.
  - `POST /delete/{doc_id}`:
    - Deletes from vector store + SQLite and redirects to `/documents`.
  - `GET /api/documents`:
    - Returns `[{id, file_name}, ...]` for chatbot document filter.
  - `POST /api/ask`:
    - Receives JSON `{question, doc_id}`.
    - Calls `answer_question(...)` and returns its dict as JSON.

### 2. Frontend (Chatbot UI + Analyzer UI)

#### `app/templates/base.html`

- Base HTML layout used by all pages:
  - Fixed **sidebar** with:
    - Brand logo and project badge.
    - Links to `/` (Upload & Analyze) and `/documents`.
  - Main content:
    - `.content-with-chat` wrapper:
      - Left: `.analyzer-content` — page-specific content (`home.html`, `results.html`, `documents.html`).
      - Right: `.chatbot-panel` — AI Chatbot UI.
- Chatbot markup:
  - `.chatbot-header` — icon + “AI Chatbot”.
  - `.chatbot-messages` — container for chat bubbles.
  - Initial bot message:
    - “Ask a question about documents.”
  - `.chatbot-doc-filter` — `<select>` for “All documents” or a specific document.
  - `.chatbot-input` — text input.
  - `.chatbot-send` — send button with paper-plane icon.
- Inline script:
  - `loadDocuments()`:
    - Fetches `/api/documents` and fills the dropdown with `(id, file_name)`.
  - `sendQuestion()`:
    - Reads text from input and selected `doc_id`.
    - Appends a user message bubble.
    - Calls `/api/ask` via `fetch` and appends a bot message bubble.
    - Adds a small source badge based on `source_type` (`SQLite`, `Vector`, or `Both`).
  - Binds:
    - Click on Send.
    - Enter key in the input.
    - Auto-load documents on page load.

#### `app/templates/home.html`

- Extends `base.html`, sets `active_page = "home"`.
- Content:
  - “Document Analyzer” header and description.
  - **Upload card**:
    - Form to `POST /upload` with file input (XML only).
  - **Load samples card**:
    - Button to `POST /load_samples` to ingest BF / FS / DR XMLs.
  - **Recent documents** card:
    - Lists up to 5 most recent documents with “View Results” links.

#### `app/templates/results.html`

- Shows extraction results for a specific document:
  - Header “Extraction Results”.
  - Document info:
    - Format (XML), file name, processed timestamp.
  - Stats:
    - Number of sections found.
    - Format.
  - Table “Extracted Fields”:
    - Columns: `#`, `Section`, `Sub-section`, `Title`, `Type`, `LMI ID`.
  - “Export CSV” button:
    - JavaScript function converts table to CSV and downloads it.

#### `app/templates/documents.html`

- Lists **all documents** processed by the system:
  - For each:
    - Format badge (XML), file name, processed timestamp.
    - “View Results” (link to `/results/{id}`).
    - “Delete” button (form to `POST /delete/{id}`).

#### `static/style.css`

- All styling for:
  - Layout:
    - `.app-layout`, `.sidebar`, `.main-content`, `.content-with-chat`.
  - Sidebar:
    - Brand header, nav links, active state, footer.
  - Cards and upload zone:
    - `card`, `upload-zone`, buttons, badges.
  - Results tables and document list.
  - **Chatbot**:
    - `.chatbot-panel` width and layout.
    - `.chatbot-messages` scrollable region.
    - `.chat-message-user` vs `.chat-message-bot` alignment.
    - `.chat-bubble` styles and source badges.
    - Document filter select, input field, and send button.
  - Responsive behaviour:
    - On small screens, sidebar hides; chatbot stacks under analyzer content.

---

## Directory Structure (Relevant to Chatbot)

```
xml-agentic-search-assistant/
├── app/
│   ├── main.py                  # GET/POST /ask, GET /api/documents, POST /api/ask
│   ├── agents/
│   │   ├── rag_agent.py         # answer_question(), classify + retrieve + synthesise
│   │   ├── tools.py             # search_metadata, search_content, no_info_found
│   │   └── llm_client.py        # call_llm() for classification and answer
│   └── templates/
│       ├── base.html            # Layout + analyzer column + chatbot panel + chat JS
│       └── ask.html             # Full Ask Documents page
├── static/
│   └── style.css                # Chatbot panel and two-column layout
├── streamlit_app.py             # Optional Streamlit chat UI (standalone chatbot)
├── AI_CHATBOT.md                # This file
├── ARCHITECTURE.md              # Document Analyzer architecture
└── REQUIREMENTS.md              # Requirements-to-implementation mapping
```

---

## Alternative UI: Streamlit Chatbot

In addition to the FastAPI side-panel chatbot, there is a **standalone Streamlit chatbot** that talks to the same RAG agent and SQLite/vector backends.

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Streamlit app that imports `answer_question` and `list_documents`, uses `st.chat_message` + `st.chat_input` to render a chat UI, and lets you filter by document in the sidebar. |

How it works:

1. Uses `list_documents()` to populate a **sidebar dropdown** (`All documents` or a specific one).
2. Displays chat history from `st.session_state.messages` with:
   - `role="user"` for user messages,
   - `role="assistant"` for bot messages.
3. On each new message:
   - Calls `answer_question(prompt, doc_id)` from `app.agents.rag_agent`.
   - Appends the answer plus a small source note (SQLite / Vector / Both) based on `source_type`.

To run the Streamlit chatbot:

```bash
cd xml-agentic-search-assistant
source .venv/bin/activate           # or .venv\Scripts\activate on Windows
pip install -r requirements.txt     # once
streamlit run streamlit_app.py
```

Use the FastAPI UI (`/upload` and **Load all sample XML documents**) to ingest documents first so the Streamlit chatbot has content to answer from.

---

## Tech Stack (Chatbot & RAG)

| Layer | Technology |
|-------|------------|
| Web | FastAPI; JSON APIs for chatbot, HTML for full Ask page |
| RAG logic | Python in `app/agents/rag_agent.py` and `app/agents/tools.py` |
| Classification & answer | LLM via `app/agents/llm_client.py` (Gemini or AI Gateway) |
| Metadata store | SQLite (`extracted_fields`, etc.) |
| Vector store | SQLite table **or** ChromaDB **or** FAISS (see `app/vector_store/`) |
| Embeddings | `app/embedder.py` (e.g. sentence-transformers); used by `search_content` |
| Frontend | Vanilla JS in `base.html` (fetch, DOM updates); no separate SPA framework |

---

## Summary

- The **AI Chatbot** is a **RAG agent** that classifies the user question, then queries **SQLite** (metadata) and/or the **vector store** (content), and returns **one answer**.
- It is shown in a **fixed panel beside the Document Analyzer** on every page and uses **`/api/documents`** and **`/api/ask`** for its behaviour.
- When no data is found from the chosen source(s), it returns **“No information found”** without calling the answer LLM.
- Routing (metadata / content / both), data sources (SQLite vs vector), and prompts are documented above and implemented as in **ARCHITECTURE.md** and **REQUIREMENTS.md**.
