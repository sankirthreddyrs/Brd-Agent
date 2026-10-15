"""Deterministic requirements completeness and validation engine.

Implements pure Python validation rules with zero LLM involvement.
Enforces the specification principle: "The backend, not the LLM, decides completeness."
"""

import difflib
import re
from typing import Sequence

from app.models.requirement import Requirement, RequirementType
from app.models.validation import Severity, ValidationIssue, ValidationResult

# Recognized quality attribute keywords for nonfunctional requirement checks
NFR_ATTRIBUTE_KEYWORDS = {
    "performance",
    "latency",
    "throughput",
    "speed",
    "response time",
    "scalability",
    "capacity",
    "elasticity",
    "load",
    "security",
    "privacy",
    "confidentiality",
    "integrity",
    "authentication",
    "authorization",
    "encryption",
    "availability",
    "uptime",
    "reliability",
    "fault tolerance",
    "resilience",
    "disaster recovery",
    "backup",
    "usability",
    "accessibility",
    "maintainability",
    "modularity",
    "extensibility",
    "portability",
    "compliance",
    "regulatory",
    "audit",
    "observability",
    "monitoring",
    "logging",
}

# Indicators for constraint rationale or authoritative sources
CONSTRAINT_RATIONALE_INDICATORS = [
    "because",
    "due to",
    "mandated by",
    "required by",
    "per",
    "standard",
    "regulation",
    "compliance",
    "policy",
    "gdpr",
    "hipaa",
    "sox",
    "pci",
    "architecture",
    "budget",
    "contract",
    "source:",
    "rationale:",
]


def _has_measurable_target(req: Requirement) -> bool:
    """Check heuristic: presence of digits, units, or percentages."""
    combined_text = " ".join([req.statement] + req.acceptance_criteria).lower()
    # Check for numbers / digits
    if re.search(r"\d+", combined_text):
        return True
    # Check for common unit or percentage symbols / words
    if re.search(
        r"(%|percent|ms|milliseconds?|seconds?|mins?|minutes?|hours?|days?|mb|gb|tb|kb|req/s|rps|tps|uptime)",
        combined_text,
    ):
        return True
    return False


def _has_business_success_measure(req: Requirement) -> bool:
    """Check if business requirement contains a verifiable success metric or target."""
    combined = " ".join(
        filter(None, [req.outcome, req.statement] + req.acceptance_criteria)
    ).lower()
    if re.search(r"\d+", combined):
        return True
    if re.search(
        r"(%|percent|roi|kpi|revenue|cost|reduction|increase|decrease|growth|saving|margin|target)",
        combined,
    ):
        return True
    return False


def _has_constraint_rationale(req: Requirement) -> bool:
    """Check if a constraint has a stated rationale or external source."""
    if req.outcome and req.outcome.strip():
        return True
    if req.trace_refs and len(req.trace_refs) > 0:
        return True
    stmt_lower = req.statement.lower()
    return any(indicator in stmt_lower for indicator in CONSTRAINT_RATIONALE_INDICATORS)


def validate_requirements(requirements: Sequence[Requirement]) -> ValidationResult:
    """Execute deterministic completeness and consistency validation on a list of requirements.

    Applies strict rule-based criteria:
    - Functional: BLOCKER if missing actor, missing outcome, or empty acceptance_criteria.
    - Nonfunctional: BLOCKER if quality attribute is unclear; WARNING if no measurable target.
    - Business: BLOCKER if missing objective; WARNING if no success measure.
    - Constraint: BLOCKER if missing rationale or source.
    - Duplicates: WARNING if similarity ratio > 0.85 between same-type requirements.
    - Low confidence: WARNING if confidence < 0.5.

    Args:
        requirements: Collection of Requirement objects to validate.

    Returns:
        ValidationResult containing all identified issues.
    """
    issues: list[ValidationIssue] = []

    # 1. Individual requirement validations
    for req in requirements:
        # Rule: Low confidence warning (< 0.5)
        if req.confidence < 0.5:
            issues.append(
                ValidationIssue(
                    code="LOW_CONFIDENCE_REQUIREMENT",
                    severity=Severity.WARNING,
                    field_path=f"requirements[{req.id}].confidence",
                    entity_id=req.id,
                    message=(
                        f"Requirement '{req.id}' has low extraction confidence "
                        f"({req.confidence:.2f}) and requires stakeholder confirmation."
                    ),
                )
            )

        if req.type == RequirementType.FUNCTIONAL:
            # Missing actor
            if not req.actor or not req.actor.strip():
                issues.append(
                    ValidationIssue(
                        code="FUNC_MISSING_ACTOR",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].actor",
                        entity_id=req.id,
                        message=f"Functional requirement '{req.id}' is missing a designated actor or persona.",
                    )
                )

            # Missing outcome
            if not req.outcome or not req.outcome.strip():
                issues.append(
                    ValidationIssue(
                        code="FUNC_MISSING_OUTCOME",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].outcome",
                        entity_id=req.id,
                        message=f"Functional requirement '{req.id}' is missing an expected outcome or business value.",
                    )
                )

            # Empty acceptance criteria
            if not req.acceptance_criteria or len(req.acceptance_criteria) == 0:
                issues.append(
                    ValidationIssue(
                        code="FUNC_EMPTY_ACCEPTANCE_CRITERIA",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].acceptance_criteria",
                        entity_id=req.id,
                        message=f"Functional requirement '{req.id}' has no acceptance criteria defined.",
                    )
                )

        elif req.type == RequirementType.NONFUNCTIONAL:
            # Check if quality attribute itself is unclear
            text_to_check = f"{req.title} {req.statement}".lower()
            attribute_found = any(
                kw in text_to_check for kw in NFR_ATTRIBUTE_KEYWORDS
            )

            if not attribute_found:
                issues.append(
                    ValidationIssue(
                        code="NFR_UNCLEAR_ATTRIBUTE",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].statement",
                        entity_id=req.id,
                        message=(
                            f"Nonfunctional requirement '{req.id}' does not clearly specify "
                            f"which quality attribute (e.g., performance, security, availability) is being governed."
                        ),
                    )
                )
            else:
                # Quality attribute named, but no measurable target
                if not _has_measurable_target(req):
                    issues.append(
                        ValidationIssue(
                            code="NFR_NO_MEASURABLE_TARGET",
                            severity=Severity.WARNING,
                            field_path=f"requirements[{req.id}].acceptance_criteria",
                            entity_id=req.id,
                            message=(
                                f"Nonfunctional requirement '{req.id}' specifies a quality attribute "
                                f"but lacks a measurable numeric target or metric (e.g., ms, %, uptime SLA)."
                            ),
                        )
                    )

        elif req.type == RequirementType.BUSINESS:
            # Missing business objective
            has_objective = bool(
                (req.outcome and req.outcome.strip())
                or (req.statement and req.statement.strip())
            )
            if not has_objective:
                issues.append(
                    ValidationIssue(
                        code="BIZ_MISSING_OBJECTIVE",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].outcome",
                        entity_id=req.id,
                        message=f"Business requirement '{req.id}' is missing an explicit business objective.",
                    )
                )
            else:
                # Has objective, but no stated success measure
                if not _has_business_success_measure(req):
                    issues.append(
                        ValidationIssue(
                            code="BIZ_NO_SUCCESS_MEASURE",
                            severity=Severity.WARNING,
                            field_path=f"requirements[{req.id}].outcome",
                            entity_id=req.id,
                            message=(
                                f"Business requirement '{req.id}' lacks a quantifiable or verifiable "
                                f"measure of business success (e.g., ROI, revenue target, percentage reduction)."
                            ),
                        )
                    )

        elif req.type == RequirementType.CONSTRAINT:
            # Constraint without stated rationale or source
            if not _has_constraint_rationale(req):
                issues.append(
                    ValidationIssue(
                        code="CONSTRAINT_MISSING_RATIONALE",
                        severity=Severity.BLOCKER,
                        field_path=f"requirements[{req.id}].outcome",
                        entity_id=req.id,
                        message=(
                            f"Constraint '{req.id}' is missing an architectural rationale, "
                            f"regulatory reference, or technical source."
                        ),
                    )
                )

    # 2. Check for duplicate-looking requirements (> 0.85 SequenceMatcher similarity)
    req_list = list(requirements)
    n = len(req_list)
    for i in range(n):
        for j in range(i + 1, n):
            req_a = req_list[i]
            req_b = req_list[j]
            if req_a.type == req_b.type:
                title_sim = difflib.SequenceMatcher(
                    None, req_a.title.lower(), req_b.title.lower()
                ).ratio()
                stmt_sim = difflib.SequenceMatcher(
                    None, req_a.statement.lower(), req_b.statement.lower()
                ).ratio()

                if title_sim > 0.85 or stmt_sim > 0.85:
                    issues.append(
                        ValidationIssue(
                            code="DUPLICATE_REQUIREMENT",
                            severity=Severity.WARNING,
                            field_path=f"requirements[{req_b.id}]",
                            entity_id=f"{req_a.id},{req_b.id}",
                            message=(
                                f"Requirements '{req_a.id}' and '{req_b.id}' appear to be "
                                f"duplicates or substantially overlapping ({req_a.type.value})."
                            ),
                        )
                    )

    return ValidationResult(issues=issues)


def validate_project_completeness(requirements: Sequence[Requirement]) -> ValidationResult:
    """Validate project-level completeness rules across all requirements.

    Rules:
    - Zero business requirements is a BLOCKER.
    - Zero functional requirements is a BLOCKER.

    Args:
        requirements: Collection of all requirements for the project.

    Returns:
        ValidationResult containing any project-level blockers.
    """
    issues: list[ValidationIssue] = []

    biz_count = sum(1 for r in requirements if r.type == RequirementType.BUSINESS)
    func_count = sum(1 for r in requirements if r.type == RequirementType.FUNCTIONAL)

    if biz_count == 0:
        issues.append(
            ValidationIssue(
                code="PROJECT_NO_BUSINESS_REQUIREMENTS",
                severity=Severity.BLOCKER,
                field_path="requirements.business",
                message="Project has zero business requirements defining high-level goals or strategic outcomes.",
            )
        )

    if func_count == 0:
        issues.append(
            ValidationIssue(
                code="PROJECT_NO_FUNCTIONAL_REQUIREMENTS",
                severity=Severity.BLOCKER,
                field_path="requirements.functional",
                message="Project has zero functional requirements specifying user workflows or features.",
            )
        )

    return ValidationResult(issues=issues)
