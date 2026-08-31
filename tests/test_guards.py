import pytest
from pydantic import ValidationError

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import (
    Assessment,
    CompletedTest,
    DiagnosticCase,
    Intervention,
    RiskLevel,
)
from fieldtech.core.models import (
    TestProposal as Proposal,
)


def test_completed_test_cannot_be_silently_repeated() -> None:
    proposal = Proposal(
        key="ping-default-gateway",
        title="Ping the default gateway",
        rationale="Localizes the network failure",
        instructions=["Ping the configured gateway"],
    )
    case = DiagnosticCase(
        title="Connectivity",
        complaint="No internet",
        completed_tests=[CompletedTest(proposal=proposal, result="Replies received")],
    )
    assessment = Assessment(
        summary="More evidence is needed",
        technician_message="Repeat the ping",
        next_test=proposal.model_copy(update={"id": "test_again"}),
    )

    with pytest.raises(GuardrailViolation, match="without a specific repeat reason"):
        validate_assessment(case, assessment)


def test_repeat_is_allowed_with_specific_changed_condition() -> None:
    proposal = Proposal(
        key="ping-default-gateway",
        title="Ping the default gateway",
        rationale="Localizes the network failure",
        instructions=["Ping the configured gateway"],
    )
    case = DiagnosticCase(
        title="Connectivity",
        complaint="No internet",
        completed_tests=[CompletedTest(proposal=proposal, result="No reply")],
    )
    repeated = proposal.model_copy(
        update={
            "id": "test_again",
            "repeat_reason": "The adapter was reseated, so link state materially changed.",
        }
    )
    assessment = Assessment(
        summary="Link state changed",
        technician_message="Repeat once after the physical change",
        next_test=repeated,
    )

    assert validate_assessment(case, assessment) is assessment


def test_destructive_intervention_requires_controls() -> None:
    with pytest.raises(ValidationError, match="require confirmation"):
        Intervention(
            title="Reset the computer",
            rationale="Attempt recovery",
            steps=["Reset Windows"],
            verification=["System boots"],
            risk=RiskLevel.DESTRUCTIVE,
            prerequisites=["Customer authorization and verified backup"],
            rollback="No guaranteed rollback exists.",
            requires_confirmation=False,
        )
