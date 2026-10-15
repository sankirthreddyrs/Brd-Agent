"""Requirement domain models for the BRD Agent.

Defines structured requirements categorized by type (business, functional, etc.)
and prioritised using the MoSCoW framework.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RequirementType(str, Enum):
    """Classification of requirement category."""

    FUNCTIONAL = "functional"
    NONFUNCTIONAL = "nonfunctional"
    BUSINESS = "business"
    CONSTRAINT = "constraint"


class Priority(str, Enum):
    """MoSCoW priority classification."""

    MUST = "MUST"
    SHOULD = "SHOULD"
    COULD = "COULD"
    WONT = "WONT"


class Requirement(BaseModel):
    """Structured requirement model capturing statements, criteria, and traceability.

    Attributes:
        id: Unique identifier for the requirement (e.g., REQ-001).
        type: Category of the requirement (functional, nonfunctional, business, constraint).
        title: Short title summarizing the requirement.
        statement: Comprehensive requirement statement (e.g., "The system shall...").
        actor: Primary actor, persona, or external system initiating or affected by the requirement.
        outcome: Desired business or technical outcome achieved by fulfilling the requirement.
        priority: MoSCoW priority classification (MUST, SHOULD, COULD, WONT).
        acceptance_criteria: Measurable criteria required to verify completion.
        trace_refs: Cross-reference links to source answers, document chunks, or assumptions.
        confidence: AI extraction confidence score between 0.0 and 1.0.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique identifier for the requirement")
    type: RequirementType = Field(..., description="Category of requirement")
    title: str = Field(..., description="Short summary title")
    statement: str = Field(..., description="Detailed requirement specification statement")
    actor: Optional[str] = Field(
        default=None,
        description="Primary actor or persona involved",
    )
    outcome: Optional[str] = Field(
        default=None,
        description="Expected business outcome or value",
    )
    priority: Priority = Field(
        default=Priority.SHOULD,
        description="MoSCoW priority ranking",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Verification criteria to satisfy requirement",
    )
    trace_refs: list[str] = Field(
        default_factory=list,
        description="Traceability references to answer_id, document_chunk, or assumption_id",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this requirement between 0.0 and 1.0",
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="IDs of source document chunks directly grounding this requirement",
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Optional analyst reasoning or justification",
    )
