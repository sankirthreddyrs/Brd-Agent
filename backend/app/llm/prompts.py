"""Prompt template functions for LLM operations in the BRD Agent.

All prompt templates are implemented as pure, deterministic string generator functions.
"""

import json
from typing import Any, Optional

from app.models.document import SourceChunk
from app.models.requirement import Requirement
from app.models.validation import ValidationIssue


def build_extraction_prompt(
    idea_text: Optional[str] = None,
    existing_requirements: Optional[list[Requirement]] = None,
    answered_context: Optional[str] = None,
    chunks: Optional[list[SourceChunk]] = None,
) -> str:
    """Build the extraction prompt instructing the LLM to analyze the business idea and source chunks.

    Acts as a senior business analyst extracting requirements across all 4 types
    (business, functional, nonfunctional, constraint) and proposing assumptions.

    Args:
        idea_text: Optional raw business idea prompt submitted by the stakeholder.
        existing_requirements: Any requirements already extracted in previous iterations.
        answered_context: Formatted string of questions and stakeholder answers.
        chunks: Optional list of SourceChunk records from uploaded source documents.

    Returns:
        Formatted prompt string.
    """
    existing_str = "None"
    if existing_requirements:
        existing_data = [
            {
                "id": req.id,
                "type": req.type.value,
                "title": req.title,
                "statement": req.statement,
                "actor": req.actor,
                "outcome": req.outcome,
                "priority": req.priority.value,
                "acceptance_criteria": req.acceptance_criteria,
                "confidence": req.confidence,
                "source_chunk_ids": req.source_chunk_ids,
            }
            for req in existing_requirements
        ]
        existing_str = json.dumps(existing_data, indent=2)

    answered_str = answered_context.strip() if answered_context else "None"

    # Format source document chunks if available
    chunks_formatted: list[str] = []
    if chunks:
        for c in chunks:
            doc_label = f"Doc: {c.document_id}"
            page_label = f"Page: {c.page_number}" if c.page_number is not None else "Page: N/A"
            section_label = f" | Section: {c.heading}" if c.heading else ""
            chunks_formatted.append(
                f"[CHUNK_ID: {c.id} | {doc_label} | {page_label}{section_label}]\n{c.text.strip()}"
            )
    chunks_str = "\n\n".join(chunks_formatted) if chunks_formatted else "None"

    idea_str = idea_text.strip() if idea_text and idea_text.strip() else "None provided (derive requirements primarily from source document chunks)."

    return f"""You are a Principal Business Systems Analyst. Your goal is to synthesize raw business ideas and source document chunks into structured requirement specifications and explicit assumptions for a formal Business Requirements Document (BRD).

### INPUT BUSINESS IDEA:
\"\"\"
{idea_str}
\"\"\"

### SOURCE DOCUMENT CHUNKS:
{chunks_str}

### PREVIOUSLY EXTRACTED REQUIREMENTS:
{existing_str}

### RESOLVED CLARIFICATION ANSWERS:
{answered_str}

### INSTRUCTIONS:
1. Extract candidate requirements categorized into four distinct types:
   - 'business': High-level business objectives, ROI goals, or strategic outcomes.
   - 'functional': Specific features, workflows, and system capabilities ('The system shall...'). Must identify primary actor, outcome, and measurable acceptance criteria.
   - 'nonfunctional': Quality attributes (performance, latency, security, uptime, scalability, compliance) with quantifiable targets where known.
   - 'constraint': Regulatory, architectural, technology, or budgetary boundaries with explicit rationale.
2. Incorporate answered clarifications from the RESOLVED CLARIFICATION ANSWERS section. Do not re-extract stale or conflicting interpretations.
3. If an existing requirement matches, preserve its ID and refine its fields. If new, provide a clean ID like 'REQ-001', 'REQ-002'.
4. Do NOT invent 'trace_refs' (leave them empty []). Traceability references are managed by the backend engine.
5. PROPOSE EXPLICIT ASSUMPTIONS: When filling unavoidable gaps with reasonable industry defaults (e.g., standard business hours, standard web browser support), do NOT guess silently. Instead, formulate an explicit Assumption with rationale and impact level ('LOW' or 'MEDIUM').
6. CRITICAL COMPLETENESS RULES:
   - If key information is genuinely missing or ambiguous (such as the specific user role, exact numerical SLA, or system outcome), DO NOT INVENT OR HALLUCINATE specifics (such as random numbers, exact dates, third-party vendor names, or APIs not mentioned in the input).
   - If an actor, outcome, or acceptance criterion was not specified, leave that field empty (None or []) or assign a low confidence score (< 0.5) so that the validation engine can generate a targeted clarification question.
7. STRICT SOURCE CHUNK CITATIONS & TRACEABILITY:
   - When extracting any requirement derived from or justified by the provided SOURCE DOCUMENT CHUNKS, you MUST populate the `source_chunk_ids` list with the exact matching chunk IDs (e.g. `source_chunk_ids: ["CHUNK-12345-0"]`).
   - You may also provide a concise `rationale` explaining how the cited chunks justify the requirement.
   - NEVER invent or hallucinate chunk IDs. Only cite chunk IDs that appear verbatim in the `[CHUNK_ID: <id> ...]` headers above. If a requirement is derived solely from the general business idea without document grounding, leave `source_chunk_ids` as an empty list [].

Output strictly according to the ExtractionResult schema.
"""


def build_gap_analysis_prompt(requirements: list[Requirement]) -> str:
    """Build the advisory gap analysis prompt for Gemini to inspect requirement sets.

    Note: Gemini's gap analysis is treated as advisory review candidate input only;
    concrete validation decisions are enforced by Python rules.

    Args:
        requirements: List of requirements to analyze for contradictions or ambiguities.

    Returns:
        Formatted prompt string.
    """
    reqs_dump = json.dumps(
        [
            {
                "id": req.id,
                "type": req.type.value,
                "title": req.title,
                "statement": req.statement,
                "actor": req.actor,
                "outcome": req.outcome,
                "confidence": req.confidence,
            }
            for req in requirements
        ],
        indent=2,
    )

    return f"""You are an expert Requirements Quality Assurance Auditor. Review the following set of requirements for ambiguities, contradictions, or overlapping duplicates.

### REQUIREMENTS SET:
{reqs_dump}

### INSTRUCTIONS:
- Identify possible contradictions, vague quality attributes, or duplicate statements across requirements.
- Flag each issue as a review candidate.
- Provide a concise description, list the related requirement IDs, and suggest a severity ('warning' or 'blocker').
- These findings serve as advisory inputs to the engineering rule engine.

Output strictly according to the GapAnalysisResult schema.
"""


def build_question_text_prompt(
    issue: ValidationIssue,
    related_requirement: Optional[Requirement] = None,
) -> str:
    """Build a deterministic prompt asking Gemini to draft one clarification question for a single issue.

    Python decides which issues warrant questions prior to invoking this prompt.

    Args:
        issue: The specific ValidationIssue flagged by the rule engine.
        related_requirement: The corresponding Requirement object, if applicable.

    Returns:
        Formatted prompt string.
    """
    req_context = "None"
    if related_requirement:
        req_context = json.dumps(
            {
                "id": related_requirement.id,
                "type": related_requirement.type.value,
                "title": related_requirement.title,
                "statement": related_requirement.statement,
                "actor": related_requirement.actor,
                "outcome": related_requirement.outcome,
            },
            indent=2,
        )

    return f"""You are a professional Business Analyst conducting a stakeholder discovery interview. A concrete information gap has been detected that prevents generating a complete Business Requirements Document.

### VALIDATION ISSUE DETAILS:
- Issue Code: {issue.code}
- Severity: {issue.severity.value}
- Affected Field: {issue.field_path}
- Diagnostic Message: {issue.message}

### ASSOCIATED REQUIREMENT:
{req_context}

### TASK:
Draft ONE clear, concise, and non-technical clarification question that a non-technical business stakeholder can easily answer.

Requirements for your output:
1. 'question_text': Phrased clearly and politely, avoiding internal jargon or code identifiers.
2. 'why_it_matters': Exactly ONE sentence explaining why this information is essential for the system architecture or business workflow.
3. 'answer_format': Choose the most appropriate format: 'TEXT', 'CHOICE', 'DATE', 'NUMBER', or 'YES_NO'.
4. 'options': If 'answer_format' is 'CHOICE', provide a helpful list of 2 to 5 realistic options. Otherwise, set to null.

Output strictly according to the QuestionDraft schema.
"""
