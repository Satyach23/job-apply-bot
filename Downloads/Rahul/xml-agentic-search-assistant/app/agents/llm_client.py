"""
LLM client — unified interface for AI Gateway and Google Gemini.

Supports two backends:
  1. LexisNexis AI Gateway (LiteLLM proxy, OpenAI-compatible)
     — Uses AI_GATEWAY_ENDPOINT + AI_GATEWAY_TENANT_KEY
     — Requires VPN access to the LexisNexis network
  2. Direct Google Gemini API (fallback for local development)
     — Uses GOOGLE_API_KEY

The gateway is tried first. If not configured or unreachable,
falls back to direct Gemini. All other modules call functions
here instead of importing any LLM SDK directly.
"""

import json

from openai import OpenAI

from app.config import (
    AI_GATEWAY_ENDPOINT,
    AI_GATEWAY_TENANT_KEY,
    GOOGLE_API_KEY,
    LLM_MAX_CHARS,
    LLM_MODEL,
)

# -------------------------------------------------------------------
# Module-level clients — created lazily on first use
# -------------------------------------------------------------------
_gateway_client = None
_gemini_client = None


def _get_gateway_client() -> OpenAI | None:
    """
    Create an OpenAI-compatible client pointing at the AI Gateway.

    Returns None if gateway is not configured (no endpoint/key).
    """
    global _gateway_client
    if _gateway_client is not None:
        return _gateway_client

    if not AI_GATEWAY_ENDPOINT or not AI_GATEWAY_TENANT_KEY:
        return None

    # LiteLLM gateway is OpenAI-compatible — use OpenAI SDK
    # with the gateway URL as base_url
    endpoint = AI_GATEWAY_ENDPOINT.rstrip("/")
    _gateway_client = OpenAI(
        api_key=AI_GATEWAY_TENANT_KEY,
        base_url=endpoint,
    )
    return _gateway_client


def _get_gemini_client() -> OpenAI | None:
    """
    Create an OpenAI-compatible client for direct Google Gemini.

    Google's Gemini API exposes an OpenAI-compatible endpoint at
    https://generativelanguage.googleapis.com/v1beta/openai/
    """
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    if not GOOGLE_API_KEY:
        return None

    _gemini_client = OpenAI(
        api_key=GOOGLE_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    return _gemini_client


def _get_client() -> OpenAI:
    """
    Get the best available LLM client.

    Priority:
      1. AI Gateway (if endpoint + key configured)
      2. Direct Gemini (if GOOGLE_API_KEY configured)
      3. Raise ValueError if nothing is configured

    Returns:
        An OpenAI-compatible client ready to make requests.
    """
    client = _get_gateway_client()
    if client is not None:
        return client

    client = _get_gemini_client()
    if client is not None:
        return client

    raise ValueError(
        "No LLM backend configured. Set either "
        "AI_GATEWAY_ENDPOINT + AI_GATEWAY_TENANT_KEY "
        "(for the LN AI Gateway) or GOOGLE_API_KEY "
        "(for direct Gemini) in your .env file."
    )


def call_llm(
    prompt: str,
    max_chars: int = LLM_MAX_CHARS,
) -> str:
    """
    Send a text prompt to the LLM and return the response.

    Tries the AI Gateway first, falls back to direct Gemini.
    Uses the OpenAI chat completions API format, which both
    the LiteLLM gateway and Gemini's OpenAI endpoint support.

    Args:
        prompt: The full prompt text to send.
        max_chars: Maximum prompt length before truncation.

    Returns:
        The model's response text, or an error message string.
    """
    # Truncate very long prompts to stay within token limits
    if len(prompt) > max_chars:
        prompt = (
            prompt[:max_chars]
            + "\n\n[Content truncated due to length]"
        )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        return (content or "").strip()
    except Exception as e:
        return f"LLM Error: {e}"


def call_llm_json(
    prompt: str,
    max_chars: int = LLM_MAX_CHARS,
) -> dict | list | None:
    """
    Send a prompt and parse the response as JSON.

    The prompt should instruct the LLM to respond with valid JSON.
    Handles responses wrapped in markdown code blocks
    (```json ... ```) by stripping the wrappers before parsing.

    Args:
        prompt: Prompt text (should request JSON output).
        max_chars: Maximum prompt length before truncation.

    Returns:
        Parsed JSON as dict or list, or None if parsing fails.
    """
    raw = call_llm(prompt, max_chars)

    # If the LLM returned an error, don't try to parse it
    if raw.startswith("LLM Error:"):
        return None

    # Strip markdown code-block wrappers if the LLM added them
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening ``` line (may include language tag)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing ``` line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Not valid JSON — caller handles the failure
        return None
