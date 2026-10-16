"""HTTP request and response schemas for FastAPI endpoints.

Domain models in app.models remain the source of truth; these models define
HTTP-level payload validation and response structuring.
"""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.assumption import Assumption
from app.models.project import Project, ProjectStatus
from app.models.question import Question
from app.models.requirement import Requirement
from app.models.validation import ValidationResult


class CreateProjectRequest(BaseModel):
    """Payload to initialize a new BRD generation project."""

    title: Optional[str] = Field(
        default=None,
        description="Optional title. Generated automatically from idea if omitted.",
    )
    idea: str = Field(
        ...,
        min_length=10,
        description="Raw business idea text (minimum 10 characters).",
    )


class CreateProjectResponse(BaseModel):
    """Response returned upon project initialization."""

    model_config = ConfigDict(use_enum_values=False)
    project: Project


class AnalyzeResponse(BaseModel):
    """Response returned from analysis iteration."""

    model_config = ConfigDict(use_enum_values=False)

    project: Project
    requirements: list[Requirement] = Field(default_factory=list)
    validation_result: ValidationResult = Field(default_factory=ValidationResult)
    open_questions: list[Question] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    next_status: ProjectStatus


class AnswerItem(BaseModel):
    """Individual answer submitted for an open clarification question."""

    question_id: str = Field(..., description="ID of the question being answered")
    value: str = Field(..., description="Stakeholder response text")


class SubmitAnswersRequest(BaseModel):
    """Payload to submit answers for open clarification questions."""

    answers: list[AnswerItem] = Field(
        ...,
        min_length=1,
        description="List of question answers to submit and merge.",
    )


class SubmitAnswersResponse(BaseModel):
    """Response returned after merging answers and re-evaluating readiness."""

    model_config = ConfigDict(use_enum_values=False)

    project: Project
    requirements: list[Requirement] = Field(default_factory=list)
    validation_result: ValidationResult = Field(default_factory=ValidationResult)
    open_questions: list[Question] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    next_status: ProjectStatus


class AssumptionDecisionRequest(BaseModel):
    """Payload to accept or reject an explicit assumption."""

    decision: Literal["accepted", "rejected", "ACCEPTED", "REJECTED"] = Field(
        ...,
        description="Review decision ('accepted' or 'rejected').",
    )


class ProjectDetailResponse(BaseModel):
    """Project metadata accompanied by aggregate entity counts."""

    model_config = ConfigDict(use_enum_values=False)

    project: Project
    requirement_count: int = Field(default=0)
    open_question_count: int = Field(default=0)
    assumption_count: int = Field(default=0)


class SourceDocumentResponse(BaseModel):
    """Metadata response for an uploaded source document."""

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique document identifier")
    project_id: str = Field(..., description="Associated project identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="Document type: pdf, docx, or txt")
    file_size_bytes: Optional[int] = Field(
        default=None,
        description="Size of the uploaded file in bytes",
    )
    status: str = Field(..., description="Processing status")
    chunk_count: int = Field(default=0, description="Total extracted chunk count")
    created_at: Optional[str] = Field(
        default=None,
        description="Creation or upload timestamp ISO string",
    )


class SourceDocumentListResponse(BaseModel):
    """List container response of uploaded source documents."""

    model_config = ConfigDict(use_enum_values=False)

    items: list[SourceDocumentResponse] = Field(
        default_factory=list,
        description="List of uploaded source documents for project",
    )


ProjectResponse = Project


class BRDVersionResponse(BaseModel):
    """Structured response representing a compiled BRD document version."""

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique BRD version identifier")
    project_id: str = Field(..., description="Associated project identifier")
    version_number: int = Field(..., description="Sequential version number")
    title: str = Field(..., description="Document title")
    content_json: dict = Field(..., description="Structured 7-section BRD JSON content")
    status: str = Field(..., description="Generation status (e.g. COMPLETED)")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of generation")


class BRDGenerateResponse(BaseModel):
    """Response returned upon successful BRD compilation and generation."""

    model_config = ConfigDict(use_enum_values=False)

    project: Project
    brd_version: BRDVersionResponse
    download_url: str = Field(..., description="Relative download URL for DOCX artifact")

