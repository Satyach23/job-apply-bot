"""schedule_svc - AI orchestration, aggregate-analysis, Task Center sync. Port 8000."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lt_common"))

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import httpx
from lt_common.database import (
    LegalCase,
    Legislation,
    Section,
    SectionImpact,
    Task,
    Tracker,
    get_db,
    init_db,
)
from lt_common.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="schedule_svc", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AnalyzeSourceRequest(BaseModel):
    source_type: str
    source_id: int


@app.post("/api/v1/legal-tracker/analyze-source")
async def analyze_source(req: AnalyzeSourceRequest, db: AsyncSession = Depends(get_db)):
    """Calls AI service for RAG + impact reasoning."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{settings.ai_service_url}/api/v1/analyze-impact",
                json={"source_type": req.source_type, "source_id": req.source_id},
                timeout=60,
            )
            if r.status_code != 200:
                return {"error": "AI service unavailable", "detail": r.text}
            data = r.json()
    except Exception as e:
        return {"error": "AI service error", "detail": str(e)}

    impacts = data.get("impacts", [])
    for imp in impacts:
        si = SectionImpact(
            section_id=imp["section_id"],
            legal_case_id=req.source_id if req.source_type == "case" else None,
            legislation_id=req.source_id if req.source_type == "legislation" else None,
            reasoning=imp.get("reasoning", ""),
            relevance_score=imp.get("relevance_score", 0.9),
        )
        db.add(si)

    return {"message": "Analysis complete", "impacts": impacts}


@app.post("/api/v1/legal-tracker/aggregate-analysis")
async def aggregate_analysis(
    source_type: str = Query(...),
    source_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    cond = SectionImpact.legal_case_id == source_id if source_type == "case" else SectionImpact.legislation_id == source_id
    r = await db.execute(select(SectionImpact).where(cond))
    impacts = r.scalars().all()
    if not impacts:
        return {"message": "No impacts", "tasks": []}

    first = impacts[0]
    r = await db.execute(select(Section).where(Section.id == first.section_id))
    section = r.scalar_one_or_none()
    if not section:
        return {"message": "Section not found", "tasks": []}

    r = await db.execute(select(Tracker).where(Tracker.publication_id == section.publication_id).limit(1))
    tracker = r.scalar_one_or_none()
    if not tracker:
        tracker = Tracker(name=f"Tracker-Pub-{section.publication_id}", publication_id=section.publication_id)
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

    # Sync to Task Center
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.task_center_url}/api/v1/tasks/sync",
                json={"source_type": source_type, "source_id": source_id, "task_ids": [t["id"] for t in tasks]},
                timeout=10,
            )
    except Exception:
        pass

    return {"message": "Tasks created", "tasks": tasks}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "schedule_svc"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
