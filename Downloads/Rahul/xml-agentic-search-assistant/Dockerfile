# ===========================================================
# ACP Document Analyzer — Production Docker Image
# ===========================================================
# Multi-stage build: slim Python image with only runtime deps.
# Serves both the FastAPI backend and Jinja2 frontend on :8000.
# ===========================================================

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Install OS-level dependencies needed by lxml / pypdf ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

# --- Install Python dependencies first (cached layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy application source + environment config ---
COPY app/  app/
COPY static/ static/
COPY .env .env

# --- Create runtime directories ---
RUN mkdir -p data/uploads

# --- Expose the default port ---
EXPOSE 8000

# --- Health-check: hit the home page every 30s ---
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# --- Start uvicorn ---
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
