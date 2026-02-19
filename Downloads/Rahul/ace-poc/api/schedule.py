"""ACE POC - Schedule Service API (analyze-source, aggregate-analysis)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import LegalCase, Legislation, Publication, Section, SectionImpact, Tracker, Task
from services.ai_service import generate_impact_reasoning
from services.rag_service import search_sections

router = APIRouter(prefix="/api/v1/legal-tracker", tags=["Schedule"])


# --- Schemas ---


class AnalyzeSourceRequest(BaseModel):
    source_type: str  # "case" or "legislation"
    source_id: int


# --- Endpoints ---


@router.post("/analyze-source")
async def analyze_source(
    req: AnalyzeSourceRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a case or legislation: find impacted sections via RAG, generate reasoning, store impacts.
    """
    if req.source_type == "case":
        r = await db.execute(select(LegalCase).where(LegalCase.id == req.source_id))
        obj = r.scalar_one_or_none()
        if not obj:
            return {"error": "Case not found"}
        if not obj.passed_p0:
            return {"error": "Case did not pass P0 filter"}
        query = f"{obj.headnotes or ''} {obj.faceted_summary or ''}".strip() or obj.case_name
        source_summary = f"{obj.case_name} - {obj.court or ''}"
    elif req.source_type == "legislation":
        r = await db.execute(select(Legislation).where(Legislation.id == req.source_id))
        obj = r.scalar_one_or_none()
        if not obj:
            return {"error": "Legislation not found"}
        if not obj.passed_p0:
            return {"error": "Legislation did not pass P0 filter"}
        query = f"{obj.title} {obj.summary or ''}".strip()
        source_summary = f"{obj.title} - {obj.effect_type or ''}"
    else:
        return {"error": "source_type must be 'case' or 'legislation'"}

    # RAG: find relevant sections
    hits = search_sections(query, top_k=5)
    if not hits:
        return {"message": "No relevant sections found", "impacts": []}

    impacts = []
    for h in hits:
        # Fetch section from DB
        r = await db.execute(select(Section).where(Section.id == h["id"]))
        section = r.scalar_one_or_none()
        if not section:
            continue

        reasoning = generate_impact_reasoning(
            req.source_type,
            source_summary,
            section.title or "",
            section.content or "",
        )

        impact = SectionImpact(
            section_id=section.id,
            legal_case_id=req.source_id if req.source_type == "case" else None,
            legislation_id=req.source_id if req.source_type == "legislation" else None,
            reasoning=reasoning,
            relevance_score=1.0 - (h.get("distance", 1) / 2) if h.get("distance") else 0.9,
        )
        db.add(impact)
        await db.flush()
        impacts.append({
            "section_id": section.id,
            "section_title": section.title,
            "reasoning_preview": reasoning[:200] + "..." if len(reasoning) > 200 else reasoning,
        })

    return {"message": "Analysis complete", "impacts": impacts}


@router.post("/aggregate-analysis")
async def aggregate_analysis(
    source_type: str = Query(...),
    source_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate section impacts into tasks for editors.
    Creates tasks in Task Center from SectionImpacts.
    """
    cond = (
        SectionImpact.legal_case_id == source_id
        if source_type == "case"
        else SectionImpact.legislation_id == source_id
    )
    r = await db.execute(select(SectionImpact).where(cond))
    impacts = r.scalars().all()
    if not impacts:
        return {"message": "No impacts to aggregate", "tasks": []}

    # Get or create tracker for first publication
    first_impact = impacts[0]
    r = await db.execute(select(Section).where(Section.id == first_impact.section_id))
    section = r.scalar_one_or_none()
    if not section:
        return {"message": "Section not found", "tasks": []}
    pub_id = section.publication_id

    r = await db.execute(select(Tracker).where(Tracker.publication_id == pub_id).limit(1))
    tracker = r.scalar_one_or_none()
    if not tracker:
        tracker = Tracker(name=f"Tracker-Pub-{pub_id}", publication_id=pub_id)
        db.add(tracker)
        await db.flush()

    tasks = []
    for imp in impacts:
        r = await db.execute(select(Section).where(Section.id == imp.section_id))
        sec = r.scalar_one_or_none()
        if not sec:
            continue
        task = Task(
            tracker_id=tracker.id,
            title=f"Update: {sec.title or sec.title_path}",
            status="NEW",
            section_id=sec.id,
            source_type=source_type,
            source_id=source_id,
            reasoning=imp.reasoning,
        )
        db.add(task)
        await db.flush()
        tasks.append({"id": task.id, "title": task.title})

    return {"message": "Tasks created", "tasks": tasks}
