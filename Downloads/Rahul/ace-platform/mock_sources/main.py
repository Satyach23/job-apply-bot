"""Mock Data Sources - DAND, DataLake, CASCI, Shepard's (for local dev)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Data Sources", version="0.1.0")

# In-memory mock data
MOCK_CASCI_ASSIGNMENTS = [
    {"id": "casci-1", "case_name": "Smith v. Acme Corp", "citation": "42 F.4th 100", "court": "US Court of Appeals"},
    {"id": "casci-2", "title": "ADA Amendments Act 2025", "effect_type": "amended"},
]
MOCK_DATALAKE_OBJECTS = {}
MOCK_SHEPARD = {"Smith v. Acme": {"letters": "O,W"}, "Jones v. State": {"letters": "A"}}


@app.get("/mock/casci/poll")
async def casci_poll():
    """CASCI polling - returns case/legislation assignments."""
    return {"assignments": MOCK_CASCI_ASSIGNMENTS, "count": len(MOCK_CASCI_ASSIGNMENTS)}


@app.get("/mock/datalake/objects/v1/{object_id}")
async def datalake_get(object_id: str, collection_id: str = ""):
    """DataLake object fetch (simulated)."""
    key = f"{collection_id}/{object_id}"
    if key in MOCK_DATALAKE_OBJECTS:
        return MOCK_DATALAKE_OBJECTS[key]
    return {"content": "mock xml content", "object_id": object_id}


@app.get("/mock/shepard/{case_name}")
async def shepard_get(case_name: str):
    """Shepard's treatment letters (simulated)."""
    for k, v in MOCK_SHEPARD.items():
        if k.lower() in case_name.lower():
            return v
    return {"letters": ""}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "mock-sources"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
