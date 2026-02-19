"""repository_service - Object hierarchy, file upload/download, xWeb, Contenta sync."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from lt_common.database import RepositoryObject, get_db, init_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="repository_service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/v1/objects")
async def list_objects(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(RepositoryObject).limit(100))
    return [{"id": o.id, "obj_type": o.obj_type, "title": o.title, "path": o.path} for o in r.scalars().all()]


@app.post("/api/v1/objects/upload")
async def upload_file(file: UploadFile, path: str = "", db: AsyncSession = Depends(get_db)):
    content = await file.read()
    obj = RepositoryObject(obj_type="file", title=file.filename, path=path or file.filename)
    db.add(obj)
    await db.flush()
    return {"id": obj.id, "path": obj.path}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "repository_service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
