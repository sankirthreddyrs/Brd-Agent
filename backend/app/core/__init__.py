"""Core engine components for BRD Agent."""

from .brd_generator import BRDGenerator
from .document_parser import (
    DocumentParser,
    ParsedChunk,
    ParsedDocument,
    parse_file,
)
from .docx_renderer import render_brd_to_docx
from .extraction import extract_requirements, extract_requirements_and_assumptions
from .merge import merge_answers_into_requirements
from .orchestrator import BRDOrchestrator, WorkflowResult
from .question_engine import (
    issues_to_questions,
    select_top_questions,
    warnings_to_assumptions,
)
from .state_machine import InvalidTransitionError, ProjectEvent, ProjectStateMachine
from .validation_rules import (
    validate_project_completeness,
    validate_requirements,
)

__all__ = [
    "ProjectStateMachine",
    "ProjectEvent",
    "InvalidTransitionError",
    "BRDOrchestrator",
    "WorkflowResult",
    "extract_requirements",
    "extract_requirements_and_assumptions",
    "merge_answers_into_requirements",
    "validate_requirements",
    "validate_project_completeness",
    "issues_to_questions",
    "select_top_questions",
    "warnings_to_assumptions",
    "DocumentParser",
    "ParsedDocument",
    "ParsedChunk",
    "parse_file",
    "BRDGenerator",
    "render_brd_to_docx",
]

