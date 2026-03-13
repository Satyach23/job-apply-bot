"""
FastAPI application — serves the web UI and handles document uploads.

Uses Jinja2 templates for HTML rendering with LexisNexis ACP branding.
All HTML lives in app/templates/ — no inline HTML in this module.

Routes:
  GET  /              — Home page with upload form
  POST /upload        — Handle file upload and run pipeline
  GET  /results/<id>  — Display extracted fields for a document
  GET  /documents     — List all processed documents
  POST /delete/<id>   — Delete a document and its results
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config import (
    APP_NAME,
    COMPANY_NAME,
    PROJECT_NAME,
    PROJECT_ROOT,
    DATA_DIR,
    STATIC_DIR,
    SUPPORTED_EXTENSIONS,
    TEMPLATES_DIR,
    UPLOADS_DIR,
    ensure_directories,
)
from app.storage import (
    delete_document,
    get_document,
    get_extracted_fields,
    init_db,
    list_documents,
)

# -------------------------------------------------------------------
# Application setup
# -------------------------------------------------------------------
app = FastAPI(
    title=f"{COMPANY_NAME} {PROJECT_NAME} - {APP_NAME}",
)

# Create required directories before any file I/O
ensure_directories()

# Initialize the SQLite database (creates tables if needed)
init_db()

# Mount the /static route to serve CSS, logo, and other assets
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)

# Configure Jinja2 template engine
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# -------------------------------------------------------------------
# Template context helper
# -------------------------------------------------------------------
def _ctx(request: Request, **kwargs) -> dict:
    """
    Build the standard template context dictionary.

    Every template receives: request, app_name, company_name,
    project_name, and supported_formats. Page-specific data
    is passed via **kwargs.
    """
    fmt_list = ", ".join(
        sorted(
            ext.upper().lstrip(".")
            for ext in SUPPORTED_EXTENSIONS
        )
    )
    return {
        "request": request,
        "app_name": APP_NAME,
        "company_name": COMPANY_NAME,
        "project_name": PROJECT_NAME,
        "supported_formats": fmt_list,
        **kwargs,
    }


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page: file upload form + recent documents list."""
    docs = list_documents()
    return templates.TemplateResponse(
        "home.html",
        _ctx(request, documents=docs),
    )


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Handle file upload: validate extension, save to disk,
    run the processing pipeline, then redirect to results.
    """
    # Validate file extension
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        docs = list_documents()
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return templates.TemplateResponse(
            "home.html",
            _ctx(
                request,
                documents=docs,
                error=(
                    f"Unsupported format: {suffix}. "
                    f"Supported: {supported}"
                ),
            ),
        )

    # Save uploaded file with UUID prefix to avoid collisions
    safe_name = Path(filename).name
    dest = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    content = await file.read()
    dest.write_bytes(content)

    # Run the full pipeline: parse -> LLM analyze -> store
    from app.agents.pipeline import run_pipeline

    try:
        result = run_pipeline(str(dest))
    except Exception as e:
        docs = list_documents()
        return templates.TemplateResponse(
            "home.html",
            _ctx(
                request,
                documents=docs,
                error=f"Processing error: {e}",
            ),
        )

    # Redirect to results page for the new document
    return RedirectResponse(
        url=f"/results/{result.id}",
        status_code=303,
    )


@app.post("/load_samples")
async def load_samples(request: Request):
    """
    Bulk-load all sample XML documents (BF, FS, DR, etc.) as separate documents.

    Looks for *.xml files under the project root and runs the pipeline
    on each one. Used to quickly populate the analyzer and chatbot with
    multiple documents instead of a single upload.
    """
    from app.agents.pipeline import run_pipeline

    # Avoid re-processing the same file paths
    existing = {d["file_path"] for d in list_documents()}

    fs_files = []
    bf_files = []
    dr_files = []

    # Scan project root and its parent for XML files (BF / FS / DR)
    seen_paths: set[str] = set()
    for root in (PROJECT_ROOT.parent, PROJECT_ROOT):
        for path in root.rglob("*.xml"):
            # Skip any XMLs inside the runtime data directory (uploads, DB artifacts)
            try:
                if DATA_DIR in path.parents:
                    continue
            except Exception:
                pass
            sp = str(path)
            if sp in seen_paths:
                continue
            seen_paths.add(sp)
            name = path.name.lower()
            if "fs doc" in name:
                fs_files.append(path)
            elif "bf doc" in name:
                bf_files.append(path)
            elif "dr doc" in name:
                dr_files.append(path)

    loaded = 0

    def load_group(paths, limit: int) -> int:
        count = 0
        for p in sorted(paths)[:limit]:
            if str(p) in existing:
                continue
            try:
                run_pipeline(str(p))
                count += 1
            except Exception:
                continue
        return count

    loaded += load_group(fs_files, 5)
    loaded += load_group(bf_files, 5)
    loaded += load_group(dr_files, 5)

    docs = list_documents()
    msg = "Loaded sample XML documents." if loaded else "No sample XML documents were loaded."
    return templates.TemplateResponse(
        "home.html",
        _ctx(
            request,
            documents=docs,
            success=msg,
        ),
    )


@app.get("/results/{doc_id}", response_class=HTMLResponse)
async def results(request: Request, doc_id: int):
    """Display extracted fields table for a specific document."""
    doc = get_document(doc_id)
    if not doc:
        return templates.TemplateResponse(
            "home.html",
            _ctx(
                request,
                documents=list_documents(),
                error="Document not found.",
            ),
        )

    fields = get_extracted_fields(doc_id)
    return templates.TemplateResponse(
        "results.html",
        _ctx(request, document=doc, fields=fields),
    )


@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    """List all processed documents."""
    docs = list_documents()
    return templates.TemplateResponse(
        "documents.html",
        _ctx(request, documents=docs),
    )


@app.post("/delete/{doc_id}")
async def delete_doc(doc_id: int):
    """Delete a document, its chunks, embeddings, and redirect to documents list."""
    from app.vector_store import get_vector_store
    get_vector_store().delete_document(doc_id)
    delete_document(doc_id)
    return RedirectResponse(
        url="/documents",
        status_code=303,
    )


@app.get("/ask", response_class=HTMLResponse)
async def ask_page(request: Request):
    """RAG question-answering page."""
    docs = list_documents()
    return templates.TemplateResponse(
        "ask.html",
        _ctx(request, documents=docs, active_page="ask"),
    )


@app.post("/ask", response_class=HTMLResponse)
async def ask_question(
    request: Request,
    question: str = Form(...),
    doc_id: Optional[int] = Form(None),
):
    """Process a question through the RAG agent and display the answer."""
    from app.agents.rag_agent import answer_question

    result = answer_question(question, doc_id if doc_id else None)
    docs = list_documents()
    return templates.TemplateResponse(
        "ask.html",
        _ctx(
            request,
            documents=docs,
            active_page="ask",
            question=question,
            answer=result["answer"],
            source_type=result["source_type"],
            sources=result["sources"],
            selected_doc_id=doc_id,
        ),
    )


# -------------------------------------------------------------------
# API for AI Chatbot panel (JSON)
# -------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    doc_id: Optional[int] = None


@app.get("/api/documents")
async def api_list_documents():
    """Return list of documents for chatbot doc filter (JSON)."""
    docs = list_documents()
    return [{"id": d["id"], "file_name": d["file_name"]} for d in docs]


@app.post("/api/ask")
async def api_ask(body: AskRequest):
    """RAG Q&A for chatbot panel; returns JSON."""
    from app.agents.rag_agent import answer_question
    result = answer_question(body.question, body.doc_id)
    return result
