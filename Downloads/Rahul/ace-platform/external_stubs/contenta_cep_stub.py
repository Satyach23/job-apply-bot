"""Stub for Contenta CMS + CEP Pipeline (Publisher, ToC, Enrichment, Loader)."""
from fastapi import FastAPI

app = FastAPI(title="Contenta/CEP Stub", version="0.1.0")


@app.post("/api/v1/lock")
async def lock(content_id: str):
    return {"locked": True, "content_id": content_id}


@app.post("/api/v1/unlock")
async def unlock(content_id: str):
    return {"unlocked": True, "content_id": content_id}


@app.post("/api/v1/xml/sync")
async def xml_sync(payload: dict):
    return {"synced": True}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "contenta-cep-stub"}
