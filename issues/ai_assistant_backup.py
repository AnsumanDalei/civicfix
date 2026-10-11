"""Small, optional OpenAI helper for the report form."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .models import CATEGORY_CHOICES


class AIAssistantUnavailable(Exception):
    """Raised when AI is not configured or the provider cannot respond."""


ACTION_INSTRUCTIONS = {
    "improve": (
        "Rewrite this civic issue report as one clear, concise sentence. "
        "Preserve the reporter's meaning and do not add facts. Return only the rewritten sentence."
    ),
    "category": (
        "Choose the closest category for this civic issue. Return exactly one category key from: "
        "hazard, sanitation, infrastructure, other. Return only the key."
    ),
    "summary": "Summarize this civic issue in one short sentence. Do not add facts. Return only the sentence.",
}


def assist_with_issue(action, description):
    """Return a short suggestion. No description or account data is stored here."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key or action not in ACTION_INSTRUCTIONS:
        raise AIAssistantUnavailable

    body = json.dumps({
        "model": getattr(settings, "OPENAI_MODEL", "").strip() or "gpt-5-mini",
        "instructions": ACTION_INSTRUCTIONS[action],
        "input": description,
        "max_output_tokens": 120,
        "store": False,
    }).encode("utf-8")
    request = Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        print("OpenAI HTTP status:", exc.code)
        try:
            error_data = json.loads(exc.read().decode("utf-8"))
            print("OpenAI error:", error_data.get("error", {}).get("message", "Unknown API error"))
            print("OpenAI error code:", error_data.get("error", {}).get("code", "Unknown"))
        except (ValueError, OSError):
            print("OpenAI returned an unreadable error response.")
        raise AIAssistantUnavailable from None

    except (URLError, TimeoutError, OSError, ValueError) as exc:
        print("OpenAI connection/response error:", type(exc).__name__)
        raise AIAssistantUnavailable from None
    text_parts = []
    try:
        for output in result.get("output", []):
            for item in output.get("content", []):
                if item.get("type") == "output_text" and item.get("text"):
                    text_parts.append(item["text"])
    except (AttributeError, TypeError):
        raise AIAssistantUnavailable from None
    suggestion = " ".join(text_parts).strip().strip('"')
    if not suggestion or len(suggestion) > 500:
        raise AIAssistantUnavailable

    if action == "category":
        valid_categories = {key for key, _label in CATEGORY_CHOICES}
        suggestion = suggestion.strip().lower()
        if suggestion not in valid_categories:
            raise AIAssistantUnavailable
    return suggestion
