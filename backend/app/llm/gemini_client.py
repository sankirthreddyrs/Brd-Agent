"""Backward-compatibility module aliasing LLMClient as GeminiClient."""

from .llm_client import (
    LLMClient,
    GeminiClient,
    clean_schema_for_gemini,
    SYSTEM_PROMPT,
)

__all__ = [
    "LLMClient",
    "GeminiClient",
    "clean_schema_for_gemini",
    "SYSTEM_PROMPT",
]
