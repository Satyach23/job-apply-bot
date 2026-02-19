"""tracker_center_svc - Tracker, publication, task, user APIs. Port 8002."""
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

from lt_common.database import (
    LegalCase,
    Legislation,
    Publication,
    Section,
    Task,
    Tracker,
    get_db,
    init_db,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="tracker_center_svc", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TaskSyncRequest(BaseModel):
    source_type: str
    source_id: int
    task_ids: list[int]


class TaskUpdateRequest(BaseModel):
    status: str | None = None


@app.get("/api/v1/tracker")
async def list_trackers(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Tracker))
    return [{"id": t.id, "name": t.name, "publication_id": t.publication_id} for t in r.scalars().all()]


@app.get("/api/v1/publication")
async def list_publications(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Publication))
    return [{"id": p.id, "name": p.name, "jurisdiction": p.jurisdiction} for p in r.scalars().all()]


@app.get("/api/v1/tasks/list")
async def list_tasks(status: str | None = Query(None), limit: int = Query(50, le=100), db: AsyncSession = Depends(get_db)):
    q = select(Task).order_by(Task.id.desc()).limit(limit)
    if status:
        q = q.where(Task.status == status)
    r = await db.execute(q)
    return [
        {"id": t.id, "title": t.title, "status": t.status, "section_id": t.section_id, "source_type": t.source_type, "source_id": t.source_id}
        for t in r.scalars().all()
    ]


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
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
        "id": task.id, "title": task.title, "status": task.status, "reasoning": task.reasoning,
        "section": section, "source": source, "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@app.patch("/api/v1/tasks/{task_id}")
async def update_task(task_id: int, req: TaskUpdateRequest, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Task).where(Task.id == task_id))
    task = r.scalar_one_or_none()
    if not task:
        return {"error": "Task not found"}
    if req.status:
        task.status = req.status
    return {"id": task.id, "status": task.status}


@app.post("/api/v1/tasks/sync")
async def sync_tasks(req: TaskSyncRequest, db: AsyncSession = Depends(get_db)):
    """Called by schedule_svc to sync tasks."""
    return {"synced": True, "task_ids": req.task_ids}


@app.get("/api/v1/user")
async def user_info():
    return {"user": "mock-editor", "roles": ["editor"]}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "tracker_center_svc"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
