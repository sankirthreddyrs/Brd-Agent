"""End-to-end integration tests for the AI Core Loop BRDOrchestrator."""

from datetime import datetime, timezone
import pytest

from app.core.orchestrator import BRDOrchestrator, WorkflowResult
from app.llm.schemas import ExtractionResult, QuestionDraft
from app.models.answer import Answer
from app.models.project import ProjectStatus
from app.models.question import AnswerFormat
from app.models.requirement import Priority, Requirement, RequirementType


class MockOrchestratorGeminiClient:
    """Mock Gemini client simulating round 1 (gap) and round 2 (resolved) extraction."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate_structured(self, prompt: str, response_schema: type):
        if response_schema == QuestionDraft:
            return QuestionDraft(
                question_text="Which user persona books service appointments?",
                why_it_matters="Identifies the primary actor executing the booking workflow.",
                answer_format=AnswerFormat.TEXT,
                options=None,
            )

        if response_schema == ExtractionResult:
            self.call_count += 1
            # Round 1: Returns business req + functional req with MISSING actor
            # Round 2+: Returns business req + functional req with actor resolved if present in context
            actor_val = None
            if "Registered Customer" in prompt:
                actor_val = "Registered Customer"

            return ExtractionResult(
                requirements=[
                    Requirement(
                        id="REQ-B1",
                        type=RequirementType.BUSINESS,
                        title="Increase Service Appointments",
                        statement="Expand local appointment bookings by 30% year over year.",
                        outcome="Achieve 30% revenue expansion from booking fees.",
                        priority=Priority.MUST,
                        confidence=1.0,
                    ),
                    Requirement(
                        id="REQ-F1",
                        type=RequirementType.FUNCTIONAL,
                        title="Book Service Appointment",
                        statement="The system shall allow scheduling appointments with local providers.",
                        actor=actor_val,  # None in round 1, populated in round 2
                        outcome="Appointment is scheduled and confirmed.",
                        priority=Priority.MUST,
                        acceptance_criteria=[
                            "Customer selects provider, service, and valid timeslot.",
                            "System issues confirmation notification to both parties.",
                        ],
                        confidence=0.95,
                    ),
                ],
                proposed_assumptions=[],
            )

        raise ValueError(f"Unexpected response_schema {response_schema}")


def test_orchestrator_detects_gap_and_resolves_upon_answer():
    """Exit condition test:
    1. A missing actor produces a relevant clarification question and status AWAITING_CLARIFICATION.
    2. Submitting an answer updates the requirement and sets status to READY_TO_GENERATE.
    """
    mock_client = MockOrchestratorGeminiClient()
    orchestrator = BRDOrchestrator(gemini_client=mock_client)

    idea = "I want to build an app where users can book appointments with local service providers."

    # --- ROUND 1: Initial extraction ---
    result_round1: WorkflowResult = orchestrator.run_analysis(
        idea_text=idea,
        existing_requirements=[],
        answered_questions=[],
        answers=[],
        already_asked_field_paths=set(),
        project_id="test-proj-001",
    )

    # Assert Round 1: Has blockers, status is AWAITING_CLARIFICATION
    assert result_round1.next_status == ProjectStatus.AWAITING_CLARIFICATION
    assert result_round1.validation_result.has_blockers
    assert any(i.code == "FUNC_MISSING_ACTOR" for i in result_round1.validation_result.issues)

    # Exactly one targeted question for the missing actor
    assert len(result_round1.open_questions) >= 1
    actor_q = next(
        q for q in result_round1.open_questions if "actor" in q.field_path
    )
    assert actor_q.impact == 3
    assert actor_q.field_path == "requirements[REQ-F1].actor"
    assert "user persona" in actor_q.question_text.lower() or "actor" in actor_q.question_text.lower()

    # --- ROUND 2: User answers the question ---
    now = datetime.now(timezone.utc)
    user_answer = Answer(
        id="ANS-100",
        project_id="test-proj-001",
        question_id=actor_q.id,
        value="Registered Customer",
        answered_at=now,
    )

    result_round2: WorkflowResult = orchestrator.run_analysis(
        idea_text=idea,
        existing_requirements=result_round1.requirements,
        answered_questions=[actor_q],
        answers=[user_answer],
        already_asked_field_paths={actor_q.field_path},
        project_id="test-proj-001",
    )

    # Assert Round 2: Blockers resolved, status is READY_TO_GENERATE
    assert not result_round2.validation_result.has_blockers
    assert result_round2.next_status == ProjectStatus.READY_TO_GENERATE
    assert len(result_round2.open_questions) == 0

    # Verify requirement was updated with the answer, trace_refs, and confidence
    req_f1 = next(r for r in result_round2.requirements if r.id == "REQ-F1")
    assert req_f1.actor == "Registered Customer"
    assert "ANS-100" in req_f1.trace_refs
    assert req_f1.confidence >= 0.95
