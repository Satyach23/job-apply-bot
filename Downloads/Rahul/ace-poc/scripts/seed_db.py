"""ACE POC - Seed database and RAG with mock data."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import async_session, init_db
from models import Publication, Section, Tracker
from services.rag_service import add_sections, clear_collection


async def seed():
    await init_db()

    async with async_session() as session:
        # Check if already seeded
        from sqlalchemy import select

        r = await session.execute(select(Publication).limit(1))
        if r.scalar_one_or_none():
            print("Data already seeded. Skip or delete ace_poc.db to reseed.")
            return

        # Publication
        pub = Publication(
            name="Federal Employment Law Treatise",
            jurisdiction="US Federal",
            practice_area="Employment Law",
        )
        session.add(pub)
        await session.flush()

        # Sections (analytical content)
        sections_data = [
            {
                "title_path": "Ch.5 > § 5.01",
                "title": "Introduction to Wrongful Termination",
                "content": "Wrongful termination claims arise when an employee is dismissed in violation of law or public policy. Key statutes include Title VII, ADA, and state common law doctrines. Courts have increasingly recognized exceptions to at-will employment.",
                "citations": "Smith v. Acme Corp, 42 US 100; Jones v. State",
            },
            {
                "title_path": "Ch.5 > § 5.02",
                "title": "At-Will Employment Doctrine",
                "content": "The at-will doctrine permits employers to terminate employees for any reason or no reason. Exceptions include retaliation, discrimination, breach of implied contract, and violation of public policy. Recent circuit court decisions have expanded public policy protections.",
                "citations": "Johnson v. Federal Circuit; Greene v. Ohio",
            },
            {
                "title_path": "Ch.5 > § 5.03",
                "title": "Retaliation and Whistleblower Protections",
                "content": "Employees who report violations are protected under whistleblower laws. Sarbanes-Oxley, Dodd-Frank, and state analogues provide remedies. Supreme Court has clarified the causation standard for retaliation claims.",
                "citations": "Thompson v. North Corp; Williams v. SEC",
            },
            {
                "title_path": "Ch.7 > § 7.01",
                "title": "ADA Reasonable Accommodation",
                "content": "The ADA requires employers to provide reasonable accommodations for qualified individuals with disabilities. Interactive process, undue hardship defense, and remote work accommodations have been subject to recent litigation.",
                "citations": "Brown v. Retail Co; ADA Amendments Act",
            },
            {
                "title_path": "Ch.7 > § 7.02",
                "title": "Family and Medical Leave",
                "content": "FMLA provides 12 weeks unpaid leave for qualifying reasons. State laws may provide additional leave. Court decisions have addressed intermittent leave, eligibility, and reinstatement rights.",
                "citations": "Davis v. Manufacturing Inc; FMLA Regulations",
            },
        ]

        sections = []
        for s in sections_data:
            sec = Section(
                publication_id=pub.id,
                title_path=s["title_path"],
                title=s["title"],
                content=s["content"],
                citations=s.get("citations", ""),
            )
            session.add(sec)
            await session.flush()
            sections.append({
                "id": sec.id,
                "title": sec.title,
                "content": sec.content,
                "title_path": sec.title_path,
                "publication_id": pub.id,
            })

        # Tracker
        tracker = Tracker(name=f"Tracker-{pub.name}", publication_id=pub.id)
        session.add(tracker)

        await session.commit()

        # Add sections to RAG (ChromaDB)
        clear_collection()
        add_sections(sections)
        print("RAG index updated.")

    print("Seed complete. Publications, sections, and RAG index ready.")


if __name__ == "__main__":
    asyncio.run(seed())
