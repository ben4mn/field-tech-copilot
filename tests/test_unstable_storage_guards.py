import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import (
    Assessment,
    CompletedIntervention,
    CompletedTest,
    DiagnosticCase,
    Intervention,
    Observation,
    RiskLevel,
)
from fieldtech.core.models import TestProposal as Proposal


def _file_copy_assessment(instruction: str | None = None) -> Assessment:
    proposal = Proposal(
        key="copy-customer-files",
        title="Copy customer files to external storage",
        rationale="Recover readable files.",
        instructions=[
            instruction
            or "Use Robocopy with /E /Z /R:1 to copy the customer files."
        ],
    )
    return Assessment(
        summary="Copy recoverable files.",
        technician_message="Copy the readable files.",
        next_test=proposal,
    )


def _completed_test(result: str) -> CompletedTest:
    return CompletedTest(
        proposal=Proposal(
            key="image-original-drive",
            title="Image the original drive",
            rationale="Preserve the source before file recovery.",
            instructions=["Create a sector-by-sector image with recovery tooling."],
        ),
        result=result,
    )


def _completed_intervention(result: str) -> CompletedIntervention:
    return CompletedIntervention(
        intervention=Intervention(
            title="Create a controlled recovery artifact",
            rationale="Preserve the unstable source before logical recovery.",
            steps=["Create the recovery artifact with approved tooling."],
            verification=["Record completion and verification status."],
            risk=RiskLevel.SAFE,
        ),
        result=result,
        technician_confirmed=True,
    )


def test_file_copy_is_rejected_for_unstable_drive() -> None:
    case = DiagnosticCase(
        title="Drive disappears",
        complaint=(
            "The hard drive spins up, stops, disappears, and sometimes "
            "shows as Not Initialized. The files are irreplaceable."
        ),
    )

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(case, _file_copy_assessment())


@pytest.mark.parametrize(
    "evidence_source",
    ["observation", "completed_test_result", "completed_intervention_result"],
)
def test_unstable_drive_state_uses_all_case_evidence(evidence_source: str) -> None:
    case = DiagnosticCase(
        title="Intermittent drive",
        complaint="Recover the customer data without changing the source.",
    )
    evidence = "The original drive disconnected and dropped offline during the read."
    if evidence_source == "observation":
        case.observations.append(Observation(text=evidence))
    elif evidence_source == "completed_test_result":
        case.completed_tests.append(_completed_test(evidence))
    else:
        case.completed_interventions.append(_completed_intervention(evidence))

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(case, _file_copy_assessment())


def test_copy_from_completed_verified_image_is_allowed() -> None:
    case = DiagnosticCase(
        title="Image-based recovery",
        complaint="The original drive is unstable and repeatedly disconnects.",
        completed_tests=[
            _completed_test(
                "The sector-by-sector disk image completed successfully, its hash "
                "matched, and the image was verified readable."
            )
        ],
    )
    assessment = _file_copy_assessment(
        "Mount the completed verified disk image read-only, then use Robocopy to "
        "copy customer files from that image to external storage."
    )

    assert validate_assessment(case, assessment) is assessment


def test_copy_from_completed_verified_duplicate_is_allowed() -> None:
    case = DiagnosticCase(
        title="Duplicate-based recovery",
        complaint="The source disk vanishes under sustained reads.",
        completed_tests=[
            _completed_test(
                "The working duplicate finished and its checksum matched; the "
                "duplicate was verified before the original was disconnected."
            )
        ],
    )
    assessment = _file_copy_assessment(
        "Extract customer files from the completed verified duplicate."
    )

    assert validate_assessment(case, assessment) is assessment


def test_copy_from_duplicate_verified_by_completed_intervention_is_allowed() -> None:
    case = DiagnosticCase(
        title="Intervention-created duplicate",
        complaint="The original disk repeatedly disconnects.",
        completed_interventions=[
            _completed_intervention(
                "The duplicate completed, its checksum matched, and verification passed."
            )
        ],
    )
    assessment = _file_copy_assessment(
        "Copy customer files from the completed verified duplicate."
    )

    assert validate_assessment(case, assessment) is assessment


def test_verified_artifact_does_not_allow_copying_from_original() -> None:
    case = DiagnosticCase(
        title="Keep work off the source",
        complaint="The original drive is unstable.",
        completed_tests=[
            _completed_test("The disk image completed and verification passed.")
        ],
    )
    assessment = _file_copy_assessment(
        "Use Robocopy to copy customer files directly from the original unstable drive."
    )

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(case, assessment)


@pytest.mark.parametrize(
    "artifact_result",
    [
        "The image completed, but it has not been verified.",
        "The image was verified readable, but creation did not complete.",
        "Imaging failed before a usable duplicate was created.",
    ],
)
def test_incomplete_or_unverified_artifact_does_not_bypass_guard(
    artifact_result: str,
) -> None:
    case = DiagnosticCase(
        title="Unfinished image",
        complaint="The original disk disconnects under sustained reads.",
        completed_tests=[_completed_test(artifact_result)],
    )
    assessment = _file_copy_assessment(
        "Copy customer files from the recovery image with Robocopy."
    )

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(case, assessment)


def test_file_copy_is_allowed_for_stable_mounted_volume() -> None:
    case = DiagnosticCase(
        title="Verified file transfer",
        complaint=(
            "The healthy source volume is mounted as D: and has remained "
            "connected and normally readable for 30 minutes."
        ),
    )
    assessment = _file_copy_assessment()

    assert validate_assessment(case, assessment) is assessment


def test_unstable_network_does_not_mark_a_healthy_drive_unstable() -> None:
    case = DiagnosticCase(
        title="Copy network logs",
        complaint=(
            "Wi-Fi is unstable and disconnects. The healthy mounted drive remains "
            "normally readable."
        ),
    )
    assessment = _file_copy_assessment("Copy the network log files from the healthy drive.")

    assert validate_assessment(case, assessment) is assessment


def test_sector_image_creation_is_not_mistaken_for_file_copy() -> None:
    case = DiagnosticCase(
        title="Preserve unstable media",
        complaint="The original disk is unstable and has intermittent read errors.",
    )
    assessment = Assessment(
        summary="Preserve the source before logical recovery.",
        technician_message="Create a controlled sector image.",
        next_test=Proposal(
            key="create-sector-image",
            title="Create an image of the original media",
            rationale="Minimize repeated reads of the source.",
            instructions=["Create a sector-level image with controlled recovery tooling."],
        ),
    )

    assert validate_assessment(case, assessment) is assessment
