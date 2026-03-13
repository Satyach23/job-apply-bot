# ACP Document Analyzer — Architecture

**Company:** LexisNexis
**Project:** ACP (Agentic Content Processing)
**Purpose:** Upload legal/regulatory documents (XML, PDF, DOCX, RTF), extract structured metadata fields using an AI-powered pipeline, and display results in a web UI.

---

## High-Level Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐     ┌────────────┐
│  Upload  │────>│  Parse File  │────>│  LLM Analyze │────>│  Store   │────>│  Display   │
│  (Web UI)│     │  (text out)  │     │  (Gemini AI) │     │ (SQLite) │     │  (Results) │
└──────────┘     └──────────────┘     └──────────────┘     └──────────┘     └────────────┘
```

1. **Upload** — User uploads a file via the web UI (FastAPI)
2. **Parse** — Format-specific parser extracts raw text from the file
3. **Analyze** — Google Gemini LLM extracts structured fields from the text
4. **Store** — Document record and extracted fields are saved to SQLite
5. **Display** — Results table is rendered in the browser

---

## Output Fields

Every document section produces a row with these five fields:

| Field        | Description                                           |
|-------------|-------------------------------------------------------|
| Section      | Main section heading the content belongs to           |
| Sub-section  | Sub-heading within the main section                   |
| Title        | Document-level title (same across all rows)           |
| Type         | Document type (Practice Note, Overview, etc.)         |
| LMI ID       | LexisNexis Metadata Identifier (EXPERT ID, CITEID)   |

---

## Key Design Decisions

1. **No regex, no hardcoded extraction** — All field identification is done by the Gemini LLM. The parsers only extract raw text; the LLM understands document structure and semantics.

2. **File-agnostic pipeline** — The same LLM prompt works for any document format. Adding a new format only requires a new parser; the analysis layer is unchanged.

3. **Registry pattern for parsers** — New formats are added by subclassing `BaseParser` and registering in `registry.py`. No if/else chains to modify.

4. **Jinja2 templates** — All HTML is in `app/templates/`, not inline in Python. Clean separation of logic and presentation.

5. **Single LLM client** — One module (`llm_client.py`) handles all Gemini API calls. DRY — no duplicate API configuration.

---

## Directory Structure

```
xml-agentic-search-assistant/
├── app/
│   ├── __init__.py              # Package marker
│   ├── config.py                # All settings, env vars, paths
│   ├── models.py                # Pydantic data models
│   ├── main.py                  # FastAPI app, routes, templates
│   ├── storage.py               # SQLite CRUD operations
│   │
│   ├── parsers/                 # Format-specific document parsers
│   │   ├── __init__.py          # Exports parse_document()
│   │   ├── base.py              # Abstract base class for parsers
│   │   ├── xml_parser.py        # XML/KnowHow parser
│   │   ├── pdf_parser.py        # PDF parser (pypdf)
│   │   ├── docx_parser.py       # Word document parser (python-docx)
│   │   ├── rtf_parser.py        # RTF parser (striprtf)
│   │   └── registry.py          # Parser registry + parse_document()
│   │
│   ├── agents/                  # LLM-powered analysis pipeline
│   │   ├── __init__.py          # Exports run_pipeline()
│   │   ├── llm_client.py        # Google Gemini API client
│   │   ├── analyzer.py          # Document field extraction agent
│   │   └── pipeline.py          # Orchestrates parse → analyze → store
│   │
│   └── templates/               # Jinja2 HTML templates
│       ├── base.html            # Base layout (sidebar, branding)
│       ├── home.html            # Upload page
│       ├── results.html         # Extraction results table
│       └── documents.html       # All documents list
│
├── static/
│   ├── style.css                # LexisNexis-branded stylesheet
│   └── logo.png                 # Company logo
│
├── data/
│   ├── uploads/                 # Uploaded files (auto-created)
│   └── acp.db                   # SQLite database (auto-created)
│
├── FS Doc *.xml                 # Sample test documents
├── .env                         # API key (not committed)
├── .env.example                 # Template for .env
├── requirements.txt             # Python dependencies
├── ARCHITECTURE.md              # This file
└── README.md                    # Quick-start instructions
```

---

## File Descriptions

### Core Application

| File | Purpose |
|------|---------|
| `app/config.py` | Single source of truth for all settings: paths, API keys, supported formats, LLM model config. Loads `.env` at import time. |
| `app/models.py` | Pydantic models: `ParsedDocument` (parser output), `ExtractedField` (one result row), `DocumentRecord` (full pipeline result). |
| `app/main.py` | FastAPI app with five routes. Uses Jinja2 templates. Handles upload, validation, pipeline execution, and result display. |
| `app/storage.py` | SQLite layer with two tables: `documents` and `extracted_fields`. All DB access is through this module. |

### Parsers

| File | Purpose |
|------|---------|
| `app/parsers/base.py` | Abstract `BaseParser` class. Defines the contract: `can_handle(path)` and `parse(path) -> ParsedDocument`. Helpers for building results/errors. |
| `app/parsers/xml_parser.py` | Walks XML element trees, strips namespaces, collects text with structural tag markers. Handles LexisNexis KnowHow namespace. |
| `app/parsers/pdf_parser.py` | Uses `pypdf` to extract text from all PDF pages. |
| `app/parsers/docx_parser.py` | Uses `python-docx` to extract paragraphs (with heading markers) and table rows. |
| `app/parsers/rtf_parser.py` | Uses `striprtf` to convert RTF control codes to plain text. |
| `app/parsers/registry.py` | Registry of parser instances. `parse_document()` auto-selects the right parser by file extension. |

### Agents

| File | Purpose |
|------|---------|
| `app/agents/llm_client.py` | Gemini API wrapper. `call_llm()` for text responses, `call_llm_json()` for JSON-parsed responses. Handles code-block stripping. |
| `app/agents/analyzer.py` | Core extraction logic. Sends document text + structured prompt to Gemini, parses JSON response into `ExtractedField` objects. |
| `app/agents/pipeline.py` | Orchestrator. Calls parser → analyzer → storage in sequence. Returns `DocumentRecord`. |

### Templates

| File | Purpose |
|------|---------|
| `base.html` | Shared layout: dark navy sidebar with LexisNexis branding, nav links, main content area. |
| `home.html` | Upload zone with drag-and-drop styling, recent documents list. |
| `results.html` | Document info header, stats cards, extracted fields table with CSV export. |
| `documents.html` | Grid of all processed documents with view/delete actions. |

---

## Adding a New Format

To add support for a new file format (e.g., `.csv`):

1. Create `app/parsers/csv_parser.py`
2. Subclass `BaseParser`, set `supported_extensions = [".csv"]`
3. Implement `parse()` to return a `ParsedDocument` with extracted text
4. Add `CSVParser()` to the `_PARSERS` list in `app/parsers/registry.py`
5. Add `".csv"` to `SUPPORTED_EXTENSIONS` in `app/config.py`

No changes needed in the analyzer, pipeline, storage, or UI — they are format-agnostic.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | FastAPI + Uvicorn |
| Templates | Jinja2 |
| LLM | Google Gemini (gemini-2.0-flash) |
| Database | SQLite3 |
| PDF Parsing | pypdf |
| DOCX Parsing | python-docx |
| RTF Parsing | striprtf |
| XML Parsing | xml.etree.ElementTree (stdlib) |
| Validation | Pydantic v2 |

---

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set up API key
cp .env.example .env
# Edit .env and add your Google Gemini API key

# Start the server
uvicorn app.main:app --reload --port 8000

# Open in browser
open http://localhost:8000
```
