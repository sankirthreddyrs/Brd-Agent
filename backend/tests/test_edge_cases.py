"""Edge-case automated test suite for Days 8-10 polish.

Covers:
a. test_empty_project_idea_and_no_sources: 422 on empty idea creation or 400 rejection on analyze with 0 docs and empty idea.
b. test_empty_or_whitespace_document_handling: 0-byte or whitespace TXT upload parsed safely without crashing chunking.
c. test_assumption_rejection_lifecycle: Rejection transitions assumption to REJECTED, creates follow-up question, and resets state.
d. test_project_not_found_across_all_endpoints: Sub-routes return 404 for unknown UUID.
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_gemini_client, get_llm_client, get_repository
from app.core.document_parser import DocumentParser
from app.llm.llm_client import LLMClient
from app.llm.schemas import ExtractionResult, QuestionDraft
from app.main import app
from app.models.assumption import Assumption, AssumptionStatus, ImpactLevel
from app.models.project import Project, ProjectStatus
from app.models.question import AnswerFormat
from tests.test_api_persistence import InMemoryProjectRepository


class MockLLMForEdgeCases:
    """Mock LLM client returning safe default structures."""

    def generate_structured(self, prompt: str, response_schema: type):
        if response_schema == QuestionDraft:
            return QuestionDraft(
                question_text="Could you clarify the requirement?",
                why_it_matters="Needed for precision.",
                answer_format=AnswerFormat.TEXT,
                options=None,
            )
        if response_schema == ExtractionResult:
            return ExtractionResult(requirements=[], assumptions=[])
        raise ValueError(f"Unexpected schema: {response_schema}")


@pytest.fixture
def edge_case_setup():
    """Setup TestClient with fresh InMemoryProjectRepository and MockLLM."""
    repo = InMemoryProjectRepository()
    mock_llm = MockLLMForEdgeCases()

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_llm_client] = lambda: mock_llm
    app.dependency_overrides[get_gemini_client] = lambda: mock_llm

    client = TestClient(app)
    yield client, repo, mock_llm

    app.dependency_overrides.clear()


def test_empty_project_idea_and_no_sources(edge_case_setup):
    """Rejection or 422 when attempting to create/analyze a project with empty idea text and zero documents."""
    client, repo, _ = edge_case_setup

    # 1. Direct validation failure (422) when payload idea is empty or under min_length
    create_empty_res = client.post("/projects", json={"title": "Empty Idea", "idea": ""})
    assert create_empty_res.status_code == 422

    # 2. Rejection (400) when a project has empty idea text and 0 source documents upon analysis
    valid_create_res = client.post(
        "/projects",
        json={"title": "Project to Clear", "idea": "Valid initial idea with sufficient length."},
    )
    assert valid_create_res.status_code == 201
    project_id = valid_create_res.json()["project"]["id"]

    # Clear idea to simulate empty state without documents
    repo.projects[project_id]["idea"] = "   "

    analyze_res = client.post(f"/projects/{project_id}/analyze")
    assert analyze_res.status_code == 400
    assert "neither idea text nor uploaded source documents" in analyze_res.json()["detail"].lower()


def test_empty_or_whitespace_document_handling(edge_case_setup):
    """Uploading an empty 0-byte or whitespace-only TXT file is handled gracefully without crashing chunking."""
    client, repo, _ = edge_case_setup

    create_res = client.post(
        "/projects",
        json={"title": "Doc Ingestion Project", "idea": "Test project for source document edge cases."},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["project"]["id"]

    # 1. Upload 0-byte empty file: handled cleanly with 400 validation error (no 500 server crash)
    empty_file = {"file": ("empty_spec.txt", b"", "text/plain")}
    res_empty = client.post(f"/projects/{project_id}/sources", files=empty_file)
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # 2. Upload whitespace-only file: parsed and chunked safely without crash, yielding 0 chunks
    whitespace_content = b"   \r\n\t  \n\n   \t  \r\n"
    ws_file = {"file": ("whitespace_spec.txt", whitespace_content, "text/plain")}
    res_ws = client.post(f"/projects/{project_id}/sources", files=ws_file)
    assert res_ws.status_code == 201
    data_ws = res_ws.json()
    assert data_ws["chunk_count"] == 0
    assert data_ws["status"] == "READY"

    # 3. Direct parser level: 0-byte raises clear ValueError, while whitespace-only parses safely with 0 chunks
    parser = DocumentParser()
    with pytest.raises(ValueError, match="0 bytes"):
        parser.parse_file("zero.txt", b"")

    parsed_spaces = parser.parse_file("spaces.txt", whitespace_content)
    assert parsed_spaces.chunks == []
    assert parsed_spaces.raw_text == ""

    # Verify sources list endpoint retrieves the stored whitespace document gracefully
    sources_res = client.get(f"/projects/{project_id}/sources")
    assert sources_res.status_code == 200
    assert len(sources_res.json()["items"]) == 1


def test_assumption_rejection_lifecycle(edge_case_setup):
    """Verifies calling the decision endpoint with REJECTED transitions the assumption correctly and records the decision."""
    client, repo, _ = edge_case_setup

    create_res = client.post(
        "/projects",
        json={"title": "Assumption Project", "idea": "Platform requiring strong enterprise security."},
    )
    project_id = create_res.json()["project"]["id"]

    # Seed proposed assumption
    asm_id = "ASM-SEC-001"
    assumption = Assumption(
        id=asm_id,
        project_id=project_id,
        statement="System uses basic HTTP Basic Auth for external APIs.",
        rationale="Simpler initial setup.",
        impact=ImpactLevel.HIGH,
        status=AssumptionStatus.PROPOSED,
    )
    repo.save_assumptions(project_id, [assumption])

    # Put project in READY_TO_GENERATE to verify transition back to AWAITING_CLARIFICATION
    repo.projects[project_id]["status"] = ProjectStatus.READY_TO_GENERATE.value

    # Call decision endpoint with 'REJECTED' (uppercase)
    res = client.post(
        f"/projects/{project_id}/assumptions/{asm_id}/decision",
        json={"decision": "REJECTED"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == AssumptionStatus.REJECTED.value

    # Verify assumption in repository is updated
    updated_in_repo = repo.get_assumptions(project_id)[0]
    assert updated_in_repo.status == AssumptionStatus.REJECTED

    # Verify rejection triggered an open clarification question
    questions = repo.get_all_questions(project_id)
    assert len(questions) == 1
    assert f"assumptions[{asm_id}]" in questions[0].field_path
    assert "rejected" in questions[0].question_text.lower()

    # Verify project status moved back to AWAITING_CLARIFICATION
    proj_updated = repo.get_project(project_id)
    assert proj_updated.status == ProjectStatus.AWAITING_CLARIFICATION


def test_project_not_found_across_all_endpoints(edge_case_setup):
    """Verifies all sub-routes return standard 404s when queried with an unknown UUID."""
    client, _, _ = edge_case_setup
    unknown_id = str(uuid.uuid4())

    # 1. Project details
    assert client.get(f"/projects/{unknown_id}").status_code == 404

    # 2. Analyze
    assert client.post(f"/projects/{unknown_id}/analyze").status_code == 404

    # 3. Sources GET & POST
    assert client.get(f"/projects/{unknown_id}/sources").status_code == 404
    dummy_file = {"file": ("test.txt", b"Sample content", "text/plain")}
    assert client.post(f"/projects/{unknown_id}/sources", files=dummy_file).status_code == 404

    # 4. Questions GET
    assert client.get(f"/projects/{unknown_id}/questions").status_code == 404

    # 5. Answers POST with valid schema payload
    valid_answers_payload = {"answers": [{"question_id": "Q-001", "value": "Specific answer text"}]}
    assert client.post(f"/projects/{unknown_id}/answers", json=valid_answers_payload).status_code == 404

    # 6. Assumptions GET & POST decision
    assert client.get(f"/projects/{unknown_id}/assumptions").status_code == 404
    assert (
        client.post(
            f"/projects/{unknown_id}/assumptions/ASM-FAKE/decision",
            json={"decision": "accepted"},
        ).status_code
        == 404
    )

    # 7. Generate BRD POST
    assert client.post(f"/projects/{unknown_id}/generate").status_code == 404

    # 8. BRD GET & download
    assert client.get(f"/projects/{unknown_id}/brd").status_code == 404
    assert client.get(f"/projects/{unknown_id}/brd/download").status_code == 404
