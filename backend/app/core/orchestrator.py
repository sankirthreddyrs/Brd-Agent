"""AI Core Loop Orchestrator for the BRD Agent.

Executes the main synthesis loop:
1. Merges new stakeholder answers into existing requirements.
2. Extracts or refreshes candidate requirements and assumptions via Gemini.
3. Deduplicates and unifies requirements.
4. Executes deterministic completeness and consistency validation.
5. If blockers exist, drafts prioritized clarification questions and sets
   status to AWAITING_CLARIFICATION; otherwise sets status to READY_TO_GENERATE.
"""

from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.core.extraction import extract_requirements
from app.core.merge import merge_answers_into_requirements
from app.core.question_engine import (
    issues_to_questions,
    select_top_questions,
    warnings_to_assumptions,
)
from app.core.validation_rules import (
    validate_project_completeness,
    validate_requirements,
)
from app.llm.llm_client import LLMClient, GeminiClient
from app.models.answer import Answer
from app.models.assumption import Assumption
from app.models.document import SourceChunk
from app.models.project import ProjectStatus
from app.models.question import Question
from app.models.requirement import Requirement
from app.models.validation import ValidationResult


class WorkflowResult(BaseModel):
    """Container representing the output of an analysis iteration cycle."""

    model_config = ConfigDict(use_enum_values=False)

    requirements: list[Requirement] = Field(
        default_factory=list,
        description="Unified list of candidate and verified requirements",
    )
    assumptions: list[Assumption] = Field(
        default_factory=list,
        description="Active assumptions including proposed defaults",
    )
    validation_result: ValidationResult = Field(
        default_factory=ValidationResult,
        description="Comprehensive validation check results",
    )
    open_questions: list[Question] = Field(
        default_factory=list,
        description="Prioritized clarification questions requiring user input",
    )
    next_status: ProjectStatus = Field(
        ...,
        description="Recommended next project state (AWAITING_CLARIFICATION or READY_TO_GENERATE)",
    )


class BRDOrchestrator:
    """Orchestrates requirement extraction, validation, and clarification cycles."""

    def __init__(
        self,
        gemini_client: Optional[LLMClient] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        """Initialize the orchestrator with an LLM client.

        Args:
            gemini_client: Configured legacy Gemini client instance.
            llm_client: Configured provider-neutral LLM client instance.
        """
        self.gemini_client = llm_client or gemini_client or LLMClient()
        self.llm_client = self.gemini_client

    def run_analysis(
        self,
        idea_text: Optional[str] = None,
        existing_requirements: Optional[Sequence[Requirement]] = None,
        answered_questions: Optional[Sequence[Question]] = None,
        answers: Optional[Sequence[Answer]] = None,
        already_asked_field_paths: Optional[set[str]] = None,
        project_id: str = "project-default",
        chunks: Optional[Sequence[SourceChunk]] = None,
    ) -> WorkflowResult:
        """Execute one complete extraction, validation, and question-generation cycle.

        Args:
            idea_text: Optional raw business idea prompt from user.
            existing_requirements: Previously captured requirements.
            answered_questions: Historical questions that received answers.
            answers: Newly submitted answers to merge.
            already_asked_field_paths: Field paths previously queried to prevent repeats.
            project_id: Target project identifier.
            chunks: Optional source document chunks for document-grounded extraction.

        Returns:
            WorkflowResult containing updated requirements, assumptions, and next status.
        """
        curr_reqs = list(existing_requirements) if existing_requirements else []
        curr_questions = list(answered_questions) if answered_questions else []
        curr_answers = list(answers) if answers else []
        asked_paths = set(already_asked_field_paths or set())

        # 1. Merge new stakeholder answers into existing requirements
        if curr_answers and curr_questions:
            merged_reqs = merge_answers_into_requirements(
                requirements=curr_reqs,
                questions=curr_questions,
                answers=curr_answers,
            )
        else:
            merged_reqs = list(curr_reqs)

        # 2. Build answered context summary for LLM grounding
        answered_lines: list[str] = []
        if curr_questions and curr_answers:
            ans_map = {a.question_id: a.value for a in curr_answers}
            for q in curr_questions:
                if q.id in ans_map:
                    answered_lines.append(f"Q: {q.question_text}\nA: {ans_map[q.id]}")
        answered_context = "\n\n".join(answered_lines) if answered_lines else None

        # 3. Extract or refresh requirements via LLM
        extracted_reqs, extracted_assumptions = extract_requirements(
            idea_text=idea_text,
            existing_requirements=merged_reqs,
            answered_context=answered_context,
            chunks=chunks,
            gemini_client=self.gemini_client,
            project_id=project_id,
        )

        # 4. Deduplicate and unify requirements (by ID)
        req_by_id: dict[str, Requirement] = {r.id: r for r in merged_reqs}
        for ext in extracted_reqs:
            if ext.id in req_by_id:
                prev = req_by_id[ext.id]
                # Retain trace refs, actor, outcome from merged answers if already provided
                req_by_id[ext.id] = ext.model_copy(
                    update={
                        "actor": prev.actor or ext.actor,
                        "outcome": prev.outcome or ext.outcome,
                        "acceptance_criteria": list(
                            dict.fromkeys(ext.acceptance_criteria + prev.acceptance_criteria)
                        ),
                        "trace_refs": list(
                            dict.fromkeys(ext.trace_refs + prev.trace_refs)
                        ),
                        "source_chunk_ids": list(
                            dict.fromkeys(ext.source_chunk_ids + prev.source_chunk_ids)
                        ),
                        "confidence": max(ext.confidence, prev.confidence),
                    }
                )
            else:
                req_by_id[ext.id] = ext

        unified_requirements = list(req_by_id.values())

        # 5. Run deterministic rule-based validations
        req_val = validate_requirements(unified_requirements)
        proj_val = validate_project_completeness(unified_requirements)
        combined_issues = req_val.issues + proj_val.issues
        validation_result = ValidationResult(issues=combined_issues)

        # Convert non-blocking warnings to explicit assumptions
        rule_assumptions = warnings_to_assumptions(
            issues=combined_issues,
            project_id=project_id,
        )
        unified_assumptions = extracted_assumptions + rule_assumptions

        # 6. Branch next status based on blockers
        if validation_result.has_blockers:
            raw_questions = issues_to_questions(
                issues=combined_issues,
                requirements=unified_requirements,
                gemini_client=self.gemini_client,
                already_asked_field_paths=asked_paths,
                project_id=project_id,
            )
            open_questions = select_top_questions(raw_questions, max_count=5)
            next_status = ProjectStatus.AWAITING_CLARIFICATION
        else:
            open_questions = []
            next_status = ProjectStatus.READY_TO_GENERATE

        return WorkflowResult(
            requirements=unified_requirements,
            assumptions=unified_assumptions,
            validation_result=validation_result,
            open_questions=open_questions,
            next_status=next_status,
        )
