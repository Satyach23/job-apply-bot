"""ACE POC - Main FastAPI application."""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.data_injection import router as data_injection_router
from api.schedule import router as schedule_router
from api.tracker_center import router as tracker_center_router
from database import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="ACE POC - Analytical Content Engine",
        description="Proof of concept: ingest → P0 filter → RAG → impact reasoning → tasks",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(data_injection_router)
    app.include_router(schedule_router)
    app.include_router(tracker_center_router)

    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.get("/healthcheck")
    async def healthcheck():
        return {"status": "ok", "service": "ace-poc"}

    @app.get("/")
    async def root():
        return {
            "message": "ACE POC - Analytical Content Engine",
            "docs": "/docs",
            "flow": "1. POST /api/v1/case_bundle/ingest or legislation_bundle/ingest → 2. POST /api/v1/legal-tracker/analyze-source → 3. POST /api/v1/legal-tracker/aggregate-analysis → 4. GET /api/v1/tasks/list",
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
