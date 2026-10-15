"""Question generation engine and warning-to-assumption converter.

Converts blocking validation issues into prioritized stakeholder clarification questions
using Gemini, and converts non-blocking warnings into explicit assumptions.
"""

from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from app.llm.gemini_client import GeminiClient
from app.llm.prompts import build_question_text_prompt
from app.llm.schemas import QuestionDraft
from app.models.assumption import Assumption, AssumptionStatus, ImpactLevel
from app.models.question import AnswerFormat, Question
from app.models.requirement import Requirement
from app.models.validation import Severity, ValidationIssue

# Impact ranking lookup table based on architectural & scope gravity
# 3: Core workflow, security, architecture, cost, project scope absence
# 2: Acceptance criteria or major user interaction
# 1: Minor or wording issues
IMPACT_LOOKUP: dict[str, int] = {
    "PROJECT_NO_BUSINESS_REQUIREMENTS": 3,
    "PROJECT_NO_FUNCTIONAL_REQUIREMENTS": 3,
    "FUNC_MISSING_ACTOR": 3,
    "FUNC_MISSING_OUTCOME": 3,
    "NFR_UNCLEAR_ATTRIBUTE": 3,
    "CONSTRAINT_MISSING_RATIONALE": 3,
    "BIZ_MISSING_OBJECTIVE": 3,
    "FUNC_EMPTY_ACCEPTANCE_CRITERIA": 2,
    "NFR_NO_MEASURABLE_TARGET": 2,
    "BIZ_NO_SUCCESS_MEASURE": 2,
    "DUPLICATE_REQUIREMENT": 1,
    "LOW_CONFIDENCE_REQUIREMENT": 1,
}


def _determine_gap_confidence(
    issue: ValidationIssue,
    related_req: Optional[Requirement],
) -> float:
    """Heuristically assign gap confidence (0.9 if completely missing, 0.5 if vague/partial)."""
    if not related_req:
        return 0.9

    field_path = issue.field_path.lower()
    if "actor" in field_path:
        return 0.9 if not related_req.actor else 0.5
    if "outcome" in field_path:
        return 0.9 if not related_req.outcome else 0.5
    if "acceptance_criteria" in field_path:
        return 0.9 if not related_req.acceptance_criteria else 0.5
    if "statement" in field_path:
        return 0.5

    return 0.9


def issues_to_questions(
    issues: Sequence[ValidationIssue],
    requirements: Sequence[Requirement],
    gemini_client: GeminiClient,
    already_asked_field_paths: Optional[set[str]] = None,
    project_id: str = "project-default",
) -> list[Question]:
    """Transform BLOCKER validation issues into prioritized Question objects using Gemini.

    Skips WARNING issues (which become assumptions) and skips field paths
    that have already been asked in prior iterations.

    Args:
        issues: List of validation issues from rule evaluation.
        requirements: List of existing requirements.
        gemini_client: Client used to draft non-technical question phrasing.
        already_asked_field_paths: Set of dot-notated field paths already queried.
        project_id: Parent project identifier.

    Returns:
        List of generated Question objects sorted by priority.
    """
    already_asked = already_asked_field_paths or set()
    req_map = {r.id: r for r in requirements}
    questions: list[Question] = []
    seen_field_paths: set[str] = set()

    for issue in issues:
        # Only BLOCKERS generate questions; warnings become assumptions
        if issue.severity != Severity.BLOCKER:
            continue

        # Skip if already asked previously or in this batch
        if issue.field_path in already_asked or issue.field_path in seen_field_paths:
            continue

        seen_field_paths.add(issue.field_path)

        related_req = req_map.get(issue.entity_id) if issue.entity_id else None
        impact = IMPACT_LOOKUP.get(issue.code, 2)
        gap_confidence = _determine_gap_confidence(issue, related_req)

        # Call Gemini to draft stakeholder question phrasing
        prompt = build_question_text_prompt(
            issue=issue,
            related_requirement=related_req,
        )
        draft: QuestionDraft = gemini_client.generate_structured(
            prompt=prompt,
            response_schema=QuestionDraft,
        )

        q_id = f"Q-{uuid.uuid4().hex[:6]}"
        question = Question(
            id=q_id,
            project_id=project_id,
            field_path=issue.field_path,
            question_text=draft.question_text,
            why_it_matters=draft.why_it_matters,
            answer_format=draft.answer_format,
            options=draft.options,
            impact=impact,
            gap_confidence=gap_confidence,
            status="open",
            created_at=datetime.now(timezone.utc),
        )
        question.compute_priority()
        questions.append(question)

    return sorted(questions, key=lambda q: q.priority, reverse=True)


def select_top_questions(questions: list[Question], max_count: int = 5) -> list[Question]:
    """Select top questions by priority, strictly preserving all impact=3 questions.

    Args:
        questions: Full list of open questions.
        max_count: Maximum standard number of questions to present.

    Returns:
        Filtered list containing all impact=3 questions plus top-priority questions up to max_count.
    """
    if not questions:
        return []

    sorted_by_priority = sorted(questions, key=lambda q: q.priority, reverse=True)

    # All impact=3 questions are mandatory regardless of max_count
    mandatory_questions = [q for q in sorted_by_priority if q.impact == 3]
    selected_ids = {q.id for q in mandatory_questions}
    selected = list(mandatory_questions)

    # Fill remaining slots up to max_count
    for q in sorted_by_priority:
        if len(selected) >= max_count:
            break
        if q.id not in selected_ids:
            selected.append(q)
            selected_ids.add(q.id)

    return sorted(selected, key=lambda q: q.priority, reverse=True)


def warnings_to_assumptions(
    issues: Sequence[ValidationIssue],
    project_id: str = "project-default",
) -> list[Assumption]:
    """Generate explicit proposed Assumption objects for WARNING-level issues.

    Non-blocking warnings (such as unquantified NFR targets or missing financial metrics)
    are captured as explicit assumptions with rationale, rather than blocking the user.

    Args:
        issues: Validation issues containing WARNINGs.
        project_id: Associated project identifier.

    Returns:
        List of proposed Assumption models.
    """
    assumptions: list[Assumption] = []

    for issue in issues:
        if issue.severity != Severity.WARNING:
            continue

        linked_ids = [issue.entity_id] if issue.entity_id else []

        if issue.code == "NFR_NO_MEASURABLE_TARGET":
            statement = (
                "Assume standard enterprise SLAs apply (e.g. 99.9% uptime, "
                "response times under 500ms for p95 traffic) until custom metrics are supplied."
            )
            rationale = (
                "The initial idea specified quality targets without concrete numerical metrics."
            )
            impact = ImpactLevel.MEDIUM

        elif issue.code == "BIZ_NO_SUCCESS_MEASURE":
            statement = (
                "Assume business success will be measured by user adoption and operational efficiency."
            )
            rationale = (
                "Quantitative ROI or financial milestone metrics were not stated in the original prompt."
            )
            impact = ImpactLevel.MEDIUM

        elif issue.code == "DUPLICATE_REQUIREMENT":
            statement = (
                f"Assume requirements '{issue.entity_id}' can be unified into a consolidated specification."
            )
            rationale = "High semantic and lexical overlap detected by sequence matcher."
            impact = ImpactLevel.LOW

        elif issue.code == "LOW_CONFIDENCE_REQUIREMENT":
            statement = (
                f"Assume requirement '{issue.entity_id}' reflects intended stakeholder scope."
            )
            rationale = "AI extraction confidence was below 0.50 threshold."
            impact = ImpactLevel.LOW

        else:
            statement = f"Assume standard default behavior for: {issue.message}"
            rationale = "Rule engine generated assumption to resolve non-blocking ambiguity."
            impact = ImpactLevel.LOW

        assumptions.append(
            Assumption(
                id=f"ASM-{uuid.uuid4().hex[:6]}",
                project_id=project_id,
                statement=statement,
                rationale=rationale,
                impact=impact,
                status=AssumptionStatus.PROPOSED,
                linked_requirement_ids=linked_ids,
            )
        )

    return assumptions
