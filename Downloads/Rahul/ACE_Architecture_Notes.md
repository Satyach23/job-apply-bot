# ACE / L+CP Analytical Platform — Architecture Notes

> Use this document while looking at the architecture diagram. Each section maps to a layer or region in the diagram.

---

## Document Purpose

This file explains the ACE (Analytical Content Engine) / L+CP Analytical Platform architecture **layer by layer**. Use it to onboard new team members, present to stakeholders, or walk through the system during reviews.

---

## What Is ACE? (30-Second Overview)

ACE is an **internal platform** that keeps our legal analytical content (treatises, commentaries, practice guides) **current** when case law and legislation change. It:

1. **Ingests** new cases and legislation from external sources
2. **Filters** to high-signal changes (P0)
3. **Uses AI** (RAG + LLMs) to find which book sections are impacted and why
4. **Creates tasks** for editors in a Task Center
5. **Integrates** with our repository, CMS, and publishing pipeline

**Users:** Internal legal editors, content managers, and platform/operations teams — not end customers.

---

## How to Read the Diagram (Top to Bottom)

The diagram is roughly organized in **layers**:

| Order | Layer | What You'll See |
|-------|-------|-----------------|
| 1 | User Access | Browser, SSO, Load Balancer |
| 2 | Data Sources | DAND, DataLake, SQS, Shepard's, CASCI |
| 3 | Orchestration | Airflow DAGs (Commentary + Legal Tracker) |
| 4 | Backend Services | tracker_center_svc, schedule_svc, data_injection_svc |
| 5 | AI Services | ADK, RAG, P0/P1 Filters |
| 6 | Task & Commentary | Task Center API, repository_service, task_service, CAAS |
| 7 | External Systems | Contenta, xWeb, CEP, Neptune, MNCR/SES |
| 8 | Storage | MySQL, S3, Solr, DocumentDB, SQS |
| 9 | Monitoring | Loguru, Splunk, Coralogix, Secrets Manager |

---

## Layer 1: User Access Layer

**Where in diagram:** Top-left region (Browser, SSO, Load Balancer).

### What It Does

This is how **people** reach the platform. Editors, managers, and operators use the UI and APIs through a secure, load-balanced entry point.

### Components

| Component | Description |
|-----------|-------------|
| **Browser** | Frontend (React / Node.js). Editors see Task Center, task details, and content tools. |
| **SSO** | Single Sign-On. One login for all internal apps. (Provider TBD in diagram.) |
| **Load Balancer** | ALB or NLB. Distributes traffic across backend instances. |
| **Production Runtime** | Gunicorn + Uvicorn, Docker (python:3.10-slim). How the apps run. |

### Key Point

- **Reporting (INSIGHT/Tableau):** CDC sync and E2E dashboard. Used for metrics (currency, time to market). Details may vary by environment.

---

## Layer 2: Data Sources

**Where in diagram:** Top-right region (DAND, DataLake, SQS queues, Shepard's, CASCI).

### What It Does

This layer is **where new legal data comes from**. All case, legislation, and citation data flows in from here before processing.

### Components

| Source | What It Provides |
|--------|------------------|
| **DAND Profile** | Legislation and case metadata. |
| **DataLake** | Raw legal documents, case/legislation data. |
| **SQS Books Queue** | Content-update triggers (e.g. BooksMonitor). |
| **SQS Case Source** | New case data delivery. |
| **Shepard's Citations** | Treatment letters (e.g. overruled by, withdrawn by). Used as P0 signal for case impact. |
| **CASCI Polling** | Case/legislation assignments from US indexing system (CASCI). |

### Key Point

- These sources feed **data_injection_svc** and **Airflow DAGs**. No data = no updates.

---

## Layer 3: Airflow DAGs / Workflow Orchestration Hub

**Where in diagram:** Orange/yellow region in the middle-top.

### What It Does

**Apache Airflow** runs scheduled workflows. Two main groups: **Commentary** (content workflow) and **Legal Tracker** (case/legislation processing).

### 3a. Commentary Orchestration (Left)

| DAG | Purpose |
|-----|---------|
| **submit_task_dag** | Entry point. Routes by `task_type`. |
| **create_task_dag** | Task creation (CRUD) + assignment email. |
| **lni_crv_processes_dag** | LNI → Repo → CEP → Contenta sync. |
| **task_status_flow_dag** | Status transitions: NEW → UPDATING → PUBLISHED. |

### 3b. Legal Tracker Orchestration (Right)

| DAG | Purpose |
|-----|---------|
| **casci_polling_dag** | Poll CASCI for new case/legislation assignments. |
| **lt_ingestion_case_process_dag** | Case processing pipeline. |
| **legislation_ingestion_dag** | Legislation ingestion. |
| **ai_single_case_processor** | Single-case AI analysis. |
| **monitor_case_dag** | Case monitoring / status checks. |
| **PQRT_case_finder** | Case finder (purpose may need clarification). |
| **PQRT_legislation_finder** | Legislation finder (purpose may need clarification). |
| **content_search_summary** | Content search summary (purpose may need clarification). |

### Key Point

- Airflow **orchestrates** the flows; the actual logic lives in the backend services (schedule_svc, data_injection_svc) and AI services.

---

## Layer 4: Backend Microservices & Shared Library

**Where in diagram:** Blue region in the center.

### What It Does

Core business logic and APIs. Three main services plus a shared library.

### 4a. lt_common (Shared Library)

| Responsibility | Details |
|----------------|---------|
| ORM / DB | SQLAlchemy ^2.x, async DB connection pool. |
| Storage clients | S3Client, DataLakeClient, AIStorageService. |
| Config | `settings.py`, advanced_settings (env, Secrets Manager). |
| Shepard's parsing | `libs/shepards` for Shepard's XML. |

### 4b. tracker_center_svc (Port 8002)

| Responsibility | Details |
|----------------|---------|
| APIs | `/api/v1/tracker`, `/publication`, `/tasks`, `/user`. |
| Role | Frontend-facing. Trackers, publications, task pages, users. |
| Dependencies | MySQL, Task Center. |

### 4c. schedule_svc (Port 8000)

| Responsibility | Details |
|----------------|---------|
| **analyze-source** | Calls AI service, stores results in DB. |
| **aggregate-analysis** | Aggregates per tracker/chapter, pushes to Task Center. |
| Task Center sync | Keeps tasks and chapter links in sync. |
| SQS enqueue | Sends work to AI task queue. |

### 4d. data_injection_svc (Port 8001)

| Responsibility | Details |
|----------------|---------|
| **case_bundle** APIs | Ingest case data. |
| **legislation_bundle** APIs | Ingest legislation data. |
| SQS listeners | CaseInjectionHandler, BooksMonitor (default on). |
| Solr ETL | 5 stages: XML parse → Section extract → Level convert → Solr doc gen → Citation enrich (JCite). |
| P0 filtering | Court level, decision date (90d), Shepard's treatment letters. |

### Key Point

- All three services use **lt_common** for DB, storage, and config.

---

## Layer 5: AI Services

**Where in diagram:** Pink/red region on the left.

### What It Does

AI is used to find **which book sections** are impacted by a new case or law, and **why**. Two main components: **RAG** (retrieval) and **ADK** (reasoning).

### 5a. P0/P1 Gating Filters

| Filter | Purpose |
|--------|---------|
| **P0 (Cases)** | Court level, decision date (90d), Shepard's treatment letters. |
| **P0 (Legislation)** | `effectType` filter. |
| **P1 (Post-MVP)** | PA (practice area), jurisdiction, title/structure constraints. |

### 5b. ADK Service (adk_api)

| Responsibility | Details |
|----------------|---------|
| Tech | Google ADK + LiteLLM, Python 3.13. |
| Case pipeline | case_para_agent (parallel: case_history, cited_case, cited_statute, rerank) → summary_bundle_agent. |
| Legislation pipeline | Similar structure. |
| Impact reasoning | LLM-based decision: does this section need an update? |

### 5c. RAG Service (rag_api)

| Responsibility | Details |
|----------------|---------|
| Tech | FastAPI, Solr, ModernBERT (GPU). |
| Semantic search | BM25 + embeddings, MoE reranker, multi-signal. |
| Citation search | Pre-extracted citation index; matches cases/legislation. |
| MVP note | Legislation uses citation search only (no semantic for legislation yet). |

### Key Point

- **RAG** finds candidate sections; **ADK** decides if they need updates and generates reasoning for editors.

---

## Layer 6: Task Center & Commentary Services

**Where in diagram:** Purple region (Task Center API, repository_service, task_service, CAAS Repo).

### What It Does

Manages **tasks** for editors and **repository** for content. Editors see what to update, where, and why.

### 6a. Task Center API

| Responsibility | Details |
|----------------|---------|
| Task CRUD | Create, update, query tasks. |
| Chapter aggregation | Groups impacts by chapter. |
| DB tables | tracker_chapter_task_links, user_editable_section_impacts. |

### 6b. repository_service

| Responsibility | Details |
|----------------|---------|
| Tech | FastAPI + Async SQLAlchemy. |
| Object hierarchy | Metadata, file upload/download (CAAS). |
| Integrations | xWeb, Contenta CMS sync, Datalake upload. |

### 6c. task_service

| Responsibility | Details |
|----------------|---------|
| Task lifecycle | CRUD, status FSM (NEW → UPDATING → PUBLISHED). |
| Notifications | SES email. |
| Integration | tracker_center_svc. |

### 6d. CAAS Repo Service

| Responsibility | Details |
|----------------|---------|
| Tech | FastAPI + Beanie/Motor. |
| S3 | Upload/download, versioning, presigned URLs. |
| DocumentDB | Metadata, aiobotocore. |

### Key Point

- Editors interact with Task Center and repository; CAAS holds file content and metadata.

---

## Layer 7: Post-MVP Scaling (6 → 60 Publications)

**Where in diagram:** Orange box (Post-MVP Scaling).

### What It Does

Strategy to scale from 6 to 60+ publications without overwhelming editors with noise.

### Strategy: "Filter early → retrieve narrow → reason deep"

| Agent / Constraint | Purpose |
|--------------------|---------|
| **PA Constraint Agent** | Practice area filtering. |
| **Batch Filter Agent** | Per-publication coarse gate. |
| **Row Filter Agent** | Fine-grained per-record filter. |
| **Title/Structure Constraints** | Jurisdiction, act/statute, topic boundaries. |

### Targets

- 60 pubs (Q1) → 200 pubs (Q2).
- Golden dataset + precision/recall + SME feedback for evaluation.

---

## Layer 8: External Systems & Integrations

**Where in diagram:** Green region (bottom-left).

### What It Does

Connects ACE to our CMS, editors, and publishing pipeline.

### Components

| System | Role |
|--------|------|
| **Contenta CMS** | Lock/unlock, XML sync. 6 titles for MVP. |
| **xWeb Editor** | Browser-based XML editor for authors. |
| **CEP Pipeline** | Publisher → ToC → Enrichment → Loader. |
| **Neptune** | Legacy CMS (migration TBD). |
| **MNCR / SES** | LNI generator, email notifications. |

---

## Layer 9: Storage Layer

**Where in diagram:** Yellow/cylinder region at the bottom.

### What It Does

Persistent storage for all data: cases, legislation, AI results, tasks, content.

### Stores

| Store | Contents |
|-------|----------|
| **MySQL / RDS** | legal_cases, legislations, section_impacts, case_section_summaries, trackers, tracker_chapter_task_links, user_editable_section_impacts, commentary_task, commentary_repository. |
| **AWS S3** | AI input/output, repo content, presigned URLs. |
| **Apache Solr** | AM section chunks, BM25 + embeddings, citation index. ETL-fed. |
| **DocumentDB** | CAAS metadata, file versioning. |
| **AWS SQS** | Books Queue, Case Source Queue. |

---

## Layer 10: Monitoring & Observability

**Where in diagram:** Brown/gray bar at the very bottom.

### What It Does

Logging, monitoring, and secret management.

### Components

| Component | Purpose |
|-----------|---------|
| **Loguru + OpenTelemetry** | Structured logging, tracing. |
| **Splunk** | DEV & CERT. |
| **Coralogix** | PROD cluster and service monitoring. |
| **AWS Secrets Manager** | DB creds, API keys, config. |

---

## Data Flow Summary (End-to-End)

```
Data Sources (DAND, DataLake, SQS, Shepard's, CASCI)
    ↓
data_injection_svc (ingest, P0 filter, Solr ETL)
    ↓
Airflow DAGs (orchestrate Legal Tracker workflows)
    ↓
schedule_svc (analyze-source → AI)
    ↓
AI Services (ADK + RAG: find sections, impact reasoning)
    ↓
schedule_svc (aggregate-analysis → Task Center)
    ↓
Task Center + repository (tasks for editors)
    ↓
Editors (xWeb, Contenta) → CEP → Publish
```

---

## Tech Stack Quick Reference

| Category | Technologies |
|----------|--------------|
| Language | Python 3.10–3.13 |
| API | FastAPI ^0.109.1, Uvicorn ^0.24.0 |
| DB | SQLAlchemy ^2.x, Alembic |
| AI | Google ADK, LiteLLM, ModernBERT (GPU) |
| Search | Apache Solr |
| Orchestration | Apache Airflow |
| Cloud | AWS (RDS, S3, SQS, DocumentDB, SES, Secrets Manager) |
| Frontend | React, Node.js |

---

## Glossary (for Team Discussions)

| Term | Meaning |
|------|---------|
| **ACE** | Analytical Content Engine — this platform. |
| **L+CP** | Lexis+ Content Platform. |
| **P0 / P1** | Gating filters (P0 = MVP, P1 = post-MVP). |
| **RAG** | Retrieval Augmented Generation — Solr + reranker + reasoning. |
| **ADK** | Agent Development Kit (Google). |
| **CEP** | Content Enrichment Pipeline (Publisher, ToC, Enrichment, Loader). |
| **CASCI** | US indexing system for case/legislation assignments. |
| **Shepard's** | Citation treatment (overruled, withdrawn, etc.). |
| **CAAS** | Content storage (S3 + DocumentDB). |

---

*Last updated from architecture diagram and supporting documents.*
