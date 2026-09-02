import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal


def _robocopy_assessment() -> Assessment:
    proposal = Proposal(
        key="copy-customer-files",
        title="Copy customer files to external storage",
        rationale="Recover readable files.",
        instructions=[
            "Use Robocopy with /E /Z /R:1 to copy the customer files."
        ],
    )
    return Assessment(
        summary="Attempt a file copy.",
        technician_message="Copy the readable files.",
        next_test=proposal,
    )


def test_file_copy_is_rejected_for_unstable_drive() -> None:
    case = DiagnosticCase(
        title="Drive disappears",
        complaint=(
            "The hard drive spins up, stops, disappears, and sometimes "
            "shows as Not Initialized. The files are irreplaceable."
        ),
    )

    with pytest.raises(
        GuardrailViolation,
        match="File-level copy was proposed",
    ):
        validate_assessment(case, _robocopy_assessment())


def test_file_copy_is_allowed_for_stable_mounted_volume() -> None:
    case = DiagnosticCase(
        title="Verified file transfer",
        complaint=(
            "The healthy source volume is mounted as D: and has remained "
            "connected and normally readable for 30 minutes."
        ),
    )
    assessment = _robocopy_assessment()

    assert validate_assessment(case, assessment) is assessment
