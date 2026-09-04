import pytest
from pydantic import ValidationError

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import (
    Assessment,
    CompletedIntervention,
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


def test_legacy_caution_intervention_loads_but_new_assessment_requires_controls() -> None:
    intervention = Intervention(
        title="Legacy caution repair",
        rationale="This was persisted before caution controls were required.",
        steps=["Apply the prior repair."],
        verification=["Verify the original symptom."],
        risk=RiskLevel.CAUTION,
    )
    assessment = Assessment(
        summary="A legacy caution intervention was loaded.",
        technician_message="Apply the repair.",
        intervention=intervention,
    )

    with pytest.raises(GuardrailViolation, match="Non-safe intervention"):
        validate_assessment(
            DiagnosticCase(title="Legacy", complaint="Synthetic legacy case"),
            assessment,
        )


def test_model_output_containing_recovery_key_is_withheld() -> None:
    assessment = Assessment(
        summary=(
            "Use 111111-222222-333333-444444-555555-666666-777777-888888."
        ),
        technician_message="Do not expose a recovery key.",
    )

    with pytest.raises(GuardrailViolation, match="recovery key"):
        validate_assessment(
            DiagnosticCase(title="BitLocker", complaint="Locked BitLocker volume"),
            assessment,
        )


def test_rephrased_completed_intervention_requires_material_repeat_reason() -> None:
    completed = Intervention(
        key="restart-print-spooler",
        title="Restart the print spooler",
        rationale="Clear the stalled queue.",
        steps=["Restart the Windows Print Spooler service."],
        verification=["Print a test page."],
        risk=RiskLevel.CAUTION,
        prerequisites=["Confirm queued jobs may be interrupted."],
        rollback="Start the service if it remains stopped.",
        requires_confirmation=True,
    )
    case = DiagnosticCase(
        title="Printer queue",
        complaint="The print queue is stalled.",
        completed_interventions=[
            CompletedIntervention(
                intervention=completed,
                result="The service restarted but the queue stayed stalled.",
                outcome="fail",
                technician_confirmed=True,
            )
        ],
    )
    rephrased = completed.model_copy(
        update={
            "id": "intervention_rephrased",
            "key": "cycle-spooler-service",
            "title": "Cycle the spooler service",
        }
    )

    with pytest.raises(GuardrailViolation, match="specific repeat reason"):
        validate_assessment(
            case,
            Assessment(
                summary="Try the same repair again.",
                technician_message="Cycle the service.",
                intervention=rephrased,
            ),
        )
