"""
RAG Agent — routes questions to SQLite and/or vector store and synthesises answers.

Routing:
  1. "metadata" — document structure, titles, section names, types, LMI IDs
     → search_metadata() (SQLite extracted_fields).
  2. "content" — what a section says, specific facts, legal guidance
     → search_content() (vector store).
  3. "both" — factual/law questions (e.g. "what does the law say about X")
     → search_metadata() and search_content(), then combine context for one answer.

If no results from the chosen source(s), no_info_found() is returned.
"""

from typing import Optional

from app.agents.llm_client import call_llm
from app.agents.tools import no_info_found, search_content, search_metadata

_CLASSIFY_PROMPT = """\
You are a routing agent. Classify the user's question into one of three categories:

1. "metadata" — the question is about document structure, titles, document types,
   section names, sub-section names, LMI IDs, or other document-level properties only.

2. "content" — the question asks only about the actual textual content: what a section says,
   specific facts, legal guidance, or body text. No need for document structure.

3. "both" — the question asks for factual or legal answers where both document structure
   and content are useful (e.g. "What does the law say about Part 36?", "Explain sanctions",
   "What are the requirements for a valid offer?"). Use both metadata and content to answer.

Respond with ONLY one word: metadata  OR  content  OR  both

Question: {question}"""

_ANSWER_PROMPT = """\
You are a helpful document assistant. Use the retrieved context below to answer
the user's question accurately and concisely. Give factual answers when the context
contains the information.
If the context does not contain enough information, say "No information found".

Context:
{context}

Question: {question}

Answer:"""


def answer_question(
    question: str,
    doc_id: Optional[int] = None,
) -> dict:
    """
    Route the question to SQLite and/or vector store, then synthesise one answer.
    For factual/law questions, both sources are queried and combined.
    """
    raw_type = call_llm(_CLASSIFY_PROMPT.format(question=question))
    raw_lower = raw_type.lower()
    if "both" in raw_lower:
        question_type = "both"
    elif "content" in raw_lower:
        question_type = "content"
    else:
        question_type = "metadata"

    context_parts = []
    sources = []
    used_metadata = False
    used_content = False

    # Metadata path (SQLite)
    if question_type in ("metadata", "both"):
        meta_results = search_metadata(question, doc_id)
        if meta_results:
            used_metadata = True
            for r in meta_results[:10]:
                line = (
                    f"Section: {r.get('section','')} | Sub-section: {r.get('sub_section','')} | "
                    f"Title: {r.get('title','')} | Type: {r.get('type','')} | "
                    f"LMI ID: {r.get('lmi_id','')} | File: {r.get('file_name','')}"
                )
                if r.get("section_text"):
                    line += f"\n  Text: {r.get('section_text','')[:500]}"
                context_parts.append(line)
            sources.extend([f"{r.get('section','')} — {r.get('title','')}" for r in meta_results[:5]])

    # Content path (vector store)
    if question_type in ("content", "both"):
        content_results = search_content(question, top_k=5)
        if content_results:
            used_content = True
            context_parts.append("\n\n--- Content (from documents) ---\n\n")
            context_parts.append("\n\n---\n\n".join(r["chunk_text"] for r in content_results))
            sources.extend([r["chunk_text"][:120] + "…" for r in content_results[:3]])

    if not context_parts:
        return {
            "answer": no_info_found(),
            "source_type": "none",
            "sources": [],
        }

    context = "\n".join(context_parts)
    answer = call_llm(_ANSWER_PROMPT.format(context=context, question=question))

    source_type = "both" if (used_metadata and used_content) else ("metadata" if used_metadata else "content")
    return {
        "answer": answer,
        "source_type": source_type,
        "sources": sources,
    }
