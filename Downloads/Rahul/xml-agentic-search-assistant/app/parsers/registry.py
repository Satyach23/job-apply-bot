"""
Parser registry: maps file extensions to their parser implementations.

Uses a registry pattern for extensibility — to add support for a new
document format:
  1. Create a parser class that inherits from BaseParser
  2. Add an instance to the _PARSERS list below
  3. Add the extension to SUPPORTED_EXTENSIONS in config.py

The parse_document() function is the single entry point for all
format-specific parsing. It auto-selects the right parser based on
the file extension.
"""

from pathlib import Path
from typing import Optional

from app.config import SUPPORTED_EXTENSIONS
from app.models import ParsedDocument
from app.parsers.base import BaseParser
from app.parsers.xml_parser import XMLParser

# ---------------------------------------------------------------------------
# Registry: all available parsers, instantiated once at module load
# ---------------------------------------------------------------------------
_PARSERS: list[BaseParser] = [XMLParser()]


def get_parser(file_path: str) -> Optional[BaseParser]:
    """
    Find the parser that can handle the given file's extension.

    Iterates through registered parsers and returns the first match.
    Returns None if no parser supports the file type.
    """
    for parser in _PARSERS:
        if parser.can_handle(file_path):
            return parser
    return None


def parse_document(file_path: str) -> ParsedDocument:
    """
    Parse a document file using the appropriate format-specific parser.

    This is the main entry point for the parsing layer. It:
      1. Validates that the file exists
      2. Checks that the extension is supported
      3. Delegates to the matching parser

    Args:
        file_path: Path to the document file.

    Returns:
        ParsedDocument with extracted text, or with error set on failure.
    """
    path = Path(file_path).resolve()

    # Validate: file must exist and be a regular file
    if not path.exists() or not path.is_file():
        return ParsedDocument(
            file_path=str(path),
            file_name=path.name,
            format="unknown",
            error=f"File not found: {path}",
        )

    # Validate: file extension must be in the supported set
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return ParsedDocument(
            file_path=str(path),
            file_name=path.name,
            format=suffix.lstrip("."),
            error=f"Unsupported format: '{suffix}'. Supported: {supported}",
        )

    # Find the registered parser for this extension
    parser = get_parser(str(path))
    if not parser:
        return ParsedDocument(
            file_path=str(path),
            file_name=path.name,
            format=suffix.lstrip("."),
            error=f"No parser registered for extension: {suffix}",
        )

    # Execute the parser and return the result
    return parser.parse(str(path))


def list_supported_formats() -> list[dict[str, str]]:
    """
    Return metadata about all registered parsers and their extensions.

    Useful for displaying supported formats in the UI.
    """
    formats = []
    for parser in _PARSERS:
        for ext in parser.supported_extensions:
            formats.append({
                "extension": ext,
                "parser": parser.__class__.__name__,
            })
    return formats
