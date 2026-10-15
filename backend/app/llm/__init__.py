"""LLM client, prompt templates, and structured schemas package."""

from .gemini_client import GeminiClient
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
    "GeminiClient",
    "build_extraction_prompt",
    "build_gap_analysis_prompt",
    "build_question_text_prompt",
    "ExtractionResult",
    "GapAnalysisResult",
    "CandidateIssue",
    "QuestionDraft",
]
