"""Phase 4 — Groq LLM ranking and explanations."""

from phase_4.config import GroqSettings, get_groq_settings
from phase_4.llm import DEFAULT_FALLBACK_EXPLANATION, recommend_with_llm

__all__ = [
    "DEFAULT_FALLBACK_EXPLANATION",
    "GroqSettings",
    "get_groq_settings",
    "recommend_with_llm",
]
