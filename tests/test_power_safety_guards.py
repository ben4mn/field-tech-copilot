import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal


@pytest.mark.parametrize(
    "instruction",
    [
        "Connect the laptop through a powered USB-C hub.",
        "Connect a 12V external battery pack to the USB-C port.",
        "Use a bypass switch for power isolation.",
        "Inject power into the motherboard.",
        "Apply 19V from a lab supply to the DC input jack.",
    ],
)
def test_unsupported_power_techniques_are_rejected(instruction: str) -> None:
    proposal = Proposal(
        key="power-isolation",
        title="Test alternate power",
        rationale="Look for activity",
        instructions=[instruction],
    )
    assessment = Assessment(
        summary="No power",
        technician_message="Try alternate power",
        next_test=proposal,
    )
    case = DiagnosticCase(title="No power", complaint="No activity")

    with pytest.raises(GuardrailViolation, match="Unsupported external-power"):
        validate_assessment(case, assessment)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rationale", "First connect an external battery pack directly to the board."),
        ("expected_results", ["Apply 19V from a lab supply if the LED stays dark."]),
        ("prerequisites", ["Connect the laptop through a powered USB-C hub."]),
        ("rollback", "Inject power into the motherboard again if the test fails."),
    ],
)
def test_unsupported_power_is_rejected_in_every_visible_action_field(
    field: str,
    value: str | list[str],
) -> None:
    proposal = Proposal(
        key="inspect-power-state",
        title="Inspect power state",
        rationale="Look for activity.",
        instructions=["Observe the charge LED without changing the hardware."],
    ).model_copy(update={field: value})
    assessment = Assessment(
        summary="The device has no visible activity.",
        technician_message="Observe the charge LED.",
        next_test=proposal,
    )

    with pytest.raises(GuardrailViolation, match="Unsupported external-power"):
        validate_assessment(
            DiagnosticCase(title="No power", complaint="No activity"),
            assessment,
        )


def test_unsupported_power_is_rejected_in_no_action_summary() -> None:
    assessment = Assessment(
        summary="Connect an external battery pack directly to the system board.",
        technician_message="No structured action is proposed.",
    )

    with pytest.raises(GuardrailViolation, match="Unsupported external-power"):
        validate_assessment(
            DiagnosticCase(title="No power", complaint="No activity"),
            assessment,
        )


def test_negated_power_safety_language_is_allowed() -> None:
    assessment = Assessment(
        summary="Do not connect an external battery pack or inject power.",
        technician_message="Stop without attempting another action.",
    )

    assert (
        validate_assessment(
            DiagnosticCase(title="No power", complaint="No activity"),
            assessment,
        )
        is assessment
    )


def test_safe_internal_disassembly_is_rejected() -> None:
    proposal = Proposal(
        key="disconnect-battery",
        title="Disconnect internal battery",
        rationale="Isolate the battery",
        instructions=["Remove the base cover and disconnect the internal battery."],
    )
    assessment = Assessment(
        summary="No power",
        technician_message="Open the laptop",
        next_test=proposal,
    )
    case = DiagnosticCase(title="No power", complaint="No activity")

    with pytest.raises(GuardrailViolation, match="incorrectly marked safe"):
        validate_assessment(case, assessment)


def test_intrusive_hardware_in_rationale_is_not_hidden_by_benign_steps() -> None:
    proposal = Proposal(
        key="inspect-charge-led",
        title="Inspect the charge LED",
        rationale="First remove the base cover, then look for the LED.",
        instructions=["Observe whether the charge LED is illuminated."],
    )
    assessment = Assessment(
        summary="Inspect the visible power state.",
        technician_message="Observe the charge LED.",
        next_test=proposal,
    )

    with pytest.raises(GuardrailViolation, match="incorrectly marked safe"):
        validate_assessment(
            DiagnosticCase(title="No power", complaint="No activity"),
            assessment,
        )
