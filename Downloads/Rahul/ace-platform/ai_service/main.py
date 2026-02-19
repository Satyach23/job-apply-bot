"""AI Service - RAG + Impact reasoning (ADK/RAG). Port 8100."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lt_common"))

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lt_common.database import LegalCase, Legislation, Section, get_db, init_db
from lt_common.config import settings

# RAG - lazy init
_chroma_client = None
_collection = None
_embed_model = None


def _get_rag():
    global _chroma_client, _collection, _embed_model
    if _collection is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from sentence_transformers import SentenceTransformer
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir, settings=ChromaSettings(anonymized_telemetry=False))
        _collection = _chroma_client.get_or_create_collection("ace_sections")
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _collection, _embed_model


def search_sections(query: str, top_k: int = 5) -> list[dict]:
    coll, model = _get_rag()
    emb = model.encode([query]).tolist()
    r = coll.query(query_embeddings=emb, n_results=top_k)
    out = []
    if r and r["ids"] and r["ids"][0]:
        for i, doc_id in enumerate(r["ids"][0]):
            meta = (r.get("metadatas") or [[]])[0]
            m = meta[i] if i < len(meta) else {}
            out.append({"id": int(doc_id), "title": m.get("title", ""), "title_path": m.get("title_path", ""), "publication_id": int(m.get("publication_id", 0)) or 0})
    return out


def generate_reasoning(source_type: str, summary: str, section_title: str, content: str) -> str:
    if settings.openai_api_key:
        try:
            import httpx
            r = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": "Explain in 2 sentences: what changed, how it affects the section, why update needed."}, {"role": "user", "content": f"Source: {summary}\nSection: {section_title}\n{content[:300]}"}],
                    "max_tokens": 200,
                },
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
    return f"Impact: {source_type} - {summary[:100]}. Section '{section_title}' may need revision."


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AI Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AnalyzeImpactRequest(BaseModel):
    source_type: str
    source_id: int


@app.post("/api/v1/analyze-impact")
async def analyze_impact(req: AnalyzeImpactRequest, db: AsyncSession = Depends(get_db)):
    if req.source_type == "case":
        r = await db.execute(select(LegalCase).where(LegalCase.id == req.source_id))
        obj = r.scalar_one_or_none()
        query = f"{obj.headnotes or ''} {obj.faceted_summary or ''}".strip() or obj.case_name if obj else ""
        summary = f"{obj.case_name} - {obj.court or ''}" if obj else ""
    elif req.source_type == "legislation":
        r = await db.execute(select(Legislation).where(Legislation.id == req.source_id))
        obj = r.scalar_one_or_none()
        query = f"{obj.title} {obj.summary or ''}".strip() if obj else ""
        summary = f"{obj.title} - {obj.effect_type or ''}" if obj else ""
    else:
        return {"impacts": []}
    if not obj or not obj.passed_p0:
        return {"impacts": []}

    hits = search_sections(query, top_k=settings.rag_top_k)
    impacts = []
    for h in hits:
        r = await db.execute(select(Section).where(Section.id == h["id"]))
        sec = r.scalar_one_or_none()
        if not sec:
            continue
        reasoning = generate_reasoning(req.source_type, summary, sec.title or sec.title_path, sec.content or "")
        impacts.append({
            "section_id": sec.id,
            "reasoning": reasoning,
            "relevance_score": 0.9,
        })
    return {"impacts": impacts}


@app.get("/healthcheck")
async def health():
    return {"status": "ok", "service": "ai_service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
