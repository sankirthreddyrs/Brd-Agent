import logging
from typing import Optional, Sequence
import uuid

from app.llm.llm_client import LLMClient, GeminiClient
from app.llm.prompts import build_extraction_prompt
from app.llm.schemas import ExtractionResult
from app.models.assumption import Assumption
from app.models.document import SourceChunk
from app.models.requirement import Requirement

logger = logging.getLogger(__name__)


def extract_requirements(
    idea_text: Optional[str] = None,
    existing_requirements: Optional[Sequence[Requirement]] = None,
    answered_context: Optional[str] = None,
    chunks: Optional[Sequence[SourceChunk]] = None,
    gemini_client: Optional[LLMClient] = None,
    project_id: str = "project-default",
    llm_client: Optional[LLMClient] = None,
) -> tuple[list[Requirement], list[Assumption]]:
    """Extract candidate requirements and proposed assumptions from a business idea and source chunks.

    Preserves IDs for existing requirements where updated, generates new clean
    unique IDs for genuinely new requirements, strictly validates chunk citations,
    drops hallucinated chunk IDs, and attaches trace_refs.

    Args:
        idea_text: Optional user input business idea or feature description.
        existing_requirements: Collection of previously extracted requirements, if any.
        answered_context: Serialized text of answered clarification questions.
        chunks: Optional collection of source document chunks for grounding.
        gemini_client: Configured LLM client instance (legacy parameter).
        project_id: Associated project identifier.
        llm_client: Configured provider-neutral LLM client instance.

    Returns:
        Tuple of (list of Requirement, list of Assumption).
    """
    client = llm_client or gemini_client or LLMClient()
    existing_reqs = list(existing_requirements) if existing_requirements else []
    valid_chunks = list(chunks) if chunks else []

    # Map existing requirements by ID and by normalized title for matching
    existing_id_set = {r.id for r in existing_reqs}
    existing_by_title = {r.title.strip().lower(): r for r in existing_reqs}

    # Map valid chunks by both ID (UUID) and label (e.g. CHUNK-...)
    chunk_by_id_or_label: dict[str, SourceChunk] = {}
    for c in valid_chunks:
        chunk_by_id_or_label[c.id] = c
        if getattr(c, "chunk_label", None):
            chunk_by_id_or_label[c.chunk_label] = c
        if c.heading and (c.heading.startswith("CHUNK-") or c.heading.startswith("chunk-")):
            chunk_by_id_or_label[c.heading] = c

    prompt = build_extraction_prompt(
        idea_text=idea_text,
        existing_requirements=existing_reqs,
        answered_context=answered_context,
        chunks=valid_chunks if valid_chunks else None,
    )

    result: ExtractionResult = client.generate_structured(
        prompt=prompt,
        response_schema=ExtractionResult,
    )

    processed_requirements: list[Requirement] = []
    used_ids: set[str] = set()

    for candidate in result.requirements:
        norm_title = candidate.title.strip().lower()

        # Check if matches an existing requirement to preserve its ID
        if candidate.id in existing_id_set:
            assigned_id = candidate.id
        elif norm_title in existing_by_title:
            assigned_id = existing_by_title[norm_title].id
        elif candidate.id and candidate.id not in used_ids and candidate.id.startswith("REQ-"):
            assigned_id = candidate.id
        else:
            assigned_id = f"REQ-{uuid.uuid4().hex[:6].upper()}"

        used_ids.add(assigned_id)

        # Validate source_chunk_ids against provided valid chunks; strip hallucinated IDs
        raw_chunk_ids = getattr(candidate, "source_chunk_ids", []) or []
        sanitized_chunk_ids: list[str] = []
        for cid in raw_chunk_ids:
            chunk_obj = chunk_by_id_or_label.get(cid)
            if chunk_obj:
                target_id = chunk_obj.id
                if target_id not in sanitized_chunk_ids:
                    sanitized_chunk_ids.append(target_id)
            else:
                logger.warning(
                    "Dropping hallucinated source_chunk_id '%s' for requirement '%s'",
                    cid,
                    candidate.title,
                )

        # Populate trace_refs for valid chunk citations: CHUNK:{chunk_id} and DOC:{doc_id}:p{page}
        updated_trace_refs = list(candidate.trace_refs or [])
        for cid in sanitized_chunk_ids:
            chunk_ref = f"CHUNK:{cid}"
            if chunk_ref not in updated_trace_refs:
                updated_trace_refs.append(chunk_ref)

            chunk_obj = chunk_by_id_or_label.get(cid)
            if chunk_obj and chunk_obj.page_number is not None:
                doc_ref = f"DOC:{chunk_obj.document_id}:p{chunk_obj.page_number}"
                if doc_ref not in updated_trace_refs:
                    updated_trace_refs.append(doc_ref)

        # Fallback grounding for requirements extracted from initial idea_text
        if not updated_trace_refs and not sanitized_chunk_ids and idea_text and idea_text.strip():
            updated_trace_refs.append("IDEA")

        processed_requirements.append(
            candidate.model_copy(
                update={
                    "id": assigned_id,
                    "source_chunk_ids": sanitized_chunk_ids,
                    "trace_refs": updated_trace_refs,
                }
            )
        )

    processed_assumptions: list[Assumption] = []
    for candidate_asm in result.proposed_assumptions:
        asm_id = candidate_asm.id
        if not asm_id or not asm_id.startswith("ASM-"):
            asm_id = f"ASM-{uuid.uuid4().hex[:6].upper()}"

        processed_assumptions.append(
            candidate_asm.model_copy(
                update={
                    "id": asm_id,
                    "project_id": project_id,
                }
            )
        )

    return processed_requirements, processed_assumptions


# Explicit alias for callers expecting extract_requirements_and_assumptions
extract_requirements_and_assumptions = extract_requirements

