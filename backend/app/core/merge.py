"""Answer merging engine for incorporating stakeholder responses into requirements.

Updates requirement attributes, boosts confidence toward 1.0, and records
full traceability links back to the answer ID without mutating existing objects.
"""

import re
from typing import Sequence
import uuid

from app.models.answer import Answer
from app.models.question import Question
from app.models.requirement import Priority, Requirement, RequirementType


def _extract_req_id(field_path: str) -> str | None:
    """Extract requirement ID from path syntax like 'requirements[REQ-001].actor'."""
    match = re.search(r"requirements\[([^\]]+)\]", field_path)
    if match:
        return match.group(1)
    return None


def merge_answers_into_requirements(
    requirements: Sequence[Requirement],
    questions: Sequence[Question],
    answers: Sequence[Answer],
) -> list[Requirement]:
    """Merge answered clarification questions into requirements immutably.

    For each answered question:
    1. Locates the targeted requirement via field_path syntax or entity correlation.
    2. Updates the relevant field (actor, outcome, acceptance_criteria, statement) with the answer.
    3. Raises the requirement's confidence to 1.0.
    4. Appends the Answer ID into trace_refs for auditability.
    5. Returns a new list of Requirement objects using model_copy(update=...).

    Args:
        requirements: Existing requirements to be updated.
        questions: Questions that were posed to the stakeholder.
        answers: Answers submitted by the stakeholder.

    Returns:
        New list of updated Requirement objects.
    """
    question_map = {q.id: q for q in questions}
    # Index requirements by id
    req_dict: dict[str, Requirement] = {r.id: r for r in requirements}
    new_requirements: list[Requirement] = []

    for answer in answers:
        question = question_map.get(answer.question_id)
        if not question:
            continue

        target_req_id = _extract_req_id(question.field_path)

        if target_req_id and target_req_id in req_dict:
            orig_req = req_dict[target_req_id]
            updates: dict[str, object] = {
                "confidence": 1.0,
            }

            # Update trace references
            current_traces = list(orig_req.trace_refs)
            if answer.id not in current_traces:
                current_traces.append(answer.id)
            updates["trace_refs"] = current_traces

            # Identify target field
            field_path = question.field_path.lower()
            if ".actor" in field_path:
                updates["actor"] = answer.value
            elif ".outcome" in field_path:
                updates["outcome"] = answer.value
            elif ".acceptance_criteria" in field_path:
                criteria = list(orig_req.acceptance_criteria)
                if answer.value not in criteria:
                    criteria.append(answer.value)
                updates["acceptance_criteria"] = criteria
            elif ".statement" in field_path:
                updates["statement"] = (
                    f"{orig_req.statement} (Clarification: {answer.value})"
                )

            req_dict[target_req_id] = orig_req.model_copy(update=updates)

        elif "requirements.business" in question.field_path:
            # Answer resolves project-level missing business requirement
            new_req_id = f"REQ-BIZ-{uuid.uuid4().hex[:4].upper()}"
            new_requirements.append(
                Requirement(
                    id=new_req_id,
                    type=RequirementType.BUSINESS,
                    title="Core Business Objective",
                    statement=answer.value,
                    actor="Stakeholder",
                    outcome=answer.value,
                    priority=Priority.MUST,
                    acceptance_criteria=[f"Demonstrate: {answer.value}"],
                    confidence=1.0,
                    trace_refs=[answer.id],
                )
            )

        elif "requirements.functional" in question.field_path:
            # Answer resolves project-level missing functional requirement
            new_req_id = f"REQ-FUNC-{uuid.uuid4().hex[:4].upper()}"
            new_requirements.append(
                Requirement(
                    id=new_req_id,
                    type=RequirementType.FUNCTIONAL,
                    title="Core Workflow Feature",
                    statement=answer.value,
                    actor="User",
                    outcome=answer.value,
                    priority=Priority.MUST,
                    acceptance_criteria=[f"System executes: {answer.value}"],
                    confidence=1.0,
                    trace_refs=[answer.id],
                )
            )

    return list(req_dict.values()) + new_requirements
