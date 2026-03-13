"""
Document analyzer agent — the core intelligence of the pipeline.

Uses the Gemini LLM to extract structured metadata fields from
parsed document text. This module contains NO regex and NO
hardcoded extraction logic. All field identification is performed
by the LLM via a carefully crafted prompt.

Output fields per document section:
  1. Section     — main section heading
  2. Sub-section — sub-heading within the section
  3. Title       — overall document title
  4. Type        — document type (Practice Note, Overview, etc.)
  5. LMI ID      — LexisNexis Metadata Identifier
"""

from app.agents.llm_client import call_llm_json
from app.models import ExtractedField, ParsedDocument

# -------------------------------------------------------------------
# Extraction prompt template
# -------------------------------------------------------------------
# The double braces {{ and }} are literal braces in the f-string
# that will appear as { and } in the final prompt sent to the LLM.
EXTRACTION_PROMPT = """You are a document analysis expert \
working with legal and regulatory documents from LexisNexis.

Analyze the following document content and extract structured \
metadata records.

For EACH distinct section or content block in the document, \
extract these five fields:

1. **Section**: The main/top-level section heading this content \
belongs to.
2. **Sub-section**: The sub-section or sub-heading within the \
main section. Use empty string if there is no sub-section.
3. **Title**: The title of the OVERALL document (same for every \
row — this is the document title, not the section title).
4. **Type**: The document type. Examples: "Practice Note", \
"Overview", "Guidance Note", "Legislation", "Case Analysis", \
"Regulatory Update". Infer from the content.
5. **LMI ID**: Any LexisNexis identifier found in the content. \
Look for: EXPERT metadata values, CITEIDs (e.g. CITEID_156491), \
normcite URNs, or any other unique document identifier. Use \
empty string if none found.

IMPORTANT RULES:
- Extract ALL sections present in the document — do not skip any
- The Title field should be the DOCUMENT-LEVEL title, consistent \
across all rows
- For LMI ID, prefer EXPERT metadata values if available, then \
CITEIDs, then normcite URNs
- Return ONLY valid JSON — no commentary, no markdown headers
- If a field has no value, use an empty string ""

Respond with a JSON array of objects in this exact format:
[
  {{
    "section": "Section Name Here",
    "sub_section": "",
    "title": "Document Title Here",
    "type": "Practice Note",
    "lmi_id": "12345"
  }}
]

--- DOCUMENT CONTENT START ---
{content}
--- DOCUMENT CONTENT END ---

Extract all sections as a JSON array:"""


def analyze_document(parsed: ParsedDocument) -> list[ExtractedField]:
    """
    Use the LLM to extract structured fields from a parsed document.

    Sends the parsed text content to Gemini with an extraction prompt
    that instructs it to identify every section and extract the five
    required output fields for each.

    Args:
        parsed: A ParsedDocument produced by one of the format parsers.

    Returns:
        A list of ExtractedField objects — one per document section.
        Returns a single error record if extraction fails.
    """
    # Handle parse errors — don't send broken content to the LLM
    if parsed.error:
        return [ExtractedField(
            section="Error",
            title=parsed.file_name,
            type="Parse Error",
            lmi_id=parsed.error,
        )]

    # Handle empty documents
    if not parsed.text or parsed.text.startswith("(No text"):
        return [ExtractedField(
            section="Error",
            title=parsed.file_name,
            type="Empty Document",
        )]

    # Build the prompt with the document content injected
    prompt = EXTRACTION_PROMPT.format(content=parsed.text)

    # Call the LLM and parse the JSON response
    result = call_llm_json(prompt)

    # Handle LLM failure (API error, invalid JSON, etc.)
    if result is None:
        return [ExtractedField(
            section="Error",
            title=parsed.file_name,
            type="LLM extraction failed",
            lmi_id="Check API key and try again",
        )]

    # Convert raw JSON records into typed ExtractedField objects
    fields: list[ExtractedField] = []
    records = result if isinstance(result, list) else [result]

    for record in records:
        if not isinstance(record, dict):
            continue
        fields.append(ExtractedField(
            section=str(record.get("section", "")),
            sub_section=str(record.get("sub_section", "")),
            title=str(record.get("title", "")),
            type=str(record.get("type", "")),
            lmi_id=str(record.get("lmi_id", "")),
            section_text=str(record.get("section_text", "")),
        ))

    # Fallback if no valid records were extracted
    if not fields:
        return [ExtractedField(
            section="No sections found",
            title=parsed.file_name,
            type="Unknown",
        )]

    return fields
