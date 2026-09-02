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