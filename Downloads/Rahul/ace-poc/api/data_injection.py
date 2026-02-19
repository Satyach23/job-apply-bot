"""ACE POC - Data Injection API (ingest cases & legislation)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import LegalCase, Legislation
from services.p0_filter import passes_p0_case, passes_p0_legislation
from dateutil import parser as date_parser

router = APIRouter(prefix="/api/v1", tags=["Data Injection"])


# --- Schemas ---


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


# --- Endpoints ---


@router.post("/case_bundle/ingest")
async def ingest_case(
    req: CaseIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a new case. Applies P0 filter."""
    passed, reason = passes_p0_case(
        req.court,
        req.decision_date,
        req.shepard_letters,
    )

    case = LegalCase(
        case_name=req.case_name,
        citation=req.citation,
        court=req.court,
        decision_date=date_parser.parse(req.decision_date) if req.decision_date else None,
        jurisdiction=req.jurisdiction,
        headnotes=req.headnotes,
        faceted_summary=req.faceted_summary,
        shepard_letters=req.shepard_letters,
        passed_p0=1 if passed else 0,
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)

    return {
        "id": case.id,
        "passed_p0": bool(passed),
        "p0_reason": reason,
    }


@router.post("/legislation_bundle/ingest")
async def ingest_legislation(
    req: LegislationIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest legislation change. Applies P0 filter."""
    passed, reason = passes_p0_legislation(
        req.effect_type,
        req.effective_date,
    )

    leg = Legislation(
        title=req.title,
        citation=req.citation,
        effect_type=req.effect_type,
        effective_date=date_parser.parse(req.effective_date) if req.effective_date else None,
        summary=req.summary,
        passed_p0=1 if passed else 0,
    )
    db.add(leg)
    await db.flush()
    await db.refresh(leg)

    return {
        "id": leg.id,
        "passed_p0": bool(passed),
        "p0_reason": reason,
    }


@router.get("/case_bundle/list")
async def list_cases(db: AsyncSession = Depends(get_db)):
    """List ingested cases."""
    r = await db.execute(select(LegalCase).order_by(LegalCase.id.desc()).limit(50))
    cases = r.scalars().all()
    return [{"id": c.id, "case_name": c.case_name, "passed_p0": bool(c.passed_p0)} for c in cases]


@router.get("/legislation_bundle/list")
async def list_legislations(db: AsyncSession = Depends(get_db)):
    """List ingested legislation."""
    r = await db.execute(select(Legislation).order_by(Legislation.id.desc()).limit(50))
    legs = r.scalars().all()
    return [{"id": l.id, "title": l.title, "passed_p0": bool(l.passed_p0)} for l in legs]
