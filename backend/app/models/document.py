"""Document domain models for source inputs and generated BRD artifacts.

Defines models for uploaded source files, chunked text for grounding, and
versioned BRD documents.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class SourceDocumentStatus(str, Enum):
    """Processing status of an uploaded source document."""

    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    READY = "READY"
    FAILED = "FAILED"


class SourceDocument(BaseModel):
    """Source document uploaded to provide grounding context for BRD generation.

    Attributes:
        id: Unique identifier for the document.
        project_id: Associated project identifier.
        filename: Original file name.
        file_type: Extension format ('pdf', 'docx', 'txt').
        status: Ingestion status (UPLOADED, EXTRACTING, READY, FAILED).
        storage_path: Local filesystem or cloud storage path.
        error_message: Processing error if status is FAILED.
        file_size_bytes: Size of the uploaded file in bytes.
        created_at: Creation or upload timestamp.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(..., description="Unique document identifier")
    project_id: str = Field(..., description="Associated project ID")
    filename: str = Field(..., description="Original filename")
    file_type: Literal["pdf", "docx", "txt", "image"] = Field(
        ...,
        description="Supported file format (pdf, docx, txt, image)",
    )
    status: SourceDocumentStatus = Field(
        ...,
        description="Document extraction status",
    )
    storage_path: Optional[str] = Field(
        default=None,
        description="Storage location path",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Diagnostic error message if extraction failed",
    )
    file_size_bytes: Optional[int] = Field(
        default=None,
        description="Size of the uploaded file in bytes",
    )
    created_at: Optional[Union[datetime, str]] = Field(
        default=None,
        description="Timestamp when document was created or uploaded",
    )
    uploaded_by: Optional[str] = Field(
        default=None,
        description="UUID of the user who uploaded this document",
    )
    uploader_email: Optional[str] = Field(
        default=None,
        description="Email address of the uploader",
    )


class SourceChunk(BaseModel):
    """Chunk of extracted text used for semantic search and traceability grounding.

    Attributes:
        id: Unique identifier for the chunk (standard UUID string).
        document_id: Identifier of source document.
        project_id: Associated project identifier.
        text: Extracted text slice.
        page_number: Source page number if available.
        heading: Nearest header or section title in original document.
        chunk_index: Zero-indexed position of chunk in source document.
        chunk_label: Optional human-readable chunk label (e.g., CHUNK-6b1277f9-0).
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique chunk UUID identifier",
    )
    document_id: str = Field(..., description="Associated document ID")
    project_id: str = Field(..., description="Associated project ID")
    text: str = Field(..., description="Extracted textual content")
    page_number: Optional[int] = Field(
        default=None,
        description="Page number from original document",
    )
    heading: Optional[str] = Field(
        default=None,
        description="Nearest section heading",
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="0-indexed order of chunk in document",
    )
    chunk_label: Optional[str] = Field(
        default=None,
        description="Human-readable label for the chunk (e.g. CHUNK-6b1277f9-0)",
    )


class BRDDocumentVersion(BaseModel):
    """Generated BRD document instance reflecting a specific input revision.

    Attributes:
        id: Unique identifier for the generated version.
        project_id: Associated project identifier.
        version: Incremental document version number.
        input_revision: Input revision number this BRD was generated from.
        title: Document title.
        content_json: Structured BRD content dictionary (requirements, assumptions, etc.).
        docx_path: Path to rendered DOCX file artifact.
        docx_bytes: Optional raw binary bytes of rendered DOCX artifact.
        model_used: Identifier of AI model that performed synthesis.
        prompt_version: Version tag of prompt templates used.
        generated_at: Timestamp when generation completed.
        quality_check_passed: Result of automated consistency and quality checks.
        is_current: True if this is the active/latest version for the project.
        status: Ingestion or generation status.
    """

    model_config = ConfigDict(use_enum_values=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique version identifier")
    project_id: str = Field(..., description="Associated project ID")
    version: int = Field(default=1, ge=1, description="Sequential BRD version number")
    input_revision: int = Field(
        default=1,
        ge=1,
        description="Input revision on which this version is based",
    )
    title: Optional[str] = Field(
        default=None,
        description="Document title",
    )
    content_json: dict[str, Any] = Field(
        ...,
        description="Structured JSON representation of BRD sections",
    )
    docx_path: Optional[str] = Field(
        default=None,
        description="Filesystem path to generated .docx document",
    )
    docx_bytes: Optional[bytes] = Field(
        default=None,
        description="Binary bytes of rendered DOCX artifact",
    )
    model_used: str = Field(
        default="llama-3.3-70b-versatile",
        description="AI model used for generating this BRD version",
    )
    prompt_version: str = Field(
        default="v1.0",
        description="Version tag of generation prompts",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when generation completed",
    )
    quality_check_passed: bool = Field(
        default=True,
        description="Flag indicating if quality validation passed",
    )
    is_current: bool = Field(
        default=True,
        description="Whether this version is the current active version",
    )
    status: Optional[str] = Field(
        default="COMPLETED",
        description="Generation status",
    )

    def __init__(self, **data: Any) -> None:
        if "version_number" in data and "version" not in data:
            data["version"] = data["version_number"]
        if "created_at" in data and "generated_at" not in data:
            data["generated_at"] = data["created_at"]
        super().__init__(**data)

    @property
    def version_number(self) -> int:
        """Alias for version number."""
        return self.version

    @property
    def created_at(self) -> datetime:
        """Alias for generated_at timestamp."""
        return self.generated_at
