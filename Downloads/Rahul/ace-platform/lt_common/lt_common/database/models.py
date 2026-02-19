"""lt_common - SQLAlchemy models."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    NEW = "NEW"
    UPDATING = "UPDATING"
    PUBLISHED = "PUBLISHED"


class LegalCase(Base):
    __tablename__ = "legal_cases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    case_name = Column(String(512), nullable=False)
    citation = Column(String(256))
    court = Column(String(256))
    decision_date = Column(DateTime)
    jurisdiction = Column(String(128))
    headnotes = Column(Text)
    faceted_summary = Column(Text)
    shepard_letters = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    passed_p0 = Column(Integer, default=0)
    section_impacts = relationship("SectionImpact", back_populates="legal_case")


class Legislation(Base):
    __tablename__ = "legislations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False)
    citation = Column(String(256))
    effect_type = Column(String(64))
    effective_date = Column(DateTime)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    passed_p0 = Column(Integer, default=0)
    section_impacts = relationship("SectionImpact", back_populates="legislation")


class Publication(Base):
    __tablename__ = "publications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    jurisdiction = Column(String(128))
    practice_area = Column(String(128))
    sections = relationship("Section", back_populates="publication")


class Section(Base):
    __tablename__ = "sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    publication_id = Column(Integer, ForeignKey("publications.id"), nullable=False)
    title_path = Column(String(512))
    title = Column(String(256))
    content = Column(Text)
    citations = Column(Text)
    publication = relationship("Publication", back_populates="sections")
    impacts = relationship("SectionImpact", back_populates="section")


class SectionImpact(Base):
    __tablename__ = "section_impacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    legal_case_id = Column(Integer, ForeignKey("legal_cases.id"))
    legislation_id = Column(Integer, ForeignKey("legislations.id"))
    reasoning = Column(Text)
    relevance_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    section = relationship("Section", back_populates="impacts")
    legal_case = relationship("LegalCase", back_populates="section_impacts")
    legislation = relationship("Legislation", back_populates="section_impacts")


class Tracker(Base):
    __tablename__ = "trackers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    publication_id = Column(Integer, ForeignKey("publications.id"))
    tasks = relationship("Task", back_populates="tracker")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    title = Column(String(512))
    status = Column(String(32), default=TaskStatus.NEW.value)
    section_id = Column(Integer, ForeignKey("sections.id"))
    source_type = Column(String(32))
    source_id = Column(Integer)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    tracker = relationship("Tracker", back_populates="tasks")


class RepositoryObject(Base):
    """Commentary repository - object hierarchy / metadata."""
    __tablename__ = "repository_objects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    obj_type = Column(String(64))
    title = Column(String(256))
    path = Column(String(512))
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
