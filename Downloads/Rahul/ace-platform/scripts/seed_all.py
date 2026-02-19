"""Seed database and RAG for all services."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lt_common"))

from lt_common.database import async_session, init_db
from lt_common.database.models import Publication, Section, Tracker


async def seed():
    await init_db()
    async with async_session() as session:
        from sqlalchemy import select
        r = await session.execute(select(Publication).limit(1))
        if r.scalar_one_or_none():
            print("Already seeded")
            return

        pub = Publication(name="Federal Employment Law Treatise", jurisdiction="US Federal", practice_area="Employment Law")
        session.add(pub)
        await session.flush()

        sections_data = [
            {"title_path": "Ch.5 > § 5.01", "title": "Introduction to Wrongful Termination", "content": "Wrongful termination claims arise when an employee is dismissed in violation of law or public policy."},
            {"title_path": "Ch.5 > § 5.02", "title": "At-Will Employment Doctrine", "content": "The at-will doctrine permits employers to terminate employees for any reason or no reason."},
            {"title_path": "Ch.5 > § 5.03", "title": "Retaliation and Whistleblower Protections", "content": "Employees who report violations are protected under whistleblower laws."},
            {"title_path": "Ch.7 > § 7.01", "title": "ADA Reasonable Accommodation", "content": "The ADA requires employers to provide reasonable accommodations for qualified individuals with disabilities."},
        ]
        sections = []
        for s in sections_data:
            sec = Section(publication_id=pub.id, title_path=s["title_path"], title=s["title"], content=s["content"])
            session.add(sec)
            await session.flush()
            sections.append({"id": sec.id, "title": sec.title, "content": sec.content, "title_path": sec.title_path, "publication_id": pub.id})

        session.add(Tracker(name=f"Tracker-{pub.name}", publication_id=pub.id))
        await session.commit()

        # Add to Chroma
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from sentence_transformers import SentenceTransformer
            import os
            base = Path("chroma_db")
            base.mkdir(exist_ok=True)
            client = chromadb.PersistentClient(path=str(base), settings=ChromaSettings(anonymized_telemetry=False))
            coll = client.get_or_create_collection("ace_sections")
            model = SentenceTransformer("all-MiniLM-L6-v2")
            for s in sections:
                text = f"{s['title']} {s['content']}"[:2000]
                emb = model.encode([text]).tolist()
                coll.upsert(ids=[str(s["id"])], embeddings=emb, metadatas=[{"title": s["title"], "title_path": s["title_path"], "publication_id": str(s["publication_id"])}])
            print("RAG index updated")
        except Exception as e:
            print(f"RAG seed skip: {e}")
    print("Seed complete")


if __name__ == "__main__":
    asyncio.run(seed())
