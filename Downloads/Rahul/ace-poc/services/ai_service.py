"""ACE POC - Impact reasoning (mock or OpenAI)."""
from __future__ import annotations

import json
from typing import Any

from config import settings


def generate_impact_reasoning(
    source_type: str,
    source_summary: str,
    section_title: str,
    section_content: str,
) -> str:
    """
    Generate impact reasoning: What changed, how it affects the section, why update needed.
    Uses OpenAI if API key set, else mock.
    """
    if settings.openai_api_key:
        return _openai_reasoning(
            source_type, source_summary, section_title, section_content
        )
    return _mock_reasoning(source_type, source_summary, section_title, section_content)


def _mock_reasoning(
    source_type: str,
    source_summary: str,
    section_title: str,
    section_content: str,
) -> str:
    """Mock reasoning for demo without API key."""
    return json.dumps({
        "what": f"New {source_type}: {source_summary[:200]}...",
        "how": f"Affects section '{section_title}' - content may need revision to reflect new legal standard.",
        "why": "Current section may cite outdated precedent or statute; update needed for accuracy.",
    }, indent=2)


def _openai_reasoning(
    source_type: str,
    source_summary: str,
    section_title: str,
    section_content: str,
) -> str:
    """Real reasoning via OpenAI (if key configured)."""
    try:
        import httpx

        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a legal analyst. In 2-3 sentences, explain: (1) WHAT changed in the new case/law, (2) HOW it affects the given section, (3) WHY an update is needed. Be concise.",
                    },
                    {
                        "role": "user",
                        "content": f"Source type: {source_type}\nSource: {source_summary}\n\nSection: {section_title}\nContent: {section_content[:500]}...",
                    },
                ],
                "max_tokens": 256,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() or _mock_reasoning(
            source_type, source_summary, section_title, section_content
        )
    except Exception:
        return _mock_reasoning(
            source_type, source_summary, section_title, section_content
        )
