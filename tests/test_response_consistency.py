from fieldtech.core.models import Assessment, Disposition, Intervention
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.core.service import DiagnosticService


def test_next_test_message_is_built_only_from_structured_action() -> None:
    assessment = Assessment(
        summary="Inspect the adapter configuration.",
        technician_message=(
            "Run ipconfig /all and then verify another device."
        ),
        next_test=Proposal(
            key="capture-ipconfig",
            title="Capture adapter configuration",
            rationale="Inspect the current DHCP configuration.",
            instructions=["Run ipconfig /all."],
        ),
    )

    DiagnosticService._synchronize_technician_message(assessment)

    assert assessment.technician_message == (
        "Next test: Capture adapter configuration. Run ipconfig /all."
    )
    assert "another device" not in assessment.technician_message


def test_intervention_message_uses_only_structured_steps() -> None:
    assessment = Assessment(
        summary="Restart the print spooler.",
        technician_message=(
            "Restart the print spooler and then restart Windows."
        ),
        intervention=Intervention(
            title="Restart print spooler",
            rationale="Recover the stalled print service.",
            steps=["Restart the print spooler service."],
            verification=["Print a Windows test page."],
            prerequisites=["Confirm the queued jobs can be safely interrupted."],
            rollback="Start the print spooler service if it remains stopped.",
            requires_confirmation=True,
        ),
    )

    DiagnosticService._synchronize_technician_message(assessment)

    assert assessment.technician_message == (
        "Proposed intervention: Restart print spooler. "
        "Technician confirmation is required before starting. "
        "Restart the print spooler service."
    )
    assert "restart Windows" not in assessment.technician_message


def test_no_action_message_cannot_introduce_a_procedure() -> None:
    assessment = Assessment(
        summary="Escalation is required.",
        technician_message="Run another diagnostic command.",
        disposition=Disposition.ESCALATE,
    )

    DiagnosticService._synchronize_technician_message(assessment)

    assert assessment.technician_message == (
        "No technician action is proposed. "
        "The structured disposition is escalation."
    )
    assert "diagnostic command" not in assessment.technician_message
