"""Unit tests for deterministic Python completeness and validation rules."""

import pytest

from app.core.validation_rules import (
    validate_project_completeness,
    validate_requirements,
)
from app.models.requirement import Priority, Requirement, RequirementType
from app.models.validation import Severity


def test_functional_requirement_missing_actor():
    """A functional requirement without an actor must produce a FUNC_MISSING_ACTOR blocker."""
    req = Requirement(
        id="REQ-F1",
        type=RequirementType.FUNCTIONAL,
        title="Payment Checkout",
        statement="The system shall process card payments.",
        actor=None,  # Missing actor
        outcome="Order is paid.",
        acceptance_criteria=["Charge card successfully"],
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "FUNC_MISSING_ACTOR"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER
    assert matching[0].field_path == "requirements[REQ-F1].actor"


def test_functional_requirement_missing_outcome():
    """A functional requirement without an outcome must produce a FUNC_MISSING_OUTCOME blocker."""
    req = Requirement(
        id="REQ-F2",
        type=RequirementType.FUNCTIONAL,
        title="Search Catalog",
        statement="The system shall allow searching items.",
        actor="Shopper",
        outcome=None,  # Missing outcome
        acceptance_criteria=["Returns relevant items"],
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "FUNC_MISSING_OUTCOME"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER
    assert matching[0].field_path == "requirements[REQ-F2].outcome"


def test_functional_requirement_empty_acceptance_criteria():
    """A functional requirement with empty acceptance_criteria must produce a FUNC_EMPTY_ACCEPTANCE_CRITERIA blocker."""
    req = Requirement(
        id="REQ-F3",
        type=RequirementType.FUNCTIONAL,
        title="Export Reports",
        statement="The system shall export CSV reports.",
        actor="Admin",
        outcome="Admin receives reports.",
        acceptance_criteria=[],  # Empty criteria
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "FUNC_EMPTY_ACCEPTANCE_CRITERIA"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER
    assert matching[0].field_path == "requirements[REQ-F3].acceptance_criteria"


def test_nfr_unclear_attribute():
    """An NFR that does not specify a recognized quality attribute must produce an NFR_UNCLEAR_ATTRIBUTE blocker."""
    req = Requirement(
        id="REQ-NF1",
        type=RequirementType.NONFUNCTIONAL,
        title="System Quality",
        statement="The system must be good and modern.",  # Unclear attribute
        outcome="Better quality",
        acceptance_criteria=["System works well"],
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "NFR_UNCLEAR_ATTRIBUTE"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER


def test_nfr_no_measurable_target():
    """An NFR naming an attribute but lacking numeric targets must produce an NFR_NO_MEASURABLE_TARGET warning."""
    req = Requirement(
        id="REQ-NF2",
        type=RequirementType.NONFUNCTIONAL,
        title="API Latency",
        statement="The system latency should be very fast.",  # No numbers / units
        outcome="Fast experience",
        acceptance_criteria=["Requests respond quickly without delay"],
    )
    result = validate_requirements([req])

    assert not result.has_blockers
    matching = [i for i in result.issues if i.code == "NFR_NO_MEASURABLE_TARGET"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.WARNING


def test_nfr_valid_measurable_target():
    """An NFR with concrete metrics (e.g. 200ms) passes without NFR issues."""
    req = Requirement(
        id="REQ-NF3",
        type=RequirementType.NONFUNCTIONAL,
        title="API Latency",
        statement="API response time must be under 200ms for p95 requests.",
        outcome="Sub-second interactive response",
        acceptance_criteria=["Average response time < 200ms under 500 rps"],
    )
    result = validate_requirements([req])
    assert len(result.issues) == 0


def test_business_requirement_missing_objective():
    """A business requirement lacking an objective must produce a BIZ_MISSING_OBJECTIVE blocker."""
    req = Requirement(
        id="REQ-B1",
        type=RequirementType.BUSINESS,
        title="Operations",
        statement="",  # Empty
        outcome=None,  # Missing
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "BIZ_MISSING_OBJECTIVE"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER


def test_business_requirement_no_success_measure():
    """A business requirement with an objective but no quantifiable metric produces a BIZ_NO_SUCCESS_MEASURE warning."""
    req = Requirement(
        id="REQ-B2",
        type=RequirementType.BUSINESS,
        title="Brand Awareness",
        statement="Expand enterprise market presence.",
        outcome="Achieve recognition across businesses.",  # No measurable metric
    )
    result = validate_requirements([req])

    assert not result.has_blockers
    matching = [i for i in result.issues if i.code == "BIZ_NO_SUCCESS_MEASURE"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.WARNING


def test_constraint_missing_rationale():
    """A constraint without an architectural or regulatory rationale must produce a CONSTRAINT_MISSING_RATIONALE blocker."""
    req = Requirement(
        id="REQ-C1",
        type=RequirementType.CONSTRAINT,
        title="Hosting Location",
        statement="The database must be deployed in Germany.",  # No rationale given
        outcome=None,
        trace_refs=[],
    )
    result = validate_requirements([req])

    assert result.has_blockers
    matching = [i for i in result.issues if i.code == "CONSTRAINT_MISSING_RATIONALE"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.BLOCKER


def test_constraint_valid_rationale():
    """A constraint that explicitly provides a rationale or source passes without blocker."""
    req = Requirement(
        id="REQ-C2",
        type=RequirementType.CONSTRAINT,
        title="Hosting Location",
        statement="The database must be hosted in Frankfurt due to GDPR data sovereignty regulations.",
        outcome="Compliance with European privacy law",
        trace_refs=["DOC-LEGAL-01"],
    )
    result = validate_requirements([req])
    assert len(result.issues) == 0


def test_duplicate_requirement_warning():
    """Highly similar requirements of the same type must be flagged with DUPLICATE_REQUIREMENT."""
    req1 = Requirement(
        id="REQ-D1",
        type=RequirementType.FUNCTIONAL,
        title="User Login Authentication",
        statement="The user shall sign into their account using their email and password.",
        actor="User",
        outcome="User is authenticated",
        acceptance_criteria=["Valid credentials log user in"],
    )
    req2 = Requirement(
        id="REQ-D2",
        type=RequirementType.FUNCTIONAL,
        title="User Login Authentication",
        statement="The user shall sign in to their account using an email and password.",
        actor="User",
        outcome="User is authenticated",
        acceptance_criteria=["Valid credentials log user in"],
    )
    result = validate_requirements([req1, req2])

    matching = [i for i in result.issues if i.code == "DUPLICATE_REQUIREMENT"]
    assert len(matching) >= 1
    assert matching[0].severity == Severity.WARNING
    assert "REQ-D1,REQ-D2" in matching[0].entity_id or "REQ-D2" in matching[0].entity_id


def test_low_confidence_warning():
    """A requirement with confidence below 0.5 must produce a LOW_CONFIDENCE_REQUIREMENT warning."""
    req = Requirement(
        id="REQ-LOW",
        type=RequirementType.FUNCTIONAL,
        title="Third-Party Sync",
        statement="The system shall sync data with unknown external CRM.",
        actor="Worker",
        outcome="Data synced",
        acceptance_criteria=["Sync completes hourly"],
        confidence=0.40,  # Below 0.5 threshold
    )
    result = validate_requirements([req])

    matching = [i for i in result.issues if i.code == "LOW_CONFIDENCE_REQUIREMENT"]
    assert len(matching) == 1
    assert matching[0].severity == Severity.WARNING


def test_project_completeness_rules():
    """Test project-level completeness: zero business and zero functional requirements are blockers."""
    # Empty set has both blockers
    empty_result = validate_project_completeness([])
    assert empty_result.has_blockers
    assert any(i.code == "PROJECT_NO_BUSINESS_REQUIREMENTS" for i in empty_result.issues)
    assert any(i.code == "PROJECT_NO_FUNCTIONAL_REQUIREMENTS" for i in empty_result.issues)

    # Set with both business and functional requirements has no project blockers
    b_req = Requirement(
        id="REQ-B",
        type=RequirementType.BUSINESS,
        title="Growth",
        statement="Increase revenue by 20%",
        outcome="Revenue growth",
    )
    f_req = Requirement(
        id="REQ-F",
        type=RequirementType.FUNCTIONAL,
        title="Search",
        statement="Search items",
        actor="User",
        outcome="Results returned",
        acceptance_criteria=["Returns results"],
    )
    complete_result = validate_project_completeness([b_req, f_req])
    assert not complete_result.has_blockers
    assert len(complete_result.issues) == 0
