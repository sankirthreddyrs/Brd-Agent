"""LLM client, prompt templates, and structured schemas package."""

from .llm_client import LLMClient, GeminiClient
from .prompts import (
    build_extraction_prompt,
    build_gap_analysis_prompt,
    build_question_text_prompt,
)
from .schemas import (
    CandidateIssue,
    ExtractionResult,
    GapAnalysisResult,
    QuestionDraft,
)

__all__ = [
    "LLMClient",
    "GeminiClient",
    "build_extraction_prompt",
    "build_gap_analysis_prompt",
    "build_question_text_prompt",
    "ExtractionResult",
    "GapAnalysisResult",
    "CandidateIssue",
    "QuestionDraft",
]
