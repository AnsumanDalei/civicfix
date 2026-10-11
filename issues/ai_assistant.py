
"""Local rule-based assistance for CivicFix reports.
No paid API or external AI service is required.
"""

import re
from difflib import SequenceMatcher

from .models import CATEGORY_CHOICES


def assist_with_issue(action, description):
    """Return a local suggestion for a civic issue description."""
    if action not in {"improve", "category", "summary"}:
        raise ValueError("Unsupported assistance action.")

    text = re.sub(r"\s+", " ", description).strip()
    if not text:
        raise ValueError("Description cannot be empty.")

    
    if action == "improve":
        text = re.sub(r"\s+", " ", description).strip()
        text = text[0].upper() + text[1:]

        # Common informal phrases -> clearer civic-report wording.
        replacements = [
            (r"\broad is very bad\b", "The road is in poor condition"),
            (r"\bpotholes?\b", "potholes"),
            (r"\bmany cars problem\b", "causing problems for vehicles"),
            (r"\bgarbage\b", "accumulated waste"),
            (r"\bstreet ?lights? not working\b", "streetlights are not working"),
            (r"\bwater leakage\b", "water is leaking"),
            (r"\bdrain is blocked\b", "the drain is blocked"),
        ]

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        if text[-1] not in ".!?":
            text += "."
        return text


    if action == "summary":
        # Use the first sentence as a simple extractive summary.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        summary = sentences[0].strip()
        if len(summary) > 180:
            summary = summary[:177].rsplit(" ", 1)[0] + "..."
        return summary

    if action == "category":
        categories = {key: label for key, label in CATEGORY_CHOICES}
        keywords = {
            "hazard": (
                "danger", "unsafe", "accident", "exposed wire",
                "fallen tree", "blocked road", "fire"
            ),
            "sanitation": (
                "garbage", "trash", "waste", "dirty", "rubbish",
                "drain smell", "litter", "sewage"
            ),
            "infrastructure": (
                "pothole", "road", "streetlight", "street light",
                "water leak", "broken pipe", "footpath", "sidewalk",
                "drain", "pavement", "bridge"
            ),
        }

        lowered = text.lower()
        scores = {
            category: sum(
                1 for keyword in words if keyword in lowered
            )
            for category, words in keywords.items()
            if category in categories
        }

        if not scores or max(scores.values(), default=0) == 0:
            return "other" if "other" in categories else next(iter(categories))

        return max(scores, key=scores.get)

    raise ValueError("Unsupported assistance action.")


def text_similarity(first, second):
    """Return a simple similarity score between two text strings."""
    first = re.sub(r"\s+", " ", first.lower()).strip()
    second = re.sub(r"\s+", " ", second.lower()).strip()
    if not first or not second:
        return 0.0
    return SequenceMatcher(None, first, second).ratio()
