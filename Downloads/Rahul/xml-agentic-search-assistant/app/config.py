"""
Configuration module for the ACP Document Analyzer.

Centralizes all application settings, environment variable loading,
and path configuration. Every other module imports from here instead
of reading os.environ directly — single source of truth.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
# Root directory of the project (parent of the 'app' package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directory for runtime data (SQLite DB, uploaded files)
DATA_DIR = PROJECT_ROOT / "data"

# Directory where uploaded files are saved before processing
UPLOADS_DIR = DATA_DIR / "uploads"

# Directory for static web assets (logo, CSS)
STATIC_DIR = PROJECT_ROOT / "static"

# Directory for Jinja2 HTML templates
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------
# Load .env file from project root if it exists
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# AI Gateway Configuration (LiteLLM proxy, OpenAI-compatible)
# ---------------------------------------------------------------------------
# LexisNexis AI Gateway endpoint (LiteLLM-based proxy).
# Exposes an OpenAI-compatible /chat/completions endpoint that
# routes to Gemini or other LLM providers behind the scenes.
AI_GATEWAY_ENDPOINT = os.environ.get(
    "AI_GATEWAY_ENDPOINT", ""
)
AI_GATEWAY_TENANT_KEY = os.environ.get(
    "AI_GATEWAY_TENANT_KEY", ""
)

# Fallback: direct Google Gemini API key (for local dev without VPN)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# ---------------------------------------------------------------------------
# Application Metadata
# ---------------------------------------------------------------------------
APP_NAME = "ACP Document Analyzer"
COMPANY_NAME = "LexisNexis"
PROJECT_NAME = "ACP"

# ---------------------------------------------------------------------------
# Supported File Formats
# ---------------------------------------------------------------------------
# Minimal configuration: this prototype only supports XML documents.
SUPPORTED_EXTENSIONS = {".xml"}

# ---------------------------------------------------------------------------
# LLM Settings
# ---------------------------------------------------------------------------
# Model name sent to the AI Gateway or Gemini API
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.0-flash")

# Maximum characters of document text to send to the LLM
LLM_MAX_CHARS = 80000

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite database file path
DB_PATH = DATA_DIR / "acp.db"

# ---------------------------------------------------------------------------
# Vector Store Backend
# ---------------------------------------------------------------------------
# Which vector store backend to use for semantic search.
# Options: "sqlite" (default, no extra deps), "chroma", "faiss"
VECTOR_BACKEND = os.environ.get("VECTOR_BACKEND", "sqlite")


# ---------------------------------------------------------------------------
# Directory Initialization
# ---------------------------------------------------------------------------
def ensure_directories() -> None:
    """
    Create all required directories if they don't exist.
    Called once at application startup before any file I/O.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
