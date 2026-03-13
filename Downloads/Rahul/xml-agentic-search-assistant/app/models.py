"""
Pydantic data models for the ACP Document Analyzer.

Defines the schema for:
  - ParsedDocument: intermediate result after file parsing (before LLM)
  - ExtractedField: a single row of extracted metadata (the five output fields)
  - DocumentRecord: a fully processed document with all its extracted fields

These models enforce type safety and provide clear contracts between
the parser layer, the LLM agent layer, and the storage layer.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    """
    Intermediate representation produced by a format-specific parser.

    Contains the raw text content and structural metadata extracted
    from the file. This is the input to the LLM analyzer agent.
    """
    file_path: str = Field(description="Absolute path to the source file")
    file_name: str = Field(description="Original file name (e.g. 'FS Doc 1.xml')")
    format: str = Field(description="File format identifier (xml, pdf, docx, rtf)")
    text: str = Field(default="", description="Extracted plain-text content of the document")
    metadata: dict = Field(default_factory=dict, description="Parser-specific structural metadata")
    error: Optional[str] = Field(default=None, description="Error message if parsing failed")


class ExtractedField(BaseModel):
    """
    A single row of extracted metadata from a document section.

    Section, Sub-section, Title, Type, LMI ID; section_text is body text
    (from XML parser or left empty when from LLM-only).
    """
    section: str = Field(default="", description="Main section heading")
    sub_section: str = Field(default="", description="Sub-section heading")
    title: str = Field(default="", description="Document title")
    type: str = Field(default="", description="Document/content type")
    lmi_id: str = Field(default="", description="LexisNexis Metadata Identifier")
    section_text: str = Field(default="", description="Section body text (from XML parser)")


class DocumentRecord(BaseModel):
    """
    Complete record for a processed document.

    Combines file metadata with the list of extracted fields.
    Used as the return type from the processing pipeline.
    """
    id: Optional[int] = None
    file_name: str = ""
    file_path: str = ""
    format: str = ""
    content_preview: str = ""
    extracted_fields: list[ExtractedField] = []
    raw_llm_response: str = ""
    created_at: Optional[str] = None
