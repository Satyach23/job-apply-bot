"""
Text chunking — splits parsed document text into overlapping chunks
for vector embedding and semantic search.
"""


def chunk_document(text: str, chunk_size: int = 400, overlap: int = 1) -> list[str]:
    """
    Split text into chunks suitable for embedding.

    Splits on double newlines (paragraph boundaries) first,
    then merges small paragraphs until chunk_size is reached.
    The `overlap` parameter keeps the last N paragraphs from
    the previous chunk to preserve context across boundaries.

    Args:
        text: Plain text to chunk.
        chunk_size: Target max characters per chunk.
        overlap: Number of paragraphs to carry over between chunks.

    Returns:
        List of text chunks. Returns [text[:chunk_size]] if no
        paragraph breaks are found.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text[:chunk_size]] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > chunk_size and current:
            chunks.append("\n\n".join(current))
            # Keep last `overlap` paragraphs for context continuity
            current = current[-overlap:] if overlap > 0 else []
            current_len = sum(len(p) for p in current)
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks
