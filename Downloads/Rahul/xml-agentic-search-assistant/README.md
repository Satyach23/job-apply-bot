# XML Agentic Search Assistant (Local Prototype)

Build and run the agent locally following **XML_Agentic_Search_Assistant_Approach (15)**.

## What this does

- **Input**: Case, legislation, or news (PDF, DOC/DOCX, or XML).
- **Planner Agent**: Identifies type (Case | Legislation | News) and routes to the right processor.
- **Format parsing**: PDF, DOC/DOCX, XML → normalized text/structure.
- **Type-specific pipeline**: Structure → index → match → suggest.
- **Editor UI**: View suggestions and confirm/reject (no auto-apply).
- **LLM Report**: Optional — LLM (Gemini or OpenAI) analyzes the document and produces a concise report. Requires API key: copy `.env.example` to `.env`, set `GOOGLE_API_KEY` or `OPENAI_API_KEY`, then upload; view in **Report** in the sidebar.

## Setup (local)

1. **Create and activate a virtual environment**

   ```bash
   cd xml-agentic-search-assistant
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   **Note:** If you see `ValueError: failed to parse CPython sys.version` when running pip, your venv was created with **Anaconda's Python**. Remove the venv and create it with a non-Anaconda interpreter (e.g. Homebrew):  
   `rm -rf .venv && /opt/homebrew/bin/python3 -m venv .venv && source .venv/bin/activate`

3. **Run the app**

   ```bash
   uvicorn app.main:app --reload
   ```

   Then open: **http://localhost:8000**

## End-to-end flow (from the document)

```
[Input: case / legislation / news (PDF, DOC, or XML)]
    ↓
[Planner Agent: identify type → Case | Legislation | News]
    ↓
[Type-specific agent: Case | Legislation | News Processing Agent]
    ↓
[Parse by format: PDF | DOC | XML]
    ↓
[Structure and index → Match → Suggest]
    ↓
[Structured suggestions for review]
    ↓
[Human editors confirm, reject, or modify]
```

## Project layout

```
xml-agentic-search-assistant/
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app + routes
│   ├── planner.py       # Planner Agent (classify type)
│   ├── parsers/         # PDF, DOCX, XML parsers
│   ├── agents/          # Case, Legislation, News processors
│   ├── storage.py       # SQLite store
│   └── templates/       # Editor UI (suggestions, confirm/reject)
├── data/                # Uploaded docs + DB (created at runtime)
└── samples/             # Sample case/legislation/news files (optional)
```

## Test cycle

1. Put sample PDF/DOC/XML files in `data/uploads/` (or use the upload API).
2. Submit an input via the UI: enter the **file path** (e.g. `./samples/case.pdf` or an absolute path) and click Submit.
3. Check **Suggestions** in the UI; confirm or reject each.
4. Inspect `data/acp.db` for metadata, index, and editor decisions.

No external APIs required for the core flow; everything runs on your machine.

## Storage and RAG

- **SQLite (regular)**: `documents`, `extracted_fields` (title, section, sub_section, section_text), `document_chunks` (plain text). DB file: `data/acp.db`.
- **Vector store** (embeddings): Set `VECTOR_BACKEND` in `.env`:
  - `sqlite` (default) — embeddings in SQLite `document_embeddings` table (same DB).
  - `chroma` — ChromaDB under `data/chroma`.
  - `faiss` — FAISS index under `data/faiss`.
- **Ask / RAG** (one agent talks to both stores by question type):
  - **Metadata questions** (titles, sections, types, LMI IDs) → SQLite only.
  - **Content questions** (what a section says, facts) → vector store only.
  - **Factual / law questions** (e.g. “What does the law say about X?”) → **both** SQLite and vector DB; context is combined for one factual answer.
- If no data is found from the chosen source(s), the tool returns **"No information found"**.

See **REQUIREMENTS.md** for a full requirements-to-files mapping.

## Steps implemented (from the document §7 Next Steps)

| Document section | Implementation |
|------------------|----------------|
| Define rules/heuristics for Planner Agent | `app/planner.py` – keyword heuristics for Case / Legislation / News |
| Implement format parsers (PDF, DOC, XML) | `app/parsers/` – `pdf_parser.py`, `docx_parser.py`, `xml_parser.py` |
| Type-specific processing agents + pipeline | `app/agents/pipeline.py` – structure → index → match → suggest |
| Minimal editor view for confirm/reject | `app/main.py` – `/suggestions` page with Confirm/Reject buttons |
| Run test cycles | Use home page to submit a file path; review suggestions and decisions in `data/agent.db` |
