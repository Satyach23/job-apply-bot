# ACE POC — Analytical Content Engine

A **proof-of-concept** implementation of the ACE / L+CP Analytical Platform core flow:

```
Ingest (case/law) → P0 Filter → RAG Retrieval → Impact Reasoning → Task Creation
```

## Quick Start

### 1. Create virtual environment and install

```bash
cd ace-poc
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Seed the database and RAG index

```bash
python scripts/seed_db.py
```

This creates:
- 1 publication (Federal Employment Law Treatise)
- 5 analytical sections (Ch.5, Ch.7)
- RAG vector index (ChromaDB + sentence-transformers)

> First run downloads the embedding model (~90MB); may take 1–2 minutes.

### 3. Start the API

```bash
uvicorn main:app --reload --port 8000
```

### 4. Walk through the flow

**Step 1: Ingest a case**

```bash
curl -X POST http://localhost:8000/api/v1/case_bundle/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "case_name": "Smith v. Acme Corp",
    "court": "US Court of Appeals",
    "decision_date": "2025-01-15",
    "headnotes": "Wrongful termination, public policy exception, retaliation",
    "faceted_summary": "Court expanded protections for whistleblowers.",
    "shepard_letters": "O"
  }'
```

Response includes `id` and `passed_p0` (true/false).

**Step 2: Analyze source (RAG + impact reasoning)**

```bash
curl -X POST http://localhost:8000/api/v1/legal-tracker/analyze-source \
  -H "Content-Type: application/json" \
  -d '{"source_type": "case", "source_id": 1}'
```

Returns impacted sections with reasoning preview.

**Step 3: Aggregate into tasks**

```bash
curl -X POST "http://localhost:8000/api/v1/legal-tracker/aggregate-analysis?source_type=case&source_id=1"
```

**Step 4: List tasks**

```bash
curl http://localhost:8000/api/v1/tasks/list
```

**Step 5: Get task details**

```bash
curl http://localhost:8000/api/v1/tasks/1
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Overview and flow |
| GET | `/healthcheck` | Health check |
| GET | `/docs` | Swagger UI |
| POST | `/api/v1/case_bundle/ingest` | Ingest case |
| POST | `/api/v1/legislation_bundle/ingest` | Ingest legislation |
| GET | `/api/v1/case_bundle/list` | List cases |
| GET | `/api/v1/legislation_bundle/list` | List legislation |
| POST | `/api/v1/legal-tracker/analyze-source` | RAG + impact reasoning |
| POST | `/api/v1/legal-tracker/aggregate-analysis` | Create tasks from impacts |
| GET | `/api/v1/tasks/list` | List tasks |
| GET | `/api/v1/tasks/{id}` | Task details |
| PATCH | `/api/v1/tasks/{id}` | Update task status |
| GET | `/api/v1/publications` | List publications |
| GET | `/api/v1/trackers` | List trackers |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./ace_poc.db` | Database URL |
| `OPENAI_API_KEY` | (empty) | If set, uses OpenAI for impact reasoning; else mock |
| `RAG_TOP_K` | 5 | Number of sections to retrieve |

Copy `.env.example` to `.env` to override.

---

## Project Structure

```
ace-poc/
├── main.py              # FastAPI app
├── config.py            # Settings
├── models.py            # SQLAlchemy models
├── database.py          # DB setup
├── api/
│   ├── data_injection.py # Ingest APIs
│   ├── schedule.py      # Analyze + aggregate
│   └── tracker_center.py# Task APIs
├── services/
│   ├── p0_filter.py     # P0 gating
│   ├── rag_service.py   # ChromaDB + embeddings
│   └── ai_service.py    # Impact reasoning (mock/OpenAI)
├── scripts/
│   └── seed_db.py       # Seed data
└── requirements.txt
```

---

## What This POC Demonstrates

1. **P0 filter** — Court level, decision date (90 days), Shepard's letters for cases; effect type for legislation.
2. **RAG** — Semantic search over analytical sections (ChromaDB + sentence-transformers).
3. **Impact reasoning** — Mock or OpenAI-generated "what, how, why" for each impacted section.
4. **Task creation** — Section impacts → editor tasks with status (NEW, UPDATING, PUBLISHED).

---

## Limitations

- Single-process; no Airflow, SQS, or distributed workers.
- SQLite; production would use MySQL/Postgres.
- Embedding model loaded at first request; no GPU acceleration.
- No real CASCI, DataLake, Shepard's, or Contenta integration.

---

## Troubleshooting

**SSL / pip install fails:** Ensure Python and pip can reach PyPI. You may need to configure certificates or use a corporate proxy.

**sentence-transformers download slow:** The first run downloads `all-MiniLM-L6-v2` (~90MB). Subsequent runs use the cache.

## License

Internal POC — for demonstration only.
