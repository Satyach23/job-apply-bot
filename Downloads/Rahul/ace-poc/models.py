"""ACE POC - SQLAlchemy models."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TaskStatus(str, Enum):
    """Task lifecycle status."""

    NEW = "NEW"
    UPDATING = "UPDATING"
    PUBLISHED = "PUBLISHED"


class LegalCase(Base):
    """New case data (simplified)."""

    __tablename__ = "legal_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_name = Column(String(512), nullable=False)
    citation = Column(String(256))
    court = Column(String(256))
    decision_date = Column(DateTime)
    jurisdiction = Column(String(128))
    headnotes = Column(Text)
    faceted_summary = Column(Text)
    shepard_letters = Column(String(64))  # e.g. "O,W" for overruled, withdrawn
    created_at = Column(DateTime, default=datetime.utcnow)
    passed_p0 = Column(Integer, default=0)  # 0=no, 1=yes

    section_impacts = relationship("SectionImpact", back_populates="legal_case")


class Legislation(Base):
    """Legislation change (simplified)."""

    __tablename__ = "legislations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    citation = Column(String(256))
    effect_type = Column(String(64))  # amended, new, etc.
    effective_date = Column(DateTime)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    passed_p0 = Column(Integer, default=0)

    section_impacts = relationship("SectionImpact", back_populates="legislation")


class Publication(Base):
    """Publication (book) metadata."""

    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    jurisdiction = Column(String(128))
    practice_area = Column(String(128))

    sections = relationship("Section", back_populates="publication")


class Section(Base):
    """Book section (chunk of analytical content)."""

    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    title_path = Column(String(512))  # e.g. "Ch.5 > § 5.02"
    title = Column(String(256))
    content = Column(Text)
    citations = Column(Text)  # Comma-separated cited cases/statutes

    publication = relationship("Publication", back_populates="sections")
    impacts = relationship("SectionImpact", back_populates="section")


class SectionImpact(Base):
    """AI-generated impact: section X is impacted by case/law Y."""

    __tablename__ = "section_impacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    legal_case_id = Column(Integer, ForeignKey("legal_cases.id"))
    legislation_id = Column(Integer, ForeignKey("legislations.id"))
    reasoning = Column(Text)  # What, how, why
    relevance_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    section = relationship("Section", back_populates="impacts")
    legal_case = relationship("LegalCase", back_populates="section_impacts")
    legislation = relationship("Legislation", back_populates="section_impacts")


class Tracker(Base):
    """Tracker (links publications to monitoring)."""

    __tablename__ = "trackers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    publication_id = Column(Integer, ForeignKey("publications.id"))

    tasks = relationship("Task", back_populates="tracker")


class Task(Base):
    """Editor task: update section X because of case/law Y."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    title = Column(String(512))
    status = Column(String(32), default=TaskStatus.NEW.value)
    section_id = Column(Integer, ForeignKey("sections.id"))
    source_type = Column(String(32))  # "case" or "legislation"
    source_id = Column(Integer)  # legal_case_id or legislation_id
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    tracker = relationship("Tracker", back_populates="tasks")
