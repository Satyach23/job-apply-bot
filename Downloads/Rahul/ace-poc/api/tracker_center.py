"""ACE POC - Tracker Center API (tasks, publications, trackers)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Task, Section, LegalCase, Legislation, Tracker, Publication

router = APIRouter(prefix="/api/v1", tags=["Tracker Center"])


# --- Schemas ---


class TaskUpdateRequest(BaseModel):
    status: str | None = None  # NEW, UPDATING, PUBLISHED


# --- Endpoints ---


@router.get("/tasks/list")
async def list_tasks(
    status: str | None = Query(None),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List tasks for editors."""
    q = select(Task).order_by(Task.id.desc()).limit(limit)
    if status:
        q = q.where(Task.status == status)
    r = await db.execute(q)
    tasks = r.scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "section_id": t.section_id,
            "source_type": t.source_type,
            "source_id": t.source_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Get task details with section and source info."""
    r = await db.execute(select(Task).where(Task.id == task_id))
    task = r.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}

    section = None
    if task.section_id:
        r = await db.execute(select(Section).where(Section.id == task.section_id))
        sec = r.scalar_one_or_none()
        if sec:
            section = {"id": sec.id, "title": sec.title, "title_path": sec.title_path}

    source = None
    if task.source_type == "case" and task.source_id:
        r = await db.execute(select(LegalCase).where(LegalCase.id == task.source_id))
        c = r.scalar_one_or_none()
        if c:
            source = {"type": "case", "case_name": c.case_name, "citation": c.citation}
    elif task.source_type == "legislation" and task.source_id:
        r = await db.execute(select(Legislation).where(Legislation.id == task.source_id))
        l = r.scalar_one_or_none()
        if l:
            source = {"type": "legislation", "title": l.title, "citation": l.citation}

    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "reasoning": task.reasoning,
        "section": section,
        "source": source,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    req: TaskUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update task status (e.g. NEW → UPDATING → PUBLISHED)."""
    r = await db.execute(select(Task).where(Task.id == task_id))
    task = r.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}
    if req.status:
        task.status = req.status
    return {"id": task.id, "status": task.status}


@router.get("/publications")
async def list_publications(db: AsyncSession = Depends(get_db)):
    """List publications."""
    r = await db.execute(select(Publication))
    pubs = r.scalars().all()
    return [{"id": p.id, "name": p.name, "jurisdiction": p.jurisdiction} for p in pubs]


@router.get("/trackers")
async def list_trackers(db: AsyncSession = Depends(get_db)):
    """List trackers."""
    r = await db.execute(select(Tracker))
    trackers = r.scalars().all()
    return [{"id": t.id, "name": t.name, "publication_id": t.publication_id} for t in trackers]
