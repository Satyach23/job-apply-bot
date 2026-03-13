"""
XML document parser for LexisNexis KnowHow and generic XML files.

Extracts:
  1. Structured storage: title, section, sub_section, section_text (from XML)
     stored in metadata["structured_sections"] for SQLite.
  2. Full plain text for chunking and vector embedding.

Handles:
  - Simple XML: <document><title>...</title><section><heading>...</heading><para>...</para></section>
  - LexisNexis KnowHow: kh:document-title, tr:secmain, core:title, para, etc.
  - Namespaced XML (strips namespace URIs for tag matching).
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from app.models import ParsedDocument
from app.parsers.base import BaseParser


def _strip_ns(tag: str) -> str:
    """Remove namespace prefix from XML tag. '{uri}local' -> 'local'."""
    if "}" in tag:
        return tag.split("}")[-1]
    return tag


def _elem_text(e: ET.Element) -> str:
    """Recursively collect all text inside an element."""
    parts = [e.text or ""]
    for child in e:
        parts.append(_elem_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split())


def _find_sections_and_title(root: ET.Element) -> tuple[str, list[dict]]:
    """
    Extract document title and list of {title, section, sub_section, section_text}.
    Works with simple <document><title>...</title><section><heading>...</heading><para>...</para>
    and LexisNexis-style (document-title, secmain, heading, para).
    """
    doc_title = ""
    structured: list[dict] = []

    # Common tag names (no namespace)
    TITLE_TAGS = ("document-title", "title")
    SECTION_TAGS = ("section", "secmain", "sec")
    HEADING_TAGS = ("heading", "heading-text", "title", "core:title")
    BODY_TAGS = ("para", "p", "body", "content", "text")

    def find_title(elem: ET.Element, depth: int) -> None:
        nonlocal doc_title
        tag = _strip_ns(elem.tag)
        if not doc_title and tag in TITLE_TAGS and depth <= 3:
            t = _elem_text(elem).strip()
            if t:
                doc_title = t
        for c in elem:
            find_title(c, depth + 1)

    def collect_sections(parent: ET.Element, path: list[str]) -> None:
        tag = _strip_ns(parent.tag)
        if tag in SECTION_TAGS:
            section_heading = ""
            sub_heading = ""
            body_parts: list[str] = []
            for c in parent:
                ct = _strip_ns(c.tag)
                if ct in HEADING_TAGS:
                    if not section_heading:
                        section_heading = _elem_text(c).strip()
                    else:
                        sub_heading = _elem_text(c).strip()
                elif ct in BODY_TAGS or ct == "content" or "para" in ct or "text" in ct:
                    body_parts.append(_elem_text(c).strip())
                else:
                    collect_sections(c, path + [section_heading or tag])
            text = " ".join(p for p in body_parts if p).strip()
            if section_heading or text:
                structured.append({
                    "title": doc_title,
                    "section": section_heading,
                    "sub_section": sub_heading,
                    "section_text": text or "",
                })
        else:
            for c in parent:
                collect_sections(c, path)

    find_title(root, 0)
    collect_sections(root, [])

    # Fallback: simple <document><title>...</title><section id="x"><heading>...</heading><para>...</para>
    if not structured and doc_title:
        for elem in root.iter():
            if _strip_ns(elem.tag) == "section":
                head = ""
                paras: list[str] = []
                for c in elem:
                    t = _strip_ns(c.tag)
                    if t in ("heading", "title", "heading-text"):
                        head = _elem_text(c).strip()
                    else:
                        paras.append(_elem_text(c).strip())
                structured.append({
                    "title": doc_title,
                    "section": head,
                    "sub_section": "",
                    "section_text": " ".join(p for p in paras if p),
                })

    return doc_title, structured


def _walk_element(element: ET.Element, parts: list[str], depth: int) -> None:
    """Recursively collect full plain text with optional tag context."""
    tag = _strip_ns(element.tag)
    if element.text and element.text.strip():
        if depth <= 3:
            parts.append(f"[{tag}] {element.text.strip()}")
        else:
            parts.append(element.text.strip())
    for child in element:
        _walk_element(child, parts, depth + 1)
    if element.tail and element.tail.strip():
        parts.append(element.tail.strip())


class XMLParser(BaseParser):
    """
    Parser for XML documents.
    Produces full text and structured title/section/subsection/section_text for SQLite.
    """

    supported_extensions = [".xml"]

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return self._build_error(file_path, f"Failed to read file: {e}")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            return self._build_error(file_path, f"XML parse error: {e}")

        # Structured extraction: title, section, sub_section, section_text
        doc_title, structured_sections = _find_sections_and_title(root)

        # Full plain text for chunking and vector store
        text_parts: list[str] = []
        _walk_element(root, text_parts, depth=0)
        text = "\n".join(text_parts).strip()
        if not text:
            text = "(No text content extracted from XML)"

        metadata: dict = {"root_tag": _strip_ns(root.tag)}
        if structured_sections:
            metadata["structured_sections"] = structured_sections
            metadata["document_title"] = doc_title

        return self._build_result(
            file_path=file_path,
            text=text,
            fmt="xml",
            metadata=metadata,
        )
