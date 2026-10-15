"""Unit tests for the Project State Machine."""

from datetime import datetime, timezone
import pytest

from app.core.state_machine import (
    InvalidTransitionError,
    ProjectEvent,
    ProjectStateMachine,
)
from app.models.project import Project, ProjectStatus


@pytest.fixture
def sample_project() -> Project:
    """Fixture providing a fresh Project instance in DRAFT status."""
    now = datetime.now(timezone.utc)
    return Project(
        id="proj-001",
        title="AI-Powered Invoice Processing",
        idea="Automatically extract line items and vendor information from PDF invoices.",
        status=ProjectStatus.DRAFT,
        input_revision=1,
        created_at=now,
        updated_at=now,
    )


def test_full_project_lifecycle_walkthrough(sample_project: Project):
    """Walk through the full lifecycle:
    DRAFT -> ANALYZING -> AWAITING_CLARIFICATION -> ANALYZING
          -> READY_TO_GENERATE -> GENERATING -> GENERATED
          -> (answer/source changed) -> ANALYZING
    """
    assert sample_project.status == ProjectStatus.DRAFT

    # 1. DRAFT -> ANALYZING
    assert ProjectStateMachine.can_transition(sample_project.status, "analyze")
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "analyze"
    )
    assert sample_project.status == ProjectStatus.ANALYZING

    # 2. ANALYZING -> AWAITING_CLARIFICATION (blocking gaps found)
    assert ProjectStateMachine.can_transition(
        sample_project.status, "blocking_gaps_found"
    )
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "blocking_gaps_found"
    )
    assert sample_project.status == ProjectStatus.AWAITING_CLARIFICATION

    # 3. AWAITING_CLARIFICATION -> ANALYZING (answers submitted)
    assert ProjectStateMachine.can_transition(
        sample_project.status, "answers_submitted"
    )
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "answers_submitted"
    )
    assert sample_project.status == ProjectStatus.ANALYZING

    # 4. ANALYZING -> READY_TO_GENERATE (no blocking gaps)
    assert ProjectStateMachine.can_transition(
        sample_project.status, "no_blocking_gaps"
    )
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "no_blocking_gaps"
    )
    assert sample_project.status == ProjectStatus.READY_TO_GENERATE

    # 5. READY_TO_GENERATE -> GENERATING (generate)
    assert ProjectStateMachine.can_transition(sample_project.status, "generate")
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "generate"
    )
    assert sample_project.status == ProjectStatus.GENERATING

    # 6. GENERATING -> GENERATED (quality passed)
    assert ProjectStateMachine.can_transition(
        sample_project.status, "quality_passed"
    )
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "quality_passed"
    )
    assert sample_project.status == ProjectStatus.GENERATED

    # 7. GENERATED -> ANALYZING (answer or source changed)
    assert ProjectStateMachine.can_transition(
        sample_project.status, "answer_or_source_changed"
    )
    sample_project.status = ProjectStateMachine.transition(
        sample_project.status, "answer_or_source_changed"
    )
    assert sample_project.status == ProjectStatus.ANALYZING


def test_generation_only_allowed_from_ready_to_generate():
    """Verify that 'generate' is strictly rejected from non-ready states."""
    disallowed_states = [
        ProjectStatus.DRAFT,
        ProjectStatus.ANALYZING,
        ProjectStatus.AWAITING_CLARIFICATION,
        ProjectStatus.GENERATING,
        ProjectStatus.GENERATED,
        ProjectStatus.FAILED,
    ]

    for status in disallowed_states:
        assert not ProjectStateMachine.can_transition(status, "generate")
        with pytest.raises(InvalidTransitionError) as exc_info:
            ProjectStateMachine.transition(status, "generate")
        assert "Generation is only allowed when status is READY_TO_GENERATE" in str(
            exc_info.value
        ) or "Cannot transition" in str(exc_info.value)

    # Allowed strictly from READY_TO_GENERATE
    assert ProjectStateMachine.can_transition(
        ProjectStatus.READY_TO_GENERATE, "generate"
    )
    result = ProjectStateMachine.transition(
        ProjectStatus.READY_TO_GENERATE, "generate"
    )
    assert result == ProjectStatus.GENERATING


def test_failed_retry_to_previous_valid_state():
    """Test the FAILED -> retry -> previous_valid_state recovery flow."""
    # GENERATING -> FAILED
    status = ProjectStateMachine.transition(
        ProjectStatus.GENERATING, "generation_or_quality_failed"
    )
    assert status == ProjectStatus.FAILED

    # Successful retry back to READY_TO_GENERATE
    recovered = ProjectStateMachine.transition(
        current=ProjectStatus.FAILED,
        event="retry",
        previous_valid_state=ProjectStatus.READY_TO_GENERATE,
    )
    assert recovered == ProjectStatus.READY_TO_GENERATE

    # Successful retry back to ANALYZING
    recovered_analyzing = ProjectStateMachine.transition(
        current=ProjectStatus.FAILED,
        event="retry",
        previous_valid_state=ProjectStatus.ANALYZING,
    )
    assert recovered_analyzing == ProjectStatus.ANALYZING


def test_failed_retry_validation_errors():
    """Ensure invalid retries from FAILED raise InvalidTransitionError."""
    # Retrying without previous_valid_state must fail
    with pytest.raises(InvalidTransitionError) as exc_info:
        ProjectStateMachine.transition(ProjectStatus.FAILED, "retry")
    assert "without providing previous_valid_state" in str(exc_info.value)

    # Retrying to FAILED itself must fail
    with pytest.raises(InvalidTransitionError) as exc_info:
        ProjectStateMachine.transition(
            ProjectStatus.FAILED,
            "retry",
            previous_valid_state=ProjectStatus.FAILED,
        )
    assert "previous_valid_state cannot be FAILED" in str(exc_info.value)

    # Trying any event other than 'retry' from FAILED must fail
    with pytest.raises(InvalidTransitionError) as exc_info:
        ProjectStateMachine.transition(ProjectStatus.FAILED, "analyze")
    assert "FAILED status can only transition via 'retry'" in str(exc_info.value)


def test_allowed_events():
    """Verify allowed_events returns exact defined events for every state."""
    assert ProjectStateMachine.allowed_events(ProjectStatus.DRAFT) == ["analyze"]
    assert set(
        ProjectStateMachine.allowed_events(ProjectStatus.ANALYZING)
    ) == {"blocking_gaps_found", "no_blocking_gaps"}
    assert ProjectStateMachine.allowed_events(
        ProjectStatus.AWAITING_CLARIFICATION
    ) == ["answers_submitted"]
    assert ProjectStateMachine.allowed_events(
        ProjectStatus.READY_TO_GENERATE
    ) == ["generate"]
    assert set(
        ProjectStateMachine.allowed_events(ProjectStatus.GENERATING)
    ) == {"quality_passed", "generation_or_quality_failed"}
    assert ProjectStateMachine.allowed_events(ProjectStatus.GENERATED) == [
        "answer_or_source_changed"
    ]
    assert ProjectStateMachine.allowed_events(ProjectStatus.FAILED) == ["retry"]


def test_instance_and_enum_compatibility():
    """Ensure state machine supports instance invocation and Enum event args."""
    sm = ProjectStateMachine()
    next_state = sm.transition(ProjectStatus.DRAFT, ProjectEvent.ANALYZE)
    assert next_state == ProjectStatus.ANALYZING
    assert sm.can_transition(ProjectStatus.DRAFT, ProjectEvent.ANALYZE)
