"""BRD Document Template Builder.

Provides skeleton generator functions that lay out the standardized
structural format of generated Business Requirements Documents.
"""

from typing import Any

from app.models.project import Project


def build_brd_skeleton(project: Project) -> dict[str, Any]:
    """Build a structured skeleton dictionary for a BRD document.

    Sections are initialized as empty lists or placeholders to be populated
    by the synthesis and requirement extraction agents.

    Args:
        project: Project domain entity containing project metadata.

    Returns:
        Structured dictionary matching the standardized BRD specification schema.
    """
    return {
        "title": project.title,
        "version": 1,
        "generated_at": None,
        "executive_summary": "",
        "business_requirements": [],  # list of Requirement (type=business)
        "functional_requirements": [],  # list of Requirement (type=functional)
        "nonfunctional_requirements": [],  # list of Requirement (type=nonfunctional)
        "constraints": [],  # list of Requirement (type=constraint)
        "assumptions": [],  # list of Assumption
        "open_questions": [],  # list of unresolved Question (should be empty at generation time)
        "traceability_note": (
            "Every requirement links to a source document, a user answer, "
            "or an explicitly accepted assumption."
        ),
    }
