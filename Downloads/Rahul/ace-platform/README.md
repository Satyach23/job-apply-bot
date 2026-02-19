# ACE Platform — Full Architecture Implementation

This implements the ACE / L+CP Analytical Platform architecture as per the diagram: **separate microservices**, **Airflow DAGs**, **SQS listeners**, **mock data sources**, and **Commentary services**.

---

## Architecture Overview

```
Data Sources (DAND, DataLake, SQS, Shepard's, CASCI)
    ↓
mock_sources (8200) - Simulated CASCI, DataLake, Shepard's
    ↓
data_injection_svc (8001) - Ingest + P0 filter + SQS listeners
    ↓
Airflow DAGs - casci_polling, lt_ingestion, lni_crv, task_status_flow
    ↓
schedule_svc (8000) - analyze-source, aggregate-analysis
    ↓
ai_service (8100) - RAG + impact reasoning
    ↓
tracker_center_svc (8002) - Task Center, tracker, publication, user APIs
    ↓
commentary/repository_service (8003) - Object hierarchy, file upload
```

---

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **mock_sources** | 8200 | DAND, DataLake, CASCI, Shepard's (mock) |
| **data_injection_svc** | 8001 | case_bundle, legislation_bundle, SQS listeners |
| **schedule_svc** | 8000 | analyze-source, aggregate-analysis |
| **tracker_center_svc** | 8002 | tracker, publication, tasks, user |
| **ai_service** | 8100 | RAG + impact reasoning |
| **repository_service** | 8003 | Commentary - objects, upload |

---

## Airflow DAGs

Located in `airflow/dags/`:

| DAG | Purpose |
|-----|---------|
| **casci_polling_dag** | Poll CASCI, trigger ingestion |
| **lt_ingestion_case_process_dag** | Case processing pipeline |
| **ai_single_case_processor_dag** | Single-case AI analysis |
| **submit_task_dag** | Commentary - route by task_type |
| **lni_crv_processes_dag** | LNI → Repo → CEP → Contenta |
| **task_status_flow_dag** | Status transitions |

> Copy DAGs to your Airflow `dags/` folder. Requires Airflow + `httpx`.

---

## Quick Start (Local Dev)

### 1. Install

```bash
cd ace-platform
pip install -r requirements.txt
pip install -e lt_common  # or: set PYTHONPATH to include lt_common
```

### 2. Seed database and RAG

```bash
python scripts/seed_all.py
```

### 3. Run services

Set PYTHONPATH so all packages are found:

```bash
export PYTHONPATH=".:./lt_common"
```

Then run each in a separate terminal (or use `run_all.py`):

```bash
# Terminal 1: Mock sources
uvicorn mock_sources.main:app --port 8200

# Terminal 2: Data injection
uvicorn data_injection_svc.main:app --port 8001

# Terminal 3: Tracker center
uvicorn tracker_center_svc.main:app --port 8002

# Terminal 4: AI service
uvicorn ai_service.main:app --port 8100

# Terminal 5: Schedule service
uvicorn schedule_svc.main:app --port 8000
```

Or use the run script:

```bash
python scripts/run_all.py
```

### 4. Run end-to-end flow

```bash
# 1. Ingest case
curl -X POST http://localhost:8001/api/v1/case_bundle/ingest \
  -H "Content-Type: application/json" \
  -d '{"case_name":"Smith v. Acme","court":"US Court of Appeals","decision_date":"2025-01-15","shepard_letters":"O"}'

# 2. Analyze (returns case id=1)
curl -X POST http://localhost:8000/api/v1/legal-tracker/analyze-source \
  -H "Content-Type: application/json" \
  -d '{"source_type":"case","source_id":1}'

# 3. Aggregate
curl -X POST "http://localhost:8000/api/v1/legal-tracker/aggregate-analysis?source_type=case&source_id=1"

# 4. List tasks
curl http://localhost:8002/api/v1/tasks/list
```

---

## Docker

```bash
docker-compose up -d
```

> Ensure all services use the same database (shared volume for SQLite, or switch to MySQL).

---

## Project Structure

```
ace-platform/
├── lt_common/                 # Shared library
│   ├── lt_common/
│   │   ├── config/
│   │   ├── database/
│   │   ├── infrastructure/
│   │   └── libs/shepards/
├── data_injection_svc/        # Port 8001
├── schedule_svc/              # Port 8000
├── tracker_center_svc/        # Port 8002
├── ai_service/                # Port 8100
├── commentary/
│   └── repository_service/   # Port 8003
├── mock_sources/              # Port 8200
├── airflow/
│   └── dags/
├── scripts/
│   ├── seed_all.py
│   └── run_all.py
├── docker-compose.yml
├── Dockerfile.*
└── requirements.txt
```

---

## What's Implemented (vs Diagram)

| Component | Status |
|-----------|--------|
| lt_common (shared lib) | ✅ |
| data_injection_svc | ✅ |
| schedule_svc | ✅ |
| tracker_center_svc | ✅ |
| AI service (RAG + reasoning) | ✅ |
| SQS listeners (mock) | ✅ |
| Mock data sources (CASCI, DataLake, Shepard's) | ✅ |
| Commentary - repository_service | ✅ |
| Airflow DAGs (Commentary + Legal Tracker) | ✅ |
| Docker Compose | ✅ |
| Loguru logging | ✅ |

---

## Environment Variables

| Variable | Default |
|----------|---------|
| DATABASE_URL | sqlite+aiosqlite:///./ace_platform.db |
| TASK_CENTER_URL | http://localhost:8002 |
| AI_SERVICE_URL | http://localhost:8100 |
| ENABLE_CASE_SQS_LISTENER | true |
| OPENAI_API_KEY | (empty = mock reasoning) |
