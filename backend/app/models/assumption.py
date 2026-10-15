"""Assumption domain models for the BRD Agent.

Defines assumptions made to resolve unanswerable gaps or standard architectural defaults.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class ImpactLevel(str, Enum):
    """Impact severity if an assumption proves invalid."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AssumptionStatus(str, Enum):
    """Lifecycle status of a project assumption."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Assumption(BaseModel):
    """Explicit assumption made during BRD synthesis.

    Attributes:
        id: Unique identifier for the assumption (e.g., ASM-001).
        project_id: Associated project identifier.
        statement: Assumption premise or claim.
        rationale: Reason why this assumption was made.
        impact: Consequence level if this assumption turns out false.
        status: Current status (PROPOSED, ACCEPTED, REJECTED, SUPERSEDED).
        linked_requirement_ids: List of requirement IDs directly dependent on this assumption.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique assumption identifier")
    project_id: str = Field(
        default="",
        description="Associated project ID",
    )
    statement: str = Field(..., description="Assumption statement")
    rationale: str = Field(..., description="Rationale for making this assumption")
    impact: ImpactLevel = Field(
        ...,
        description="Potential impact if assumption is invalidated",
    )
    status: AssumptionStatus = Field(
        default=AssumptionStatus.PROPOSED,
        description="Current approval status of the assumption",
    )
    linked_requirement_ids: list[str] = Field(
        default_factory=list,
        description="IDs of requirements linked to this assumption",
    )
