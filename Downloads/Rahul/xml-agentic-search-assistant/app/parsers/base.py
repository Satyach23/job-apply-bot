"""
Abstract base class for all document parsers.

Every format-specific parser (XML, PDF, DOCX, RTF) must inherit from
BaseParser and implement the parse() method. This ensures a consistent
interface across all formats and makes adding new parsers straightforward.

To add a new format:
  1. Create a new file (e.g. csv_parser.py)
  2. Subclass BaseParser, set supported_extensions, implement parse()
  3. Register the parser in parsers/registry.py
"""

from abc import ABC, abstractmethod
from pathlib import Path

from app.models import ParsedDocument


class BaseParser(ABC):
    """
    Abstract base class for format-specific document parsers.

    Provides:
      - can_handle(): checks if a file's extension matches this parser
      - parse(): abstract method that subclasses must implement
      - _build_result(): helper to construct a successful ParsedDocument
      - _build_error(): helper to construct an error ParsedDocument
    """

    # Subclasses MUST override this with the extensions they support
    # Example: [".xml"] or [".pdf"]
    supported_extensions: list[str] = []

    def can_handle(self, file_path: str) -> bool:
        """
        Check whether this parser supports the given file's extension.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if this parser handles the file's extension.
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in self.supported_extensions

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse the file at the given path and extract its text content.

        Must be implemented by every format-specific parser subclass.
        Should never raise exceptions — return _build_error() instead.

        Args:
            file_path: Absolute path to the file to parse.

        Returns:
            A ParsedDocument with extracted text, or with error set on failure.
        """
        ...

    def _build_result(
        self,
        file_path: str,
        text: str,
        fmt: str,
        metadata: dict | None = None,
    ) -> ParsedDocument:
        """
        Construct a successful ParsedDocument from common fields.

        This helper avoids repeating the same construction logic in
        every parser's parse() method.
        """
        path = Path(file_path)
        return ParsedDocument(
            file_path=str(path),
            file_name=path.name,
            format=fmt,
            text=text,
            metadata=metadata or {},
        )

    def _build_error(self, file_path: str, error_msg: str) -> ParsedDocument:
        """
        Construct a ParsedDocument that represents a parsing failure.

        The error field will be set, and text will be empty.
        """
        path = Path(file_path)
        return ParsedDocument(
            file_path=str(path),
            file_name=path.name,
            format=path.suffix.lstrip("."),
            error=error_msg,
        )
