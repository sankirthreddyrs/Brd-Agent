"""Validation domain models for project readiness and data consistency checks.

Identifies blockers and warnings preventing generation or indicating ambiguity.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    """Severity tier for validation findings."""

    BLOCKER = "blocker"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """Individual issue found during validation or gap analysis.

    Attributes:
        code: Machine-readable rule violation code (e.g., GAP_MISSING_ACTOR).
        severity: Level of severity (blocker prevents generation, warning advises review).
        field_path: Dot-notated path to the field or section that triggered the issue.
        entity_id: Optional identifier of the associated requirement, question, or document.
        message: Human-readable explanation of the issue.
    """

    model_config = ConfigDict(use_enum_values=False)

    code: str = Field(..., description="Machine-readable issue code")
    severity: Severity = Field(..., description="Issue severity classification")
    field_path: str = Field(..., description="Path to the affected field or entity")
    entity_id: Optional[str] = Field(
        default=None,
        description="Associated entity identifier (requirement ID, question ID, etc.)",
    )
    message: str = Field(..., description="Human-readable issue explanation")


class ValidationResult(BaseModel):
    """Aggregate result from a validation check suite.

    Attributes:
        issues: List of validation issues discovered.
    """

    model_config = ConfigDict(use_enum_values=False)

    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="List of issues found during validation",
    )

    @property
    def has_blockers(self) -> bool:
        """Return True if any issues are of BLOCKER severity."""
        return any(issue.severity == Severity.BLOCKER for issue in self.issues)
