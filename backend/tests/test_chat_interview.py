"""Unit and integration tests for conversational clarification chat interview endpoint."""

from datetime import datetime, timezone
from typing import Any, Optional
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_gemini_client, get_repository
from app.llm.prompts import ChatTurnEvaluation
from app.main import app
from app.models.answer import Answer
from app.models.project import Project, ProjectStatus
from app.models.question import AnswerFormat, Question
from app.models.requirement import Priority, Requirement, RequirementType
from tests.test_api_persistence import InMemoryProjectRepository


class MockChatLLMClient:
    """Mock LLM client evaluating conversational clarification interview turns."""

    def __init__(self) -> None:
        self.last_prompt: Optional[str] = None

    def generate_structured(self, prompt: str, response_schema: type) -> Any:
        self.last_prompt = prompt
        if response_schema == ChatTurnEvaluation:
            # If prompt indicates user is answering who the actor is
            if "Verified Business Owner" in prompt:
                return ChatTurnEvaluation(
                    answered_question_id="Q-ACTOR-01",
                    extracted_answer="Verified Business Owner",
                    reply="Thank you! I've registered 'Verified Business Owner' as the actor. All requirements are now fully defined and validated. You can now generate the BRD!",
                )
            # Default conversational reply
            return ChatTurnEvaluation(
                answered_question_id=None,
                extracted_answer=None,
                reply="Hello! As your Lead Business Analyst, I see we have an open question about who initiates booking. Could you clarify the user role?",
            )
        raise ValueError(f"Unexpected schema: {response_schema}")


@pytest.fixture
def chat_env():
    repo = InMemoryProjectRepository()
    mock_llm = MockChatLLMClient()

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_gemini_client] = lambda: mock_llm

    client = TestClient(app)
    yield client, repo, mock_llm
    app.dependency_overrides.clear()


def test_conversational_chat_general_inquiry(chat_env):
    """Test chatting with assistant when no specific question is answered."""
    client, repo, _ = chat_env

    # 1. Setup project in AWAITING_CLARIFICATION with 1 open question
    project = repo.create_project(
        title="Fleet Management System",
        idea="Real-time vehicle tracking and service booking platform.",
    )
    repo.set_status_with_transition(
        project.id,
        ProjectStatus.ANALYZING,
        event="analyze",
    )
    repo.set_status_with_transition(
        project.id,
        ProjectStatus.AWAITING_CLARIFICATION,
        event="blocking_gaps_found",
    )

    q = Question(
        id="Q-ACTOR-01",
        project_id=project.id,
        field_path="requirements[REQ-01].actor",
        question_text="Which user role books service appointments?",
        why_it_matters="Clarifies who performs the booking action.",
        answer_format=AnswerFormat.TEXT,
        impact=3,
        gap_confidence=0.9,
        priority=2.7,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    repo.save_questions(project.id, [q])

    # 2. User sends general question
    response = client.post(
        f"/projects/{project.id}/chat",
        json={
            "message": "Hi, what information do you need from me?",
            "history": [],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "Lead Business Analyst" in data["reply"]
    assert data["answered_question_id"] is None
    assert data["open_question_count"] == 1
    assert data["is_ready_to_generate"] is False
    assert data["project_status"] == ProjectStatus.AWAITING_CLARIFICATION.value

    # Verify no answer was persisted
    assert len(repo.get_answers(project.id)) == 0


def test_conversational_chat_answers_question_and_transitions(chat_env):
    """Test user answering a clarification question, updating requirements, and transitioning to READY_TO_GENERATE."""
    client, repo, _ = chat_env

    # 1. Setup project with valid business req and functional req missing actor
    project = repo.create_project(
        title="Fleet Management System",
        idea="Real-time vehicle tracking and service booking platform.",
    )
    repo.set_status_with_transition(
        project.id,
        ProjectStatus.ANALYZING,
        event="analyze",
    )
    repo.set_status_with_transition(
        project.id,
        ProjectStatus.AWAITING_CLARIFICATION,
        event="blocking_gaps_found",
    )

    biz_req = Requirement(
        id="REQ-BIZ-01",
        type=RequirementType.BUSINESS,
        title="Fleet Efficiency",
        statement="Improve fleet operational efficiency by 20%.",
        outcome="Achieve 20% operational efficiency gain.",
        priority=Priority.MUST,
        confidence=1.0,
    )
    func_req = Requirement(
        id="REQ-01",
        type=RequirementType.FUNCTIONAL,
        title="Book Vehicle Maintenance",
        statement="Book maintenance for company vehicles.",
        actor=None,  # Missing actor creates blocker
        outcome="Maintenance booked successfully.",
        priority=Priority.MUST,
        acceptance_criteria=["Select date and service center", "Receive confirmation ticket"],
        confidence=0.6,
    )
    repo.save_requirements(project.id, [biz_req, func_req])

    q = Question(
        id="Q-ACTOR-01",
        project_id=project.id,
        field_path="requirements[REQ-01].actor",
        question_text="Which user role books service appointments?",
        why_it_matters="Clarifies who performs the booking action.",
        answer_format=AnswerFormat.TEXT,
        impact=3,
        gap_confidence=0.9,
        priority=2.7,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    repo.save_questions(project.id, [q])

    # 2. User sends message providing the answer
    response = client.post(
        f"/projects/{project.id}/chat",
        json={
            "message": "The actor who books appointments is the Verified Business Owner.",
            "history": [
                {"role": "assistant", "content": "Which user role books service appointments?"}
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answered_question_id"] == "Q-ACTOR-01"
    assert "Verified Business Owner" in data["reply"]
    assert data["open_question_count"] == 0
    assert data["is_ready_to_generate"] is True
    assert data["project_status"] == ProjectStatus.READY_TO_GENERATE.value

    # 3. Check repository answer persistence
    answers = repo.get_answers(project.id)
    assert len(answers) == 1
    assert answers[0].question_id == "Q-ACTOR-01"
    assert answers[0].value == "Verified Business Owner"
    assert answers[0].answered_by == "dev-user-000"

    # 4. Check requirement update and trace_refs
    updated_reqs = {r.id: r for r in repo.get_requirements(project.id)}
    assert updated_reqs["REQ-01"].actor == "Verified Business Owner"
    assert updated_reqs["REQ-01"].confidence == 1.0
    assert any(ref.startswith("ANS:") for ref in updated_reqs["REQ-01"].trace_refs)

    # 5. Check question status updated to answered
    all_qs = repo.get_all_questions(project.id)
    assert all_qs[0].status == "answered"


def test_conversational_chat_project_not_found(chat_env):
    """Test 404 returned when project does not exist."""
    client, _, _ = chat_env
    response = client.post(
        "/projects/non-existent-uuid/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 404
