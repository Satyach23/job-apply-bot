"""
Agent package: LLM-powered document analysis pipeline.

The run_pipeline() function is the main entry point — it orchestrates
file parsing, LLM field extraction, and database storage.
"""

from app.agents.pipeline import run_pipeline

__all__ = ["run_pipeline"]
