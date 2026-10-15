"""Unit tests for BRD Agent Pydantic domain models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models import (
    Answer,
    AnswerFormat,
    Assumption,
    AssumptionStatus,
    BRDDocumentVersion,
    ImpactLevel,
    Priority,
    Project,
    ProjectStatus,
    Question,
    Requirement,
    RequirementType,
    Severity,
    SourceChunk,
    SourceDocument,
    SourceDocumentStatus,
    ValidationIssue,
    ValidationResult,
)
from app.templates.brd_template import build_brd_skeleton


def test_project_model_defaults_and_validation():
    """Verify Project model initialization, default values, and types."""
    now = datetime.now(timezone.utc)
    proj = Project(
        id="p-100",
        title="CRM Integration Hub",
        idea="Connect Salesforce with internal ERP.",
        created_at=now,
        updated_at=now,
    )

    assert proj.status == ProjectStatus.DRAFT
    assert proj.input_revision == 1
    assert proj.last_error is None
    assert proj.title == "CRM Integration Hub"

    # Input revision must be >= 1
    with pytest.raises(ValidationError):
        Project(
            id="p-101",
            title="Invalid",
            idea="Invalid revision",
            input_revision=0,
            created_at=now,
            updated_at=now,
        )


def test_requirement_model_validations():
    """Validate Requirement model constraints, default values, and confidence limits."""
    req = Requirement(
        id="REQ-001",
        type=RequirementType.FUNCTIONAL,
        title="User SSO",
        statement="The system shall allow users to sign in using Okta SSO.",
        actor="Employee",
        outcome="Seamless single sign-on experience.",
        priority=Priority.MUST,
        acceptance_criteria=["Redirect to Okta login", "Session lasts 8 hours"],
        trace_refs=["DOC-001#chunk-2"],
        confidence=0.95,
    )
    assert req.priority == Priority.MUST
    assert req.confidence == 0.95
    assert len(req.acceptance_criteria) == 2

    # Confidence cannot exceed 1.0
    with pytest.raises(ValidationError):
        Requirement(
            id="REQ-002",
            type=RequirementType.NONFUNCTIONAL,
            title="Latency",
            statement="Latency < 100ms",
            confidence=1.05,
        )

    # Confidence cannot be negative
    with pytest.raises(ValidationError):
        Requirement(
            id="REQ-003",
            type=RequirementType.BUSINESS,
            title="ROI",
            statement="Must increase revenue by 20%",
            confidence=-0.1,
        )

    # Invalid RequirementType enum rejected
    with pytest.raises(ValidationError):
        Requirement(
            id="REQ-004",
            type="invalid_type",  # type: ignore[arg-type]
            title="Bad",
            statement="Bad type",
        )


def test_question_model_and_compute_priority():
    """Test Question model validation rules and compute_priority() calculation."""
    now = datetime.now(timezone.utc)
    question = Question(
        id="Q-001",
        project_id="p-100",
        field_path="security.authentication",
        question_text="Which identity provider does your company use?",
        why_it_matters="Determines authentication adapter required.",
        answer_format=AnswerFormat.CHOICE,
        options=["Okta", "Azure AD", "Auth0", "Custom SAML"],
        impact=3,
        gap_confidence=0.8,
        created_at=now,
    )

    # Priority calculation
    priority_score = question.compute_priority()
    assert pytest.approx(priority_score, rel=1e-3) == 2.4
    assert pytest.approx(question.priority, rel=1e-3) == 2.4

    # Impact outside 1-3 range is rejected: impact=0
    with pytest.raises(ValidationError):
        Question(
            id="Q-002",
            project_id="p-100",
            field_path="scope",
            question_text="Invalid question?",
            why_it_matters="Testing impact min bound",
            answer_format=AnswerFormat.TEXT,
            impact=0,
            gap_confidence=0.5,
            created_at=now,
        )

    # Impact outside 1-3 range is rejected: impact=4
    with pytest.raises(ValidationError):
        Question(
            id="Q-003",
            project_id="p-100",
            field_path="scope",
            question_text="Invalid question?",
            why_it_matters="Testing impact max bound",
            answer_format=AnswerFormat.TEXT,
            impact=4,
            gap_confidence=0.5,
            created_at=now,
        )

    # gap_confidence outside 0.0-1.0 is rejected: gap_confidence=1.5
    with pytest.raises(ValidationError):
        Question(
            id="Q-004",
            project_id="p-100",
            field_path="scope",
            question_text="Invalid confidence?",
            why_it_matters="Testing confidence upper bound",
            answer_format=AnswerFormat.YES_NO,
            impact=2,
            gap_confidence=1.5,
            created_at=now,
        )

    # Invalid status is rejected
    with pytest.raises(ValidationError):
        Question(
            id="Q-005",
            project_id="p-100",
            field_path="scope",
            question_text="Invalid status?",
            why_it_matters="Testing status enum",
            answer_format=AnswerFormat.YES_NO,
            impact=2,
            gap_confidence=0.5,
            status="archived",  # type: ignore[arg-type]
            created_at=now,
        )


def test_validation_result_has_blockers():
    """Verify ValidationResult blocker detection."""
    # Empty result
    result_empty = ValidationResult()
    assert not result_empty.has_blockers

    # Warning only
    result_warning = ValidationResult(
        issues=[
            ValidationIssue(
                code="WARN_MISSING_OPTIONAL_SECTION",
                severity=Severity.WARNING,
                field_path="nonfunctional.scalability",
                message="Scalability targets are unspecified.",
            )
        ]
    )
    assert not result_warning.has_blockers

    # Blocker present
    result_blocker = ValidationResult(
        issues=[
            ValidationIssue(
                code="BLOCKER_AMBIGUOUS_ACTOR",
                severity=Severity.BLOCKER,
                field_path="requirements[0].actor",
                entity_id="REQ-001",
                message="Primary actor is missing and ambiguous.",
            ),
            ValidationIssue(
                code="WARN_NO_ACCEPTANCE_CRITERIA",
                severity=Severity.WARNING,
                field_path="requirements[0].acceptance_criteria",
                entity_id="REQ-001",
                message="Acceptance criteria empty.",
            ),
        ]
    )
    assert result_blocker.has_blockers


def test_assumption_model_validations():
    """Verify Assumption model instantiation and enum constraints."""
    asm = Assumption(
        id="ASM-001",
        project_id="p-100",
        statement="All users reside in North America.",
        rationale="Client indicated primary business operations in US & Canada.",
        impact=ImpactLevel.MEDIUM,
        status=AssumptionStatus.PROPOSED,
        linked_requirement_ids=["REQ-001", "REQ-002"],
    )
    assert asm.status == AssumptionStatus.PROPOSED
    assert asm.impact == ImpactLevel.MEDIUM
    assert len(asm.linked_requirement_ids) == 2

    # Reject invalid impact enum
    with pytest.raises(ValidationError):
        Assumption(
            id="ASM-002",
            project_id="p-100",
            statement="Test bad impact",
            rationale="Test",
            impact="CRITICAL",  # type: ignore[arg-type]
        )


def test_answer_model():
    """Verify Answer model attributes."""
    now = datetime.now(timezone.utc)
    ans = Answer(
        id="ANS-001",
        project_id="p-100",
        question_id="Q-001",
        value="Okta",
        answered_at=now,
    )
    assert ans.question_id == "Q-001"
    assert ans.value == "Okta"


def test_document_and_version_models():
    """Verify SourceDocument, SourceChunk, and BRDDocumentVersion models."""
    doc = SourceDocument(
        id="DOC-001",
        project_id="p-100",
        filename="specs.pdf",
        file_type="pdf",
        status=SourceDocumentStatus.READY,
        storage_path="/data/docs/DOC-001.pdf",
    )
    assert doc.status == SourceDocumentStatus.READY

    # Unsupported file type rejected
    with pytest.raises(ValidationError):
        SourceDocument(
            id="DOC-002",
            project_id="p-100",
            filename="malicious.exe",
            file_type="exe",  # type: ignore[arg-type]
            status=SourceDocumentStatus.UPLOADED,
        )

    chunk = SourceChunk(
        id="CHK-001",
        document_id="DOC-001",
        project_id="p-100",
        text="Section 3: Security & Access Control Requirements...",
        page_number=3,
        heading="3. Security",
        chunk_index=0,
    )
    assert chunk.chunk_index == 0
    assert chunk.page_number == 3

    now = datetime.now(timezone.utc)
    version = BRDDocumentVersion(
        id="VER-001",
        project_id="p-100",
        version=1,
        input_revision=1,
        content_json={"title": "CRM Hub"},
        model_used="gemini-1.5-pro",
        prompt_version="v1.0.0",
        generated_at=now,
        quality_check_passed=True,
    )
    assert version.is_current is True
    assert version.quality_check_passed is True


def test_brd_skeleton_structure():
    """Verify build_brd_skeleton creates a dictionary matching the BRD template spec."""
    now = datetime.now(timezone.utc)
    project = Project(
        id="p-200",
        title="Fleet Management System",
        idea="GPS tracking and predictive maintenance for logistics trucks.",
        created_at=now,
        updated_at=now,
    )
    skeleton = build_brd_skeleton(project)

    assert skeleton["title"] == "Fleet Management System"
    assert skeleton["version"] == 1
    assert skeleton["generated_at"] is None
    assert skeleton["executive_summary"] == ""
    assert isinstance(skeleton["business_requirements"], list)
    assert isinstance(skeleton["functional_requirements"], list)
    assert isinstance(skeleton["nonfunctional_requirements"], list)
    assert isinstance(skeleton["constraints"], list)
    assert isinstance(skeleton["assumptions"], list)
    assert isinstance(skeleton["open_questions"], list)
    assert (
        skeleton["traceability_note"]
        == "Every requirement links to a source document, a user answer, or an explicitly accepted assumption."
    )
