"""data_injection_svc - Ingest case/legislation, SQS listeners, Solr ETL. Port 8001."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lt_common"))

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dateutil import parser as date_parser
from lt_common.database import get_db, init_db, LegalCase, Legislation
from lt_common.config import settings
from lt_common.infrastructure.storage.queue_client import QueueClient
from lt_common.libs.shepards import parse_shepard_letters

# P0 filter
def passes_p0_case(court, decision_date, shepard_letters) -> tuple[bool, str]:
    from datetime import timedelta
    if not court:
        return False, "Missing court"
    court_ok = any(p in (court or "") for p in settings.p0_courts) or "Supreme" in (court or "") or "Circuit" in (court or "")
    if not court_ok:
        return False, f"Court not in P0 list"
    if decision_date:
        try:
            d = date_parser.parse(decision_date).date() if isinstance(decision_date, str) else (decision_date.date() if hasattr(decision_date, "date") else decision_date)
            if d < (datetime.utcnow() - timedelta(days=settings.case_decision_days_limit)).date():
                return False, "Decision date too old"
        except Exception:
            pass
    return True, "Passed P0"


def passes_p0_legislation(effect_type, effective_date) -> tuple[bool, str]:
    if effect_type and effect_type.lower() not in {"amended", "new", "added"}:
        return False, "Invalid effect type"
    return True, "Passed P0"


queue_client = QueueClient()
listener_task = None


async def sqs_listener_loop():
    """SQS listener - polls queues and triggers ingestion."""
    while settings.enable_case_sqs_listener:
        try:
            msgs = await queue_client.receive_case_messages(5)
            for m in msgs:
                # Process case message - would call case_bundle API
                pass
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    global listener_task
    if settings.enable_case_sqs_listener:
        listener_task = asyncio.create_task(sqs_listener_loop())
    yield
    if listener_task:
        listener_task.cancel()


app = FastAPI(title="data_injection_svc", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CaseIngestRequest(BaseModel):
    case_name: str
    citation: str | None = None
    court: str | None = None
    decision_date: str | None = None
    jurisdiction: str | None = None
    headnotes: str | None = None
    faceted_summary: str | None = None
    shepard_letters: str | None = None


class LegislationIngestRequest(BaseModel):
    title: str
    citation: str | None = None
    effect_type: str | None = None
    effective_date: str | None = None
    summary: str | None = None


@app.post("/api/v1/case_bundle/ingest")
async def ingest_case(req: CaseIngestRequest, db: AsyncSession = Depends(get_db)):
    passed, reason = passes_p0_case(req.court, req.decision_date, req.shepard_letters)
    case = LegalCase(
        case_name=req.case_name, citation=req.citation, court=req.court,
        decision_date=date_parser.parse(req.decision_date) if req.decision_date else None,
        jurisdiction=req.jurisdiction, headnotes=req.headnotes, faceted_summary=req.faceted_summary,
        shepard_letters=req.shepard_letters, passed_p0=1 if passed else 0,
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return {"id": case.id, "passed_p0": bool(passed), "p0_reason": reason}


@app.post("/api/v1/legislation_bundle/ingest")
async def ingest_legislation(req: LegislationIngestRequest, db: AsyncSession = Depends(get_db)):
    passed, reason = passes_p0_legislation(req.effect_type, req.effective_date)
    leg = Legislation(
        title=req.title, citation=req.citation, effect_type=req.effect_type,
        effective_date=date_parser.parse(req.effective_date) if req.effective_date else None,
        summary=req.summary, passed_p0=1 if passed else 0,
    )
    db.add(leg)
    await db.flush()
    await db.refresh(leg)
    return {"id": leg.id, "passed_p0": bool(passed), "p0_reason": reason}


@app.get("/api/v1/case_bundle/list")
async def list_cases(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(LegalCase).order_by(LegalCase.id.desc()).limit(50))
    return [{"id": c.id, "case_name": c.case_name, "passed_p0": bool(c.passed_p0)} for c in r.scalars().all()]


@app.get("/api/v1/legislation_bundle/list")
async def list_legislations(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Lislation).order_by(Legislation.id.desc()).limit(50))
    return [{"id": l.id, "title": l.title, "passed_p0": bool(l.passed_p0)} for l in r.scalars().all()]


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "data_injection_svc"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
