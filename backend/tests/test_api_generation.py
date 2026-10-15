"""Integration and API tests for BRD generation, inspection, and DOCX download endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_gemini_client, get_repository
from app.main import app
from app.models.assumption import Assumption, AssumptionStatus, ImpactLevel
from app.models.project import Project, ProjectStatus
from app.models.requirement import Priority, Requirement, RequirementType
from tests.test_api_persistence import InMemoryProjectRepository


@pytest.fixture
def generation_test_setup():
    """Setup in-memory repository and FastAPI TestClient with overrides."""
    repo = InMemoryProjectRepository()
    mock_llm = MagicMock()

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_gemini_client] = lambda: mock_llm

    client = TestClient(app)
    yield client, repo, mock_llm

    app.dependency_overrides.clear()


def test_generate_endpoint_success_lifecycle(generation_test_setup):
    """POST /projects/{id}/generate compiles BRD, saves version, and transitions to COMPLETED."""
    client, repo, _ = generation_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Smart Logistics Platform", "idea": "Automated dispatch and freight telematics tracking."},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["project"]["id"]

    # Seed grounded requirements and assumption
    req1 = Requirement(
        id="REQ-FUNC-101",
        title="Automated Route Dispatch",
        statement="System automatically calculates optimal truck route based on fuel and tolls.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Logistics Manager",
        outcome="Shortest, most cost-effective travel itinerary.",
        acceptance_criteria=["Route calculation completes within 2 seconds."],
        trace_refs=["ANSWER:A-1"],
    )
    req2 = Requirement(
        id="REQ-NFR-101",
        title="Telemetry Response Latency",
        statement="GPS ping ingestion must process within 500ms p95.",
        type=RequirementType.NONFUNCTIONAL,
        priority=Priority.MUST,
        actor="Vehicle Sensor Gateway",
        outcome="Real-time map updates.",
        acceptance_criteria=["Load tests sustain 1000 pings/sec with < 500ms response."],
        trace_refs=["CHUNK:doc-chunk-1"],
    )
    asm = Assumption(
        id="ASM-101",
        statement="All delivery vehicles are equipped with active cellular transponders.",
        rationale="Standard industry practice for nationwide carriers.",
        impact=ImpactLevel.HIGH,
        status=AssumptionStatus.ACCEPTED,
    )
    repo.save_requirements(project_id, [req1, req2])
    repo.save_assumptions(project_id, [asm])

    # Put project into READY_TO_GENERATE status
    repo.projects[project_id]["status"] = ProjectStatus.READY_TO_GENERATE.value

    # Call generate endpoint
    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 200
    data = gen_res.json()

    assert "project" in data
    assert data["project"]["status"] == "COMPLETED"

    assert "brd_version" in data
    version = data["brd_version"]
    assert version["project_id"] == project_id
    assert version["version_number"] == 1
    assert version["status"] == "COMPLETED"
    assert "functional_requirements" in version["content_json"]
    assert "traceability_matrix" in version["content_json"]

    assert data["download_url"] == f"/projects/{project_id}/brd/download"

    # Verify GET /projects/{id}/brd
    brd_res = client.get(f"/projects/{project_id}/brd")
    assert brd_res.status_code == 200
    brd_data = brd_res.json()
    assert brd_data["version_number"] == 1
    assert brd_data["status"] == "COMPLETED"
    assert len(brd_data["content_json"]["functional_requirements"]) == 1

    # Verify GET /projects/{id}/brd/download
    dl_res = client.get(f"/projects/{project_id}/brd/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert 'attachment; filename="BRD_Smart_Logistics_Platform_v1.docx"' in dl_res.headers["content-disposition"]
    assert dl_res.content[:4] == b"PK\x03\x04"


def test_generate_endpoint_guard_rejects_non_ready_statuses(generation_test_setup):
    """POST /projects/{id}/generate rejects DRAFT, ANALYZING, and AWAITING_CLARIFICATION with 400."""
    client, repo, _ = generation_test_setup

    create_res = client.post("/projects", json={"idea": "Cloud-based telemedicine video consultation portal."})
    project_id = create_res.json()["project"]["id"]

    for invalid_status in (ProjectStatus.DRAFT, ProjectStatus.ANALYZING, ProjectStatus.AWAITING_CLARIFICATION):
        repo.projects[project_id]["status"] = invalid_status.value
        res = client.post(f"/projects/{project_id}/generate")
        assert res.status_code == 400
        assert "READY_TO_GENERATE" in res.json()["detail"]


def test_generate_traceability_check_blocks_ungrounded_requirements(generation_test_setup):
    """POST /projects/{id}/generate rejects ungrounded requirements with HTTP 422 and marks project FAILED."""
    client, repo, _ = generation_test_setup

    create_res = client.post("/projects", json={"idea": "AI healthcare portal."})
    project_id = create_res.json()["project"]["id"]

    # Seed an ungrounded requirement (no trace_refs and no source_chunk_ids)
    ungrounded_req = Requirement(
        id="REQ-UNGROUNDED-1",
        title="Autonomous AI Medical Diagnosis",
        statement="The system diagnoses complex diseases autonomously without human doctor oversight.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Patient",
        outcome="Instant medical diagnosis.",
        acceptance_criteria=["Prescription generated."],
        trace_refs=[],
        source_chunk_ids=[],
    )
    repo.save_requirements(project_id, [ungrounded_req])
    repo.projects[project_id]["status"] = ProjectStatus.READY_TO_GENERATE.value

    # Attempt generation -> Rejected with 422
    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 422
    assert "Traceability" in gen_res.json()["detail"]

    # Project transitioned to FAILED
    proj = repo.get_project(project_id)
    assert proj.status == ProjectStatus.FAILED
    assert proj.last_error is not None
    assert "REQ-UNGROUNDED-1" in proj.last_error


def test_get_brd_and_download_not_found(generation_test_setup):
    """GET /projects/{id}/brd and /download return 404 if project or BRD does not exist."""
    client, repo, _ = generation_test_setup
    random_id = str(uuid.uuid4())

    # Nonexistent project
    assert client.get(f"/projects/{random_id}/brd").status_code == 404
    assert client.get(f"/projects/{random_id}/brd/download").status_code == 404

    # Existing project without BRD version
    create_res = client.post("/projects", json={"idea": "Personal financial budget tracking app."})
    project_id = create_res.json()["project"]["id"]

    assert client.get(f"/projects/{project_id}/brd").status_code == 404
    assert client.get(f"/projects/{project_id}/brd/download").status_code == 404


def test_generate_endpoint_recovers_from_failed_and_grounds_idea_requirements(generation_test_setup):
    """POST /projects/{id}/generate recovers from FAILED and grounds idea-derived requirements to ['IDEA']."""
    client, repo, _ = generation_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Inventory ERP", "idea": "Track warehouse inventory stock and low threshold alerts."},
    )
    project_id = create_res.json()["project"]["id"]

    # Requirement derived from idea, initially having no chunk or answer citations
    req = Requirement(
        id="REQ-005",
        title="Stock Level Tracking",
        statement="The system tracks stock counts in real time.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Warehouse Clerk",
        outcome="Updated stock counts.",
        acceptance_criteria=["Stock counts update on barcode scan."],
        trace_refs=[],
        source_chunk_ids=[],
    )
    repo.save_requirements(project_id, [req])

    # Put project into FAILED status (simulating a previous failure)
    repo.projects[project_id]["status"] = ProjectStatus.FAILED.value
    repo.projects[project_id]["previous_valid_status"] = ProjectStatus.READY_TO_GENERATE.value

    # Generating from FAILED triggers recovery, grounds to IDEA, and finishes COMPLETED
    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 200
    res_data = gen_res.json()

    assert res_data["project"]["status"] == "COMPLETED"
    brd = res_data["brd_version"]
    assert brd["status"] == "COMPLETED"

    # Verify REQ-005 now has IDEA trace reference
    func_reqs = brd["content_json"]["functional_requirements"]
    assert len(func_reqs) == 1
    assert "IDEA" in func_reqs[0]["trace_refs"]


def test_generate_endpoint_grounds_via_linked_assumptions(generation_test_setup):
    """Requirements without document chunks are grounded when linked to an accepted assumption."""
    client, repo, _ = generation_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "HR Payroll System", "idea": "Employee salary disbursements and tax deductions."},
    )
    project_id = create_res.json()["project"]["id"]

    req = Requirement(
        id="REQ-010",
        title="Automated Tax Withholding",
        statement="Calculate federal and state tax deductions according to current tax brackets.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Payroll Specialist",
        outcome="Accurate pay stubs generated.",
        acceptance_criteria=["Tax withholding complies with IRS tables."],
        trace_refs=[],
        source_chunk_ids=[],
    )
    asm = Assumption(
        id="ASM-TAX-01",
        statement="Assume standard IRS 2026 progressive tax tables apply.",
        rationale="Client confirmed US-based enterprise operation.",
        impact=ImpactLevel.HIGH,
        status=AssumptionStatus.ACCEPTED,
        linked_requirement_ids=["REQ-010"],
    )
    repo.save_requirements(project_id, [req])
    repo.save_assumptions(project_id, [asm])

    repo.projects[project_id]["status"] = ProjectStatus.READY_TO_GENERATE.value

    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 200
    res_data = gen_res.json()
    assert res_data["project"]["status"] == "COMPLETED"

    func_reqs = res_data["brd_version"]["content_json"]["functional_requirements"]
    assert len(func_reqs) == 1
    assert any("ASSUMPTION:ASM-TAX-01" in tr for tr in func_reqs[0]["trace_refs"])


def test_generate_endpoint_recovers_from_failed_when_previous_valid_status_was_generating(generation_test_setup):
    """Recovering from FAILED when previous_valid_status was GENERATING must succeed without InvalidTransitionError."""
    client, repo, _ = generation_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "E-Commerce Re-platform", "idea": "Modern headless commerce platform with real-time inventory."},
    )
    project_id = create_res.json()["project"]["id"]

    req = Requirement(
        id="REQ-ECOM-01",
        title="Inventory Sync",
        statement="Sync SKU counts across warehouses every 60 seconds.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Warehouse Sync Worker",
        outcome="Consistent inventory counts.",
        acceptance_criteria=["Discrepancy resolved within 60s."],
        trace_refs=["IDEA"],
    )
    repo.save_requirements(project_id, [req])

    # Put project into FAILED with previous_valid_status == GENERATING (as left by a failed generation attempt)
    repo.projects[project_id]["status"] = ProjectStatus.FAILED.value
    repo.projects[project_id]["previous_valid_status"] = ProjectStatus.GENERATING.value
    repo.projects[project_id]["last_error"] = "Previous generation timeout"

    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 200
    res_data = gen_res.json()
    assert res_data["project"]["status"] == "COMPLETED"
    assert res_data["brd_version"]["version_number"] == 1


def test_generate_endpoint_allows_idempotent_generating_status(generation_test_setup):
    """POST /projects/{id}/generate succeeds if project is already in GENERATING status without raising InvalidTransitionError."""
    client, repo, _ = generation_test_setup

    create_res = client.post(
        "/projects",
        json={"title": "Fleet Management", "idea": "GPS tracking and vehicle route planning."},
    )
    project_id = create_res.json()["project"]["id"]

    req = Requirement(
        id="REQ-FLEET-01",
        title="Vehicle Location",
        statement="Display active truck locations on operations map.",
        type=RequirementType.FUNCTIONAL,
        priority=Priority.MUST,
        actor="Dispatcher",
        outcome="Live vehicle position markers.",
        acceptance_criteria=["Position updates within 5s."],
        trace_refs=["IDEA"],
    )
    repo.save_requirements(project_id, [req])

    # Put project into GENERATING status
    repo.projects[project_id]["status"] = ProjectStatus.GENERATING.value

    gen_res = client.post(f"/projects/{project_id}/generate")
    assert gen_res.status_code == 200
    res_data = gen_res.json()
    assert res_data["project"]["status"] == "COMPLETED"
    assert res_data["brd_version"]["status"] == "COMPLETED"


def test_set_status_with_transition_supports_reason_parameter(generation_test_setup):
    """Calling set_status_with_transition with reason keyword parameter works without error."""
    _, repo, _ = generation_test_setup

    proj = repo.create_project(title="Test Reason", idea="Idea text for test")
    repo.projects[proj.id]["status"] = ProjectStatus.READY_TO_GENERATE.value

    # Transition using reason keyword argument without explicit event
    p1 = repo.set_status_with_transition(proj.id, ProjectStatus.GENERATING, reason="Starting BRD compilation")
    assert p1.status == ProjectStatus.GENERATING

    # Transition to COMPLETED using reason keyword argument
    p2 = repo.set_status_with_transition(proj.id, ProjectStatus.COMPLETED, reason="BRD generation succeeded")
    assert p2.status == ProjectStatus.COMPLETED


