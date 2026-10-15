"""Local lifecycle test and demonstration script for the BRD Agent.

Executes a full lifecycle walkthrough of a Project instance moving through
its defined states, demonstrating validation, transitions, and recovery.
"""

from datetime import datetime, timezone
import sys

from app.core.state_machine import InvalidTransitionError, ProjectEvent, ProjectStateMachine
from app.models import (
    AnswerFormat,
    ImpactLevel,
    Priority,
    Project,
    ProjectStatus,
    Question,
    Requirement,
    RequirementType,
    ValidationIssue,
    ValidationResult,
    Severity,
)
from app.templates.brd_template import build_brd_skeleton


def main() -> None:
    print("=" * 70)
    print(">> BRD AGENT - CORE FOUNDATION STATE MACHINE & MODEL DEMO")
    print("=" * 70)

    # 1. Initialize project
    now = datetime.now(timezone.utc)
    project = Project(
        id="proj-demo-001",
        title="Enterprise Expense Approval Automation",
        idea="Automate receipt ingestion, policy validation, and tier-based manager approvals.",
        status=ProjectStatus.DRAFT,
        input_revision=1,
        created_at=now,
        updated_at=now,
    )
    print(f"\n[1] Created Project: '{project.title}'")
    print(f"    Current Status: {project.status.value}")

    # 2. Transition: DRAFT -> ANALYZING
    project.status = ProjectStateMachine.transition(project.status, "analyze")
    print(f"\n[2] Triggered event 'analyze'")
    print(f"    Current Status: {project.status.value}")

    # 3. Simulate gap detection: ANALYZING -> AWAITING_CLARIFICATION
    question = Question(
        id="Q-001",
        project_id=project.id,
        field_path="business_rules.approval_limits",
        question_text="What is the maximum dollar threshold for single-manager approval?",
        why_it_matters="Determines policy routing thresholds in functional requirements.",
        answer_format=AnswerFormat.NUMBER,
        impact=3,
        gap_confidence=0.9,
        created_at=now,
    )
    priority = question.compute_priority()
    print(f"\n[3] Detected Gap Question: '{question.question_text}'")
    print(f"    Impact={question.impact}, Confidence={question.gap_confidence} -> Priority={priority:.2f}")

    project.status = ProjectStateMachine.transition(project.status, "blocking_gaps_found")
    print(f"    Current Status: {project.status.value}")

    # 4. User answers: AWAITING_CLARIFICATION -> ANALYZING
    project.status = ProjectStateMachine.transition(project.status, "answers_submitted")
    print(f"\n[4] User submitted answers. Triggered 'answers_submitted'")
    print(f"    Current Status: {project.status.value}")

    # 5. No more blocking gaps: ANALYZING -> READY_TO_GENERATE
    validation = ValidationResult(issues=[])
    assert not validation.has_blockers
    project.status = ProjectStateMachine.transition(project.status, "no_blocking_gaps")
    print(f"\n[5] Analysis completed without blocking gaps.")
    print(f"    Current Status: {project.status.value}")

    # 6. Guard check: Ensure invalid transition fails
    print("\n[6] Testing transition guard: Attempting illegal event 'generate' from DRAFT (simulation)...")
    try:
        ProjectStateMachine.transition(ProjectStatus.DRAFT, "generate")
    except InvalidTransitionError as err:
        print(f"    SUCCESS: Guard blocked illegal transition: {err}")

    # 7. Generate BRD: READY_TO_GENERATE -> GENERATING
    project.status = ProjectStateMachine.transition(project.status, "generate")
    print(f"\n[7] Triggered 'generate'")
    print(f"    Current Status: {project.status.value}")

    # 8. Quality Passed: GENERATING -> GENERATED
    project.status = ProjectStateMachine.transition(project.status, "quality_passed")
    print(f"\n[8] Automated quality checks passed. Triggered 'quality_passed'")
    print(f"    Current Status: {project.status.value}")

    # 9. Build sample skeleton
    skeleton = build_brd_skeleton(project)
    print(f"\n[9] Generated BRD Skeleton:")
    print(f"    Title: {skeleton['title']}")
    print(f"    Version: {skeleton['version']}")
    print(f"    Traceability Note: {skeleton['traceability_note']}")

    # 10. Simulate subsequent edit: GENERATED -> ANALYZING
    project.status = ProjectStateMachine.transition(project.status, "answer_or_source_changed")
    print(f"\n[10] Source document updated post-generation. Triggered 'answer_or_source_changed'")
    print(f"     Current Status: {project.status.value}")

    # 11. Test Failure recovery path: GENERATING -> FAILED -> retry
    print("\n[11] Testing Failure & Retry Recovery Flow...")
    prev_state = ProjectStatus.READY_TO_GENERATE
    failed_state = ProjectStateMachine.transition(ProjectStatus.GENERATING, "generation_or_quality_failed")
    print(f"     Transitioned to: {failed_state.value}")
    recovered_state = ProjectStateMachine.transition(
        current=failed_state,
        event="retry",
        previous_valid_state=prev_state,
    )
    print(f"     Successfully recovered via 'retry' back to: {recovered_state.value}")

    print("\n" + "=" * 70)
    print("[OK] ALL LIFECYCLE TRANSITIONS AND MODEL CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
