"""Tests for Source Document Upload and Grounded Analysis Integration in FastAPI endpoints."""

from datetime import datetime, timezone
import io
from typing import Any, Optional
import uuid
import pypdf
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_gemini_client, get_repository
from app.llm.schemas import ExtractionResult, QuestionDraft
from app.main import app
from app.models.assumption import Assumption, AssumptionStatus, ImpactLevel
from app.models.document import SourceChunk, SourceDocument, SourceDocumentStatus
from app.models.project import Project, ProjectStatus
from app.models.question import AnswerFormat, Question
from app.models.requirement import Priority, Requirement, RequirementType
from app.models.validation import ValidationIssue, ValidationResult
from tests.test_api_persistence import InMemoryProjectRepository


class MockLLMClientForSources:
    """Mock LLM client tailored for source document chunk extraction and traceability testing."""

    def __init__(self) -> None:
        self.last_prompt: Optional[str] = None
        self.received_chunk_ids: list[str] = []

    def generate_structured(self, prompt: str, response_schema: type) -> Any:
        self.last_prompt = prompt

        if response_schema == QuestionDraft:
            return QuestionDraft(
                question_text="What authentication scheme is required?",
                why_it_matters="Clarifies login security.",
                answer_format=AnswerFormat.TEXT,
                options=None,
            )

        if response_schema == ExtractionResult:
            import re
            chunk_id = "CHUNK-UNKNOWN"
            match = re.search(r"\[CHUNK_ID:\s*([^\s|\]]+)", prompt)
            if match:
                chunk_id = match.group(1).strip()
                self.received_chunk_ids.append(chunk_id)

            return ExtractionResult(
                requirements=[
                    Requirement(
                        id="REQ-BIZ-001",
                        type=RequirementType.BUSINESS,
                        title="Revenue Expansion",
                        statement="Expand enterprise subscription volume by 35% annually.",
                        outcome="Achieve 35% revenue growth.",
                        priority=Priority.MUST,
                        confidence=1.0,
                    ),
                    Requirement(
                        id="REQ-FUNC-001",
                        type=RequirementType.FUNCTIONAL,
                        title="Automated Statement Reconciliation",
                        statement="System automatically parses uploaded source ledger statements.",
                        actor="Financial Auditor",
                        outcome="Ledger reconciled successfully.",
                        priority=Priority.MUST,
                        acceptance_criteria=[
                            "Parser validates statement format",
                            "Generates discrepancy summary",
                        ],
                        source_chunk_ids=[chunk_id] if chunk_id != "CHUNK-UNKNOWN" else [],
                        confidence=0.98,
                    ),
                ],
                proposed_assumptions=[
                    Assumption(
                        id="ASM-001",
                        project_id="test",
                        statement="Assume PDF bank statements use UTF-8 text encoding.",
                        rationale="Standard export format for commercial banking systems.",
                        impact=ImpactLevel.LOW,
                        status=AssumptionStatus.PROPOSED,
                    )
                ],
            )
        raise ValueError(f"Unexpected schema: {response_schema}")


@pytest.fixture
def sources_test_setup():
    """Setup TestClient with fresh InMemoryProjectRepository and MockLLMClientForSources."""
    repo = InMemoryProjectRepository()
    mock_llm = MockLLMClientForSources()

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_gemini_client] = lambda: mock_llm

    client = TestClient(app)
    yield client, repo, mock_llm

    app.dependency_overrides.clear()


def test_upload_valid_txt_file_persists_chunks(sources_test_setup):
    """Uploading a valid TXT file via POST /projects/{id}/sources returns 201 and persists chunks."""
    client, repo, _ = sources_test_setup

    # 1. Create project
    create_res = client.post(
        "/projects",
        json={"title": "Document Parsing Project", "idea": "System for extracting requirements from financial specs."},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["project"]["id"]

    # 2. Upload text document
    doc_content = (
        "Business Objective: Automate 90% of manual requirement analysis.\n"
        "Functional Specification: The application shall allow financial managers to import quarterly budgets.\n"
        "Security: The system must enforce AES-256 encryption at rest."
    )
    files = {"file": ("financial_specs.txt", doc_content.encode("utf-8"), "text/plain")}
    res = client.post(f"/projects/{project_id}/sources", files=files)
    assert res.status_code == 201

    doc_data = res.json()
    assert doc_data["project_id"] == project_id
    assert doc_data["filename"] == "financial_specs.txt"
    assert doc_data["file_type"] == "txt"
    assert doc_data["status"] == "READY"
    assert doc_data["chunk_count"] >= 1
    assert doc_data["file_size_bytes"] == len(doc_content.encode("utf-8"))
    assert doc_data["created_at"] is not None

    # 3. Check persistence in repository
    chunks = repo.get_source_chunks_by_project(project_id)
    assert len(chunks) == doc_data["chunk_count"]
    assert any("financial managers" in c.text for c in chunks)

    # 4. Strictly verify SourceChunk.id is a valid UUID string
    first_chunk = chunks[0]
    parsed_uuid = uuid.UUID(first_chunk.id)
    assert str(parsed_uuid) == first_chunk.id
    assert first_chunk.chunk_label is not None
    assert first_chunk.chunk_label.startswith("CHUNK-")

    # 5. Verify repository row conversion guarantees PostgreSQL UUID compatibility
    from app.db.repository import ProjectRepository
    row = ProjectRepository._source_chunk_to_row(first_chunk)
    assert uuid.UUID(row["id"])
    assert uuid.UUID(row["document_id"])
    assert uuid.UUID(row["project_id"])

    # 6. Verify non-UUID chunk IDs gracefully convert to valid UUIDs in row
    non_uuid_chunk = SourceChunk(
        id="CHUNK-6b1277f9-0",
        document_id=project_id,
        project_id=project_id,
        text="Sample text",
        chunk_index=0,
    )
    converted_row = ProjectRepository._source_chunk_to_row(non_uuid_chunk)
    assert uuid.UUID(converted_row["id"])
    assert converted_row["heading"] == "CHUNK-6b1277f9-0"

    # 7. Verify GET /projects/{id}/sources listing
    list_res = client.get(f"/projects/{project_id}/sources")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert "items" in list_data
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["id"] == doc_data["id"]
    assert list_data["items"][0]["chunk_count"] == doc_data["chunk_count"]


def test_upload_valid_pdf_file_persists_chunks(sources_test_setup):
    """Uploading a valid PDF file via POST /projects/{id}/sources returns 201."""
    client, repo, _ = sources_test_setup

    # Create project
    create_res = client.post(
        "/projects",
        json={"title": "PDF Analysis Project", "idea": "Ingesting architecture documentation from PDF format."},
    )
    project_id = create_res.json()["project"]["id"]

    # Generate 2-page PDF
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    files = {"file": ("architecture.pdf", pdf_bytes, "application/pdf")}
    res = client.post(f"/projects/{project_id}/sources", files=files)
    assert res.status_code == 201

    data = res.json()
    assert data["filename"] == "architecture.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "READY"
    assert data["file_size_bytes"] == len(pdf_bytes)


def test_upload_file_exceeding_10mb_rejected(sources_test_setup):
    """Uploading a file exceeding 10MB returns 400 or 413."""
    client, _, _ = sources_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Oversized Test", "idea": "Testing size threshold guardrails."},
    )
    project_id = create_res.json()["project"]["id"]

    oversized_bytes = b"0" * (10 * 1024 * 1024 + 1024)  # > 10MB
    files = {"file": ("large_data.txt", oversized_bytes, "text/plain")}
    res = client.post(f"/projects/{project_id}/sources", files=files)
    assert res.status_code in (400, 413)
    assert "10MB" in res.json()["detail"]


def test_upload_to_nonexistent_project_returns_404(sources_test_setup):
    """Uploading to a non-existent project returns 404."""
    client, _, _ = sources_test_setup

    files = {"file": ("notes.txt", b"Some project notes", "text/plain")}
    res = client.post(f"/projects/{str(uuid.uuid4())}/sources", files=files)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_upload_to_invalid_project_status_rejected(sources_test_setup):
    """Uploading sources to a project in FAILED status returns 400."""
    client, repo, _ = sources_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Failed State Test", "idea": "Testing upload state restrictions."},
    )
    project_id = create_res.json()["project"]["id"]

    # Force project into FAILED status
    repo.projects[project_id]["status"] = ProjectStatus.FAILED.value

    files = {"file": ("notes.txt", b"New requirements text", "text/plain")}
    res = client.post(f"/projects/{project_id}/sources", files=files)
    assert res.status_code == 400
    assert "Cannot upload sources" in res.json()["detail"]


def test_analyze_with_uploaded_documents_passes_chunks_and_traces(sources_test_setup):
    """Calling /analyze with uploaded documents passes chunks to orchestrator and sets trace_refs."""
    client, repo, mock_llm = sources_test_setup

    # 1. Create project
    create_res = client.post(
        "/projects",
        json={"title": "End-to-End Grounded Project", "idea": "Financial statement processing engine."},
    )
    project_id = create_res.json()["project"]["id"]

    # 2. Upload source document
    doc_text = "The system shall automatically reconcile bank ledger records against invoices."
    files = {"file": ("bank_specs.txt", doc_text.encode("utf-8"), "text/plain")}
    upload_res = client.post(f"/projects/{project_id}/sources", files=files)
    assert upload_res.status_code == 201

    persisted_chunks = repo.get_source_chunks_by_project(project_id)
    assert len(persisted_chunks) >= 1
    target_chunk_id = persisted_chunks[0].id

    # 3. Call POST /projects/{id}/analyze
    analyze_res = client.post(f"/projects/{project_id}/analyze")
    assert analyze_res.status_code == 200

    data = analyze_res.json()
    assert "requirements" in data
    reqs = data["requirements"]

    # 4. Verify requirement contains chunk traceability reference
    grounded_req = next((r for r in reqs if r["id"] == "REQ-FUNC-001"), None)
    assert grounded_req is not None
    assert target_chunk_id in grounded_req["source_chunk_ids"]
    assert f"CHUNK:{target_chunk_id}" in grounded_req["trace_refs"]

    # Verify prompt received chunks
    assert mock_llm.last_prompt is not None
    assert "### SOURCE DOCUMENT CHUNKS:" in mock_llm.last_prompt
    assert target_chunk_id in mock_llm.last_prompt


def test_analyze_with_only_source_documents_no_idea_text(sources_test_setup):
    """If project has uploaded documents but empty idea_text, analysis proceeds with chunks as primary input."""
    client, repo, mock_llm = sources_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Doc-Only Project", "idea": "Placeholder text before clearing."},
    )
    project_id = create_res.json()["project"]["id"]

    # Clear idea text to simulate a project configured solely with documents
    repo.projects[project_id]["idea"] = ""

    # Upload source document
    files = {"file": ("architecture_spec.txt", b"System shall support 10000 concurrent sessions.", "text/plain")}
    upload_res = client.post(f"/projects/{project_id}/sources", files=files)
    assert upload_res.status_code == 201

    # Execute analysis
    analyze_res = client.post(f"/projects/{project_id}/analyze")
    assert analyze_res.status_code == 200
    assert len(analyze_res.json()["requirements"]) >= 1
    assert "None provided (derive requirements primarily from source document chunks)." in mock_llm.last_prompt


def test_analyze_without_idea_or_documents_rejected(sources_test_setup):
    """Calling /analyze when neither idea nor documents exist returns 400."""
    client, repo, _ = sources_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Empty Project", "idea": "Placeholder to clear."},
    )
    project_id = create_res.json()["project"]["id"]
    repo.projects[project_id]["idea"] = ""

    analyze_res = client.post(f"/projects/{project_id}/analyze")
    assert analyze_res.status_code == 400
    assert "neither idea text nor uploaded source documents" in analyze_res.json()["detail"]
