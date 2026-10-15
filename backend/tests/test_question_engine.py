"""Unit tests for the question engine and warning-to-assumption generator."""

from datetime import datetime, timezone
import pytest

from app.core.question_engine import (
    issues_to_questions,
    select_top_questions,
    warnings_to_assumptions,
)
from app.llm.schemas import QuestionDraft
from app.models.assumption import ImpactLevel
from app.models.question import AnswerFormat, Question
from app.models.requirement import Requirement, RequirementType
from app.models.validation import Severity, ValidationIssue


class FakeGeminiClient:
    """Mock client returning deterministic QuestionDraft responses without API calls."""

    def generate_structured(self, prompt: str, response_schema: type):
        if response_schema == QuestionDraft:
            return QuestionDraft(
                question_text="Who is the primary actor executing this operation?",
                why_it_matters="Determines user role permissions and access policies.",
                answer_format=AnswerFormat.TEXT,
                options=None,
            )
        raise ValueError(f"Unsupported schema {response_schema}")


def test_issues_to_questions_mapping_and_priority():
    """Verify impact mapping, priority computation, and warning exclusion."""
    fake_client = FakeGeminiClient()

    req = Requirement(
        id="REQ-01",
        type=RequirementType.FUNCTIONAL,
        title="Order Food",
        statement="Order food items",
        actor=None,
        outcome="Food ordered",
        acceptance_criteria=[],
    )

    issues = [
        # Impact 3 blocker
        ValidationIssue(
            code="FUNC_MISSING_ACTOR",
            severity=Severity.BLOCKER,
            field_path="requirements[REQ-01].actor",
            entity_id="REQ-01",
            message="Missing actor",
        ),
        # Impact 2 blocker
        ValidationIssue(
            code="FUNC_EMPTY_ACCEPTANCE_CRITERIA",
            severity=Severity.BLOCKER,
            field_path="requirements[REQ-01].acceptance_criteria",
            entity_id="REQ-01",
            message="No criteria",
        ),
        # Warning (must NOT generate a question)
        ValidationIssue(
            code="NFR_NO_MEASURABLE_TARGET",
            severity=Severity.WARNING,
            field_path="requirements[REQ-01].nfr",
            entity_id="REQ-01",
            message="No target",
        ),
    ]

    questions = issues_to_questions(
        issues=issues,
        requirements=[req],
        gemini_client=fake_client,
    )

    # Exactly 2 questions generated (warnings excluded)
    assert len(questions) == 2

    q1 = next(q for q in questions if "actor" in q.field_path)
    assert q1.impact == 3
    assert q1.gap_confidence == 0.9
    assert pytest.approx(q1.priority, rel=1e-3) == 2.7  # 3 * 0.9

    q2 = next(q for q in questions if "acceptance_criteria" in q.field_path)
    assert q2.impact == 2
    assert q2.gap_confidence == 0.9
    assert pytest.approx(q2.priority, rel=1e-3) == 1.8  # 2 * 0.9


def test_issues_to_questions_dedupes_already_asked():
    """Verify that field paths already asked previously are ignored."""
    fake_client = FakeGeminiClient()
    issues = [
        ValidationIssue(
            code="FUNC_MISSING_ACTOR",
            severity=Severity.BLOCKER,
            field_path="requirements[REQ-01].actor",
            entity_id="REQ-01",
            message="Missing actor",
        )
    ]

    already_asked = {"requirements[REQ-01].actor"}

    questions = issues_to_questions(
        issues=issues,
        requirements=[],
        gemini_client=fake_client,
        already_asked_field_paths=already_asked,
    )

    assert len(questions) == 0


def test_select_top_questions_preserves_all_impact_3():
    """Ensure select_top_questions enforces max_count while ALWAYS preserving impact=3."""
    now = datetime.now(timezone.utc)

    # Create 6 questions, 4 of which have impact=3
    questions = [
        Question(
            id="Q1",
            project_id="p1",
            field_path="path1",
            question_text="Q1 text",
            why_it_matters="m1",
            answer_format=AnswerFormat.TEXT,
            impact=3,
            gap_confidence=0.9,
            priority=2.7,
            created_at=now,
        ),
        Question(
            id="Q2",
            project_id="p1",
            field_path="path2",
            question_text="Q2 text",
            why_it_matters="m2",
            answer_format=AnswerFormat.TEXT,
            impact=3,
            gap_confidence=0.8,
            priority=2.4,
            created_at=now,
        ),
        Question(
            id="Q3",
            project_id="p1",
            field_path="path3",
            question_text="Q3 text",
            why_it_matters="m3",
            answer_format=AnswerFormat.TEXT,
            impact=3,
            gap_confidence=0.7,
            priority=2.1,
            created_at=now,
        ),
        Question(
            id="Q4",
            project_id="p1",
            field_path="path4",
            question_text="Q4 text",
            why_it_matters="m4",
            answer_format=AnswerFormat.TEXT,
            impact=3,
            gap_confidence=0.6,
            priority=1.8,
            created_at=now,
        ),
        Question(
            id="Q5",
            project_id="p1",
            field_path="path5",
            question_text="Q5 text",
            why_it_matters="m5",
            answer_format=AnswerFormat.TEXT,
            impact=2,
            gap_confidence=0.9,
            priority=1.8,
            created_at=now,
        ),
        Question(
            id="Q6",
            project_id="p1",
            field_path="path6",
            question_text="Q6 text",
            why_it_matters="m6",
            answer_format=AnswerFormat.TEXT,
            impact=1,
            gap_confidence=0.9,
            priority=0.9,
            created_at=now,
        ),
    ]

    # When max_count=2, all 4 impact=3 questions MUST be returned
    selected_2 = select_top_questions(questions, max_count=2)
    assert len(selected_2) == 4
    assert {q.id for q in selected_2} == {"Q1", "Q2", "Q3", "Q4"}

    # When max_count=5, all 4 impact=3 plus the highest priority other question (Q5) must be returned
    selected_5 = select_top_questions(questions, max_count=5)
    assert len(selected_5) == 5
    assert {q.id for q in selected_5} == {"Q1", "Q2", "Q3", "Q4", "Q5"}


def test_warnings_to_assumptions_generation():
    """Verify that WARNING validation issues are converted to reasonable explicit assumptions."""
    issues = [
        ValidationIssue(
            code="NFR_NO_MEASURABLE_TARGET",
            severity=Severity.WARNING,
            field_path="requirements[REQ-01].acceptance_criteria",
            entity_id="REQ-01",
            message="No measurable target",
        ),
        ValidationIssue(
            code="DUPLICATE_REQUIREMENT",
            severity=Severity.WARNING,
            field_path="requirements[REQ-02]",
            entity_id="REQ-01,REQ-02",
            message="Duplicate overlap",
        ),
    ]

    assumptions = warnings_to_assumptions(issues, project_id="test-proj")
    assert len(assumptions) == 2

    nfr_asm = next(a for a in assumptions if "REQ-01" in a.linked_requirement_ids)
    assert nfr_asm.impact == ImpactLevel.MEDIUM
    assert "SLA" in nfr_asm.statement or "standard" in nfr_asm.statement.lower()

    dup_asm = next(a for a in assumptions if "REQ-01,REQ-02" in a.linked_requirement_ids)
    assert dup_asm.impact == ImpactLevel.LOW
