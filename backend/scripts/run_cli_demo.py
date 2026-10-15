"""Interactive CLI demonstration script for the BRD Agent AI Core Loop.

Allows interactive testing of requirement extraction, deterministic validation,
question generation, and answer merging from a terminal.
"""

from datetime import datetime, timezone
import json
import os
import sys
import uuid

# Ensure backend root is on sys.path when running script directly
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.orchestrator import BRDOrchestrator, WorkflowResult
from app.llm.gemini_client import GeminiClient
from app.models.answer import Answer
from app.models.project import ProjectStatus
from app.models.question import Question
from app.models.requirement import Requirement


def print_banner() -> None:
    print("=" * 75)
    print(">> BRD AGENT - AI CORE LOOP INTERACTIVE DEMO")
    print("=" * 75)
    print("This script demonstrates:")
    print("  1. Extracting candidate requirements via Gemini LLM")
    print("  2. Running deterministic Python completeness checks (pure rule engine)")
    print("  3. Generating prioritized clarification questions for blocking gaps")
    print("  4. Merging user answers and re-evaluating readiness until READY_TO_GENERATE")
    print("=" * 75)


def main() -> None:
    print_banner()

    # Verify Groq API key is available
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[ERROR] GROQ_API_KEY environment variable is missing.")
        print("Please configure your Groq API key in backend/.env or your environment.")
        sys.exit(1)

    gemini_client = GeminiClient()
    orchestrator = BRDOrchestrator(gemini_client=gemini_client)

    # 1. Prompt for business idea
    default_idea = "I want to build an app where users can book appointments with local service providers."
    print("\nEnter your business idea (or press Enter to use default incomplete sample):")
    user_input = input("> ").strip()
    idea_text = user_input if user_input else default_idea

    print(f"\n[INFO] Starting analysis for idea:\n\"\"\"{idea_text}\"\"\"\n")

    # In-memory tracking state
    requirements: list[Requirement] = []
    historical_questions: list[Question] = []
    answers: list[Answer] = []
    asked_paths: set[str] = set()

    max_rounds = 5
    current_round = 1

    while current_round <= max_rounds:
        print(f"\n--- [ ROUND {current_round}/{max_rounds} ] Running Analysis Loop ---")
        result: WorkflowResult = orchestrator.run_analysis(
            idea_text=idea_text,
            existing_requirements=requirements,
            answered_questions=historical_questions,
            answers=answers,
            already_asked_field_paths=asked_paths,
            project_id="demo-proj-001",
        )

        requirements = result.requirements

        print(f"\n[Extracted Requirements]: {len(result.requirements)}")
        for r in result.requirements:
            print(f"  * [{r.id}] ({r.type.value.upper()}) {r.title}")
            print(f"      Statement: {r.statement}")
            print(f"      Actor: {r.actor or '<MISSING>'} | Outcome: {r.outcome or '<MISSING>'}")
            print(f"      Confidence: {r.confidence:.2f} | Priority: {r.priority.value}")
            if r.acceptance_criteria:
                print(f"      Criteria: {', '.join(r.acceptance_criteria)}")
            if r.trace_refs:
                print(f"      Trace Refs: {r.trace_refs}")

        print(f"\n[Validation Findings]: {len(result.validation_result.issues)} issue(s)")
        for issue in result.validation_result.issues:
            marker = "[BLOCKER]" if issue.severity.value == "blocker" else "[WARN]"
            print(f"  {marker} {issue.code} on '{issue.field_path}': {issue.message}")

        if result.assumptions:
            print(f"\n[Active Assumptions]: {len(result.assumptions)}")
            for asm in result.assumptions:
                print(f"  * [{asm.id}] ({asm.impact.value}) {asm.statement}")

        print(f"\n[Status]: {result.next_status.value}")

        if result.next_status == ProjectStatus.READY_TO_GENERATE:
            print("\n" + "=" * 75)
            print("[SUCCESS] ALL BLOCKING GAPS RESOLVED! Project is READY_TO_GENERATE.")
            print("=" * 75)

            final_output = {
                "requirements": [r.model_dump() for r in result.requirements],
                "assumptions": [a.model_dump() for a in result.assumptions],
            }
            print("\nFinal Requirements & Assumptions JSON:")
            print(json.dumps(final_output, indent=2, default=str))
            break

        # Process open questions
        if not result.open_questions:
            print("\n[NOTE] No open questions generated, but status is not READY_TO_GENERATE.")
            break

        print(f"\n[Clarification Questions Needed]: ({len(result.open_questions)} open)")
        new_answers_this_round: list[Answer] = []

        for idx, q in enumerate(result.open_questions, start=1):
            historical_questions.append(q)
            asked_paths.add(q.field_path)

            print(f"\nQuestion {idx}/{len(result.open_questions)}:")
            print(f"  Prompt: {q.question_text}")
            print(f"  Why It Matters: {q.why_it_matters}")
            print(f"  Impact: {q.impact}/3 | Gap Conf: {q.gap_confidence} | Priority: {q.priority:.2f}")
            if q.options:
                print(f"  Options: {', '.join(q.options)}")

            user_ans = input(f"Your answer (format={q.answer_format.value}): ").strip()
            if not user_ans:
                user_ans = "Standard default user" if "actor" in q.field_path else "Verified and approved"

            ans_obj = Answer(
                id=f"ANS-{uuid.uuid4().hex[:6].upper()}",
                project_id="demo-proj-001",
                question_id=q.id,
                value=user_ans,
                answered_at=datetime.now(timezone.utc),
            )
            new_answers_this_round.append(ans_obj)
            answers.append(ans_obj)

        current_round += 1

    if current_round > max_rounds:
        print(f"\n[WARNING] Reached maximum round limit of {max_rounds} rounds.")


if __name__ == "__main__":
    main()
