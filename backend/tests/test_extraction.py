"""Unit tests for document chunk-grounded requirement extraction and traceability verification."""

from unittest.mock import MagicMock
import pytest

from app.core.extraction import extract_requirements, extract_requirements_and_assumptions
from app.llm.prompts import build_extraction_prompt
from app.llm.schemas import ExtractedRequirementDraft, ExtractionResult
from app.models.document import SourceChunk
from app.models.requirement import Priority, Requirement, RequirementType


class MockLLMClient:
    """Mock LLM client returning predetermined ExtractionResult."""

    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.last_prompt: str | None = None

    def generate_structured(self, prompt: str, response_schema: type):
        self.last_prompt = prompt
        return self.result


def test_extraction_with_chunks_populates_trace_refs():
    """Verify that valid chunk citations populate source_chunk_ids and trace_refs."""
    chunk1 = SourceChunk(
        id="CHUNK-DOC1-0",
        document_id="doc-uuid-1",
        project_id="proj-1",
        text="The system shall provide biometric authentication for all staff members.",
        page_number=3,
        heading="Access Control",
        chunk_index=0,
    )
    chunk2 = SourceChunk(
        id="CHUNK-DOC1-1",
        document_id="doc-uuid-1",
        project_id="proj-1",
        text="All customer financial transactions must complete within 200ms latency.",
        page_number=5,
        heading="Performance SLA",
        chunk_index=1,
    )

    draft_req1 = ExtractedRequirementDraft(
        id="REQ-001",
        type=RequirementType.FUNCTIONAL,
        title="Biometric Staff Authentication",
        statement="The system shall authenticate all staff using biometric verification.",
        actor="Staff Member",
        outcome="Secure access granted",
        priority=Priority.MUST,
        acceptance_criteria=["Fingerprint or facial recognition verified against staff directory."],
        confidence=0.98,
        source_chunk_ids=["CHUNK-DOC1-0"],
        rationale="Specified directly in section Access Control on page 3.",
    )

    draft_req2 = ExtractedRequirementDraft(
        id="REQ-002",
        type=RequirementType.NONFUNCTIONAL,
        title="Transaction Processing Latency",
        statement="All customer financial transactions must complete within 200ms.",
        outcome="Fast transaction processing",
        priority=Priority.MUST,
        acceptance_criteria=["99.9% of transactions respond under 200ms under 500 RPS load."],
        confidence=0.95,
        source_chunk_ids=["CHUNK-DOC1-1"],
        rationale="Specified in performance SLAs on page 5.",
    )

    mock_client = MockLLMClient(
        ExtractionResult(requirements=[draft_req1, draft_req2], proposed_assumptions=[])
    )

    reqs, assumptions = extract_requirements_and_assumptions(
        idea_text="Enterprise payment portal with high security",
        chunks=[chunk1, chunk2],
        gemini_client=mock_client,
        project_id="proj-1",
    )

    assert len(reqs) == 2
    # Verify Req 1 trace refs
    req1 = reqs[0]
    assert req1.source_chunk_ids == ["CHUNK-DOC1-0"]
    assert "CHUNK:CHUNK-DOC1-0" in req1.trace_refs
    assert "DOC:doc-uuid-1:p3" in req1.trace_refs
    assert req1.rationale == "Specified directly in section Access Control on page 3."

    # Verify Req 2 trace refs
    req2 = reqs[1]
    assert req2.source_chunk_ids == ["CHUNK-DOC1-1"]
    assert "CHUNK:CHUNK-DOC1-1" in req2.trace_refs
    assert "DOC:doc-uuid-1:p5" in req2.trace_refs


def test_hallucinated_chunk_ids_filtered_out():
    """Verify that hallucinated or non-existent chunk IDs are stripped from source_chunk_ids and trace_refs."""
    real_chunk = SourceChunk(
        id="CHUNK-VALID-0",
        document_id="doc-real",
        project_id="proj-1",
        text="Customer records shall be retained for 7 years according to compliance policies.",
        page_number=12,
        chunk_index=0,
    )

    # LLM returns one valid chunk ID and one hallucinated chunk ID
    draft_req = ExtractedRequirementDraft(
        id="REQ-001",
        type=RequirementType.CONSTRAINT,
        title="Record Retention Policy",
        statement="Customer records shall be retained for 7 years.",
        priority=Priority.MUST,
        confidence=0.9,
        source_chunk_ids=["CHUNK-VALID-0", "CHUNK-HALLUCINATED-999"],
        rationale="Compliance policy",
    )

    mock_client = MockLLMClient(
        ExtractionResult(requirements=[draft_req], proposed_assumptions=[])
    )

    reqs, _ = extract_requirements(
        idea_text="Compliance constraints",
        chunks=[real_chunk],
        gemini_client=mock_client,
        project_id="proj-1",
    )

    assert len(reqs) == 1
    req = reqs[0]
    # Hallucinated ID must be filtered out
    assert req.source_chunk_ids == ["CHUNK-VALID-0"]
    assert "CHUNK:CHUNK-VALID-0" in req.trace_refs
    assert "DOC:doc-real:p12" in req.trace_refs
    assert "CHUNK:CHUNK-HALLUCINATED-999" not in req.trace_refs


def test_pure_idea_text_backward_compatibility():
    """Verify that pure idea-text extraction continues to function seamlessly without chunks."""
    draft_req = ExtractedRequirementDraft(
        id="REQ-001",
        type=RequirementType.FUNCTIONAL,
        title="User Registration",
        statement="The system shall allow new users to register an account.",
        actor="Prospective Customer",
        outcome="Account created",
        priority=Priority.MUST,
        acceptance_criteria=["User enters valid email, password, and completes verification."],
        confidence=1.0,
        source_chunk_ids=[],
    )

    mock_client = MockLLMClient(
        ExtractionResult(requirements=[draft_req], proposed_assumptions=[])
    )

    reqs, assumptions = extract_requirements(
        idea_text="I want an e-commerce platform where customers can sign up and buy products.",
        chunks=None,
        gemini_client=mock_client,
        project_id="proj-1",
    )

    assert len(reqs) == 1
    req = reqs[0]
    assert req.title == "User Registration"
    assert req.source_chunk_ids == []
    assert req.trace_refs == ["IDEA"]


def test_build_extraction_prompt_formats_chunks():
    """Verify build_extraction_prompt includes chunk headers, document IDs, page numbers, and instructions."""
    chunk = SourceChunk(
        id="CHUNK-TEST-42",
        document_id="doc-specs-pdf",
        project_id="proj-1",
        text="Payment gateway integration must support 3D Secure 2.0 protocol.",
        page_number=8,
        heading="Payment Gateway",
        chunk_index=3,
    )

    prompt = build_extraction_prompt(
        idea_text="Payment processing service",
        chunks=[chunk],
    )

    assert "[CHUNK_ID: CHUNK-TEST-42 | Doc: doc-specs-pdf | Page: 8 | Section: Payment Gateway]" in prompt
    assert "Payment gateway integration must support 3D Secure 2.0 protocol." in prompt
    assert "STRICT SOURCE CHUNK CITATIONS & TRACEABILITY" in prompt
    assert "source_chunk_ids" in prompt
