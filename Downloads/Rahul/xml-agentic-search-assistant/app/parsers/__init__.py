"""
Document parser package.

Provides a unified interface for parsing multiple document formats
(XML, PDF, DOCX, RTF). The parse_document() function is the single
entry point — it auto-detects the format and delegates to the
appropriate parser.
"""

from app.parsers.registry import parse_document, list_supported_formats

__all__ = ["parse_document", "list_supported_formats"]
