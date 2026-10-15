"""Deterministic finite state machine for project lifecycle management.

Enforces transition rules defined in the BRD Agent specification:
  DRAFT --(analyze)--> ANALYZING
  ANALYZING --(blocking_gaps_found)--> AWAITING_CLARIFICATION
  ANALYZING --(no_blocking_gaps)--> READY_TO_GENERATE
  AWAITING_CLARIFICATION --(answers_submitted)--> ANALYZING
  READY_TO_GENERATE --(generate)--> GENERATING
  GENERATING --(quality_passed)--> GENERATED
  GENERATING --(generation_or_quality_failed)--> FAILED
  GENERATED --(answer_or_source_changed)--> ANALYZING
  FAILED --(retry)--> <previous_valid_state>
"""

from enum import Enum
from typing import Optional, Union

from app.models.project import ProjectStatus


class ProjectEvent(str, Enum):
    """Named lifecycle events that trigger transitions."""

    ANALYZE = "analyze"
    BLOCKING_GAPS_FOUND = "blocking_gaps_found"
    NO_BLOCKING_GAPS = "no_blocking_gaps"
    ANSWERS_SUBMITTED = "answers_submitted"
    GENERATE = "generate"
    QUALITY_PASSED = "quality_passed"
    GENERATION_OR_QUALITY_FAILED = "generation_or_quality_failed"
    ANSWER_OR_SOURCE_CHANGED = "answer_or_source_changed"
    RETRY = "retry"


class InvalidTransitionError(Exception):
    """Raised when an illegal project status transition is attempted."""

    def __init__(
        self,
        current: Union[ProjectStatus, str],
        event: Union[str, ProjectEvent],
        message: Optional[str] = None,
    ) -> None:
        self.current = current
        self.event = event
        curr_val = current.value if hasattr(current, "value") else str(current)
        evt_val = event.value if hasattr(event, "value") else str(event)
        self.message = (
            message
            or f"Invalid transition: cannot process event '{evt_val}' from status '{curr_val}'."
        )
        super().__init__(self.message)


# Transition table mapping current_state -> {event: next_state}
# FAILED maps 'retry' to None because its destination is dynamic (previous_valid_state).
TRANSITION_TABLE: dict[ProjectStatus, dict[str, Optional[ProjectStatus]]] = {
    ProjectStatus.DRAFT: {
        ProjectEvent.ANALYZE.value: ProjectStatus.ANALYZING,
    },
    ProjectStatus.ANALYZING: {
        ProjectEvent.BLOCKING_GAPS_FOUND.value: ProjectStatus.AWAITING_CLARIFICATION,
        ProjectEvent.NO_BLOCKING_GAPS.value: ProjectStatus.READY_TO_GENERATE,
    },
    ProjectStatus.AWAITING_CLARIFICATION: {
        ProjectEvent.ANSWERS_SUBMITTED.value: ProjectStatus.ANALYZING,
    },
    ProjectStatus.READY_TO_GENERATE: {
        ProjectEvent.GENERATE.value: ProjectStatus.GENERATING,
    },
    ProjectStatus.GENERATING: {
        ProjectEvent.QUALITY_PASSED.value: ProjectStatus.GENERATED,
        ProjectEvent.GENERATION_OR_QUALITY_FAILED.value: ProjectStatus.FAILED,
    },
    ProjectStatus.GENERATED: {
        ProjectEvent.ANSWER_OR_SOURCE_CHANGED.value: ProjectStatus.ANALYZING,
    },
    ProjectStatus.COMPLETED: {
        ProjectEvent.ANSWER_OR_SOURCE_CHANGED.value: ProjectStatus.ANALYZING,
    },
    ProjectStatus.FAILED: {
        ProjectEvent.RETRY.value: None,  # Dynamically points to previous_valid_state
    },
}


class ProjectStateMachine:
    """State machine governing Project status transitions using a rule engine.

    Methods can be called as class methods or on instances.
    """

    @staticmethod
    def _coerce_status(status: Union[ProjectStatus, str]) -> ProjectStatus:
        """Coerce a string or ProjectStatus into a validated ProjectStatus enum."""
        if isinstance(status, ProjectStatus):
            return status
        try:
            return ProjectStatus(str(status))
        except ValueError as exc:
            raise InvalidTransitionError(
                current=str(status),
                event="<unknown>",
                message=f"Unknown ProjectStatus '{status}'.",
            ) from exc

    @staticmethod
    def _coerce_event(event: Union[str, ProjectEvent]) -> str:
        """Coerce an event into its string value representation."""
        if hasattr(event, "value"):
            return str(event.value)
        return str(event)

    @classmethod
    def allowed_events(cls, current: Union[ProjectStatus, str]) -> list[str]:
        """Return the list of valid events permitted from the current project status.

        Args:
            current: Current ProjectStatus enum or string name.

        Returns:
            List of allowed event string names.
        """
        status = cls._coerce_status(current)
        return list(TRANSITION_TABLE.get(status, {}).keys())

    @classmethod
    def can_transition(
        cls,
        current: Union[ProjectStatus, str],
        event: Union[str, ProjectEvent],
        previous_valid_state: Optional[Union[ProjectStatus, str]] = None,
        target_status: Optional[Union[ProjectStatus, str]] = None,
    ) -> bool:
        """Check whether a transition is allowed from the current state with the given event.

        Args:
            current: Current ProjectStatus enum or string.
            event: Event string or ProjectEvent.
            previous_valid_state: Optional previous state (checked if transitioning from FAILED).
            target_status: Optional desired target ProjectStatus.

        Returns:
            True if the transition is permissible, False otherwise.
        """
        try:
            status = cls._coerce_status(current)
        except InvalidTransitionError:
            return False

        evt = cls._coerce_event(event)
        target = cls._coerce_status(target_status) if target_status is not None else None

        # Allow idempotent self-transition if explicitly targeting GENERATING
        if status == ProjectStatus.GENERATING and target == ProjectStatus.GENERATING:
            return True

        # Special allowance: GENERATING -> COMPLETED
        if status == ProjectStatus.GENERATING and (target == ProjectStatus.COMPLETED or evt == "completed"):
            return True

        transitions_for_state = TRANSITION_TABLE.get(status, {})

        if evt not in transitions_for_state:
            return False

        # If retrying from FAILED, validate previous_valid_state if provided
        if status == ProjectStatus.FAILED and evt == ProjectEvent.RETRY.value:
            if previous_valid_state is not None:
                try:
                    prev = cls._coerce_status(previous_valid_state)
                    # previous_valid_state cannot itself be FAILED
                    return prev != ProjectStatus.FAILED
                except InvalidTransitionError:
                    return False
            # When previous_valid_state is not supplied, valid if target is READY_TO_GENERATE
            if target == ProjectStatus.READY_TO_GENERATE:
                return True
            return True

        return True

    @classmethod
    def transition(
        cls,
        current: Union[ProjectStatus, str],
        event: Union[str, ProjectEvent],
        previous_valid_state: Optional[Union[ProjectStatus, str]] = None,
        target_status: Optional[Union[ProjectStatus, str]] = None,
    ) -> ProjectStatus:
        """Execute a state transition, returning the new ProjectStatus.

        Args:
            current: Current ProjectStatus enum or string.
            event: Event string or ProjectEvent triggering the transition.
            previous_valid_state: Required when current state is FAILED and event is 'retry'.
                Represents the stored valid state before the failure occurred.
            target_status: Optional desired target ProjectStatus.

        Returns:
            The resulting ProjectStatus.

        Raises:
            InvalidTransitionError: If the transition is not allowed under the BRD lifecycle rules.
        """
        status = cls._coerce_status(current)
        evt = cls._coerce_event(event)
        target = cls._coerce_status(target_status) if target_status is not None else None

        # Idempotent self-transition if targeting GENERATING
        if status == ProjectStatus.GENERATING and target == ProjectStatus.GENERATING:
            return ProjectStatus.GENERATING

        # Enforce generation rule: generation is strictly allowed only from READY_TO_GENERATE
        if evt == ProjectEvent.GENERATE.value and status != ProjectStatus.READY_TO_GENERATE:
            raise InvalidTransitionError(
                current=status,
                event=evt,
                message=(
                    f"Generation is only allowed when status is READY_TO_GENERATE. "
                    f"Current status is '{status.value}'."
                ),
            )

        # Enforce recovery from FAILED strictly via 'retry' with valid previous state
        if status == ProjectStatus.FAILED:
            if evt != ProjectEvent.RETRY.value:
                raise InvalidTransitionError(
                    current=status,
                    event=evt,
                    message=f"FAILED status can only transition via 'retry'. Received '{evt}'.",
                )
            if previous_valid_state is None and target != ProjectStatus.READY_TO_GENERATE:
                raise InvalidTransitionError(
                    current=status,
                    event=evt,
                    message="Cannot retry from FAILED without providing previous_valid_state.",
                )
            if previous_valid_state is not None:
                prev = cls._coerce_status(previous_valid_state)
                if prev == ProjectStatus.FAILED:
                    raise InvalidTransitionError(
                        current=status,
                        event=evt,
                        message="previous_valid_state cannot be FAILED.",
                    )
                # If failure occurred during GENERATING, recovering cleanly restores to READY_TO_GENERATE
                if prev == ProjectStatus.GENERATING:
                    return ProjectStatus.READY_TO_GENERATE
                return prev
            if target == ProjectStatus.READY_TO_GENERATE:
                return ProjectStatus.READY_TO_GENERATE

        # Special allowance: GENERATING -> COMPLETED
        if status == ProjectStatus.GENERATING and (target == ProjectStatus.COMPLETED or evt == "completed"):
            return ProjectStatus.COMPLETED

        transitions_for_state = TRANSITION_TABLE.get(status, {})

        if evt not in transitions_for_state:
            allowed = cls.allowed_events(status)
            raise InvalidTransitionError(
                current=status,
                event=evt,
                message=(
                    f"Cannot transition from '{status.value}' via event '{evt}'. "
                    f"Allowed events: {allowed}"
                ),
            )

        next_status = transitions_for_state[evt]
        assert next_status is not None, f"Expected non-null target status for {status} + {evt}"
        return next_status
