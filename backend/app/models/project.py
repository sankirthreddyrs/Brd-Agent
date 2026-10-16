"""Project domain models for the BRD Agent.

Defines the core Project entity and its lifecycle status enum.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectStatus(str, Enum):
    """Lifecycle statuses for a BRD project."""

    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    READY_TO_GENERATE = "READY_TO_GENERATE"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Project(BaseModel):
    """Core domain model representing a BRD generation project.

    Attributes:
        id: Unique identifier for the project.
        title: Human-readable project title.
        idea: Original raw business idea text or prompt provided by user.
        status: Current lifecycle state of the project.
        input_revision: Counter tracking changes to inputs (answers, uploaded sources).
        created_at: Timestamp when project was initialized.
        updated_at: Timestamp when project was last modified.
        last_error: Diagnostic error message when status is FAILED.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique identifier for the project")
    title: str = Field(..., description="Project title")
    idea: str = Field(..., description="Original business idea text")
    status: ProjectStatus = Field(
        default=ProjectStatus.DRAFT,
        description="Current project lifecycle status",
    )
    input_revision: int = Field(
        default=1,
        ge=1,
        description="Revision number of project inputs",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the project was created",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the project was last updated",
    )
    last_error: Optional[str] = Field(
        default=None,
        description="Populated error message when status == FAILED",
    )
    owner_id: Optional[str] = Field(
        default=None,
        description="UUID of the user who created/owns this project",
    )
    owner_email: Optional[str] = Field(
        default=None,
        description="Email address of the project owner",
    )
