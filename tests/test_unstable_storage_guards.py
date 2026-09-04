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


def test_no_action_cannot_hide_file_copy_in_summary() -> None:
    case = DiagnosticCase(
        title="Drive disappears",
        complaint="The original drive is unstable and repeatedly disconnects.",
    )
    assessment = Assessment(
        summary="Use Robocopy to copy the customer files from the original drive.",
        technician_message="No structured action is proposed.",
        disposition="escalate",
    )

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(case, assessment)


def test_no_action_cannot_hide_imaging_in_summary() -> None:
    case = DiagnosticCase(
        title="Drive disappears",
        complaint="The original drive is unstable and repeatedly disconnects.",
    )
    assessment = Assessment(
        summary="Image the drive before doing anything else.",
        technician_message="No structured action is proposed.",
        disposition="escalate",
    )

    with pytest.raises(GuardrailViolation, match="must be a caution intervention"):
        validate_assessment(case, assessment)


def test_negated_copy_language_is_allowed_without_an_action() -> None:
    case = DiagnosticCase(
        title="Drive disappears",
        complaint="The original drive is unstable and repeatedly disconnects.",
    )
    assessment = Assessment(
        summary="Do not use Robocopy or copy customer files from the original drive.",
        technician_message="Stop and escalate to professional recovery.",
        disposition="escalate",
    )

    assert validate_assessment(case, assessment) is assessment


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


def test_failed_artifact_outcome_overrides_optimistic_result_wording() -> None:
    completed = _completed_test(
        "The image completed and its checksum matched before the overall operation failed."
    )
    completed.outcome = "fail"
    case = DiagnosticCase(
        title="Failed recovery image",
        complaint="The original disk is unstable and disconnects.",
        completed_tests=[completed],
    )

    with pytest.raises(GuardrailViolation, match="File-level copy was proposed"):
        validate_assessment(
            case,
            _file_copy_assessment("Copy customer files from the recovery image."),
        )


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


@pytest.mark.parametrize(
    "symptom",
    [
        "clicks during reads",
        "makes a click during reads",
        "makes clicking sounds during reads",
        "is disappearing from Disk Management",
        "keeps vanishing from Windows",
        "goes offline during reads",
        "went offline during reads",
    ],
)
def test_common_unstable_drive_wording_blocks_copy_from_original(
    symptom: str,
) -> None:
    case = DiagnosticCase(
        title="Unstable drive",
        complaint=f"The original drive {symptom} and has no backup.",
    )

    with pytest.raises(GuardrailViolation):
        validate_assessment(case, _file_copy_assessment())


def test_negated_clicking_does_not_mark_healthy_drive_unstable() -> None:
    case = DiagnosticCase(
        title="Healthy source",
        complaint=(
            "The healthy mounted drive is not clicking and has remained normally "
            "readable for 30 minutes."
        ),
    )

    assert validate_assessment(case, _file_copy_assessment()) is not None


def test_sector_image_creation_requires_a_controlled_intervention() -> None:
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

    with pytest.raises(GuardrailViolation, match="must be a caution intervention"):
        validate_assessment(case, assessment)


def test_controlled_imaging_is_allowed_with_all_required_controls() -> None:
    case = DiagnosticCase(
        title="Preserve unstable media",
        complaint=(
            "The original disk is unstable with intermittent read errors, but remains "
            "continuously detected as a block device."
        ),
    )
    intervention = Intervention(
        key="controlled-image-original-drive",
        title="Create a controlled sector image",
        rationale="Preserve the source before logical recovery.",
        steps=[
            "Use GNU ddrescue with a persistent mapfile for one non-scraping pass."
        ],
        verification=["Confirm the image and mapfile exist before any extraction."],
        risk=RiskLevel.CAUTION,
        requires_confirmation=True,
        prerequisites=[
            "Record that the customer accepts the risk of further degradation or data loss.",
            "Verify the source identity, model, serial, capacity, and device path.",
            "Verify that the destination is healthy, empty, and larger than the source.",
        ],
        rollback="Stop imaging, preserve the image and mapfile, and power off the source.",
    )
    assessment = Assessment(
        summary="The source is stable enough for one controlled imaging pass.",
        technician_message="Create the controlled image after confirmation.",
        intervention=intervention,
    )

    assert validate_assessment(case, assessment) is assessment


def test_imaging_is_rejected_for_severe_mechanical_failure_and_unique_data() -> None:
    case = DiagnosticCase(
        title="Severe drive failure",
        complaint=(
            "The original hard drive clicks, repeatedly spins up and down, and contains "
            "irreplaceable photos with no backup."
        ),
    )
    assessment = Assessment(
        summary="Attempt imaging.",
        technician_message="Run the proposed imaging intervention.",
        intervention=Intervention(
            key="controlled-image-original-drive",
            title="Create a controlled sector image",
            rationale="Attempt preservation.",
            steps=["Run GNU ddrescue against the original drive."],
            verification=["Confirm the image exists."],
            risk=RiskLevel.CAUTION,
            requires_confirmation=True,
            prerequisites=[
                "Record that the customer accepts the data-loss risk.",
                "Verify the source identity and serial number.",
                "Verify that the destination is healthy, empty, and larger.",
            ],
            rollback="Stop imaging and power off the source.",
        ),
    )

    with pytest.raises(GuardrailViolation, match="severe mechanical symptoms"):
        validate_assessment(case, assessment)


def _severe_irreplaceable_case() -> DiagnosticCase:
    return DiagnosticCase(
        title="Severe drive failure",
        complaint=(
            "The original hard drive clicks, repeatedly spins up and down, and contains "
            "irreplaceable photos with no backup."
        ),
    )


def test_severe_irreplaceable_drive_blocks_further_read_only_tests() -> None:
    assessment = Assessment(
        summary="Collect more health data before deciding whether to escalate.",
        technician_message="Run the proposed storage test.",
        next_test=Proposal(
            key="inspect-drive-health",
            title="Inspect drive health",
            rationale="Collect another health signal.",
            instructions=[
                "Run Get-PhysicalDisk and Get-StorageReliabilityCounter against the "
                "original drive."
            ],
        ),
    )

    with pytest.raises(GuardrailViolation, match="severe mechanical symptoms"):
        validate_assessment(_severe_irreplaceable_case(), assessment)


def test_negated_mechanical_symptom_does_not_force_severe_escalation() -> None:
    case = DiagnosticCase(
        title="Logically inaccessible drive",
        complaint=(
            "The drive shows Not Initialized but is not clicking and contains the "
            "only copy of the photos."
        ),
    )
    assessment = Assessment(
        summary="Collect one read-only device-state snapshot.",
        technician_message="Run Get-Disk without initializing the drive.",
        next_test=Proposal(
            key="inspect-disk-state",
            title="Inspect disk state",
            rationale="Distinguish logical state from severe mechanical failure.",
            instructions=["Run Get-Disk and record the device state."],
        ),
    )

    assert validate_assessment(case, assessment) is assessment


def test_severe_irreplaceable_drive_blocks_continue_reading_narrative() -> None:
    assessment = Assessment(
        summary="Continue trying to read it before escalation.",
        technician_message="No structured action is proposed.",
        disposition="escalate",
    )

    with pytest.raises(GuardrailViolation, match="severe mechanical symptoms"):
        validate_assessment(_severe_irreplaceable_case(), assessment)


def test_severe_irreplaceable_drive_allows_power_off_escalation() -> None:
    assessment = Assessment(
        summary="Power the drive off and escalate to professional data recovery.",
        technician_message="Do not continue reading or testing the original drive.",
        disposition="escalate",
    )

    assert validate_assessment(_severe_irreplaceable_case(), assessment) is assessment


@pytest.mark.parametrize(
    "summary",
    [
        "Do not power off the drive. Escalate to professional recovery.",
        "Power off is unnecessary. Escalate to professional recovery.",
        "Power off the drive. Avoid professional recovery.",
    ],
)
def test_severe_irreplaceable_drive_requires_affirmative_controls(
    summary: str,
) -> None:
    assessment = Assessment(
        summary=summary,
        technician_message="No structured action is proposed.",
        disposition="escalate",
    )

    with pytest.raises(GuardrailViolation, match="severe mechanical symptoms"):
        validate_assessment(_severe_irreplaceable_case(), assessment)


def test_severe_irreplaceable_drive_allows_only_power_off_intervention() -> None:
    assessment = Assessment(
        summary="Power the drive off and escalate to professional data recovery.",
        technician_message="Power off the original drive and leave it disconnected.",
        disposition="escalate",
        intervention=Intervention(
            key="power-off-failing-drive",
            title="Power off the failing drive",
            rationale="Prevent further mechanical degradation.",
            steps=["Power the failing drive off and leave it disconnected."],
            verification=["Confirm the drive is no longer spinning."],
            risk=RiskLevel.SAFE,
        ),
    )

    assert validate_assessment(_severe_irreplaceable_case(), assessment) is assessment
