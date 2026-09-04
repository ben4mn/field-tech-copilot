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


def _locked_case() -> DiagnosticCase:
    return DiagnosticCase(
        title="BitLocker data transfer",
        complaint=(
            "The stable NVMe volume is locked by BitLocker. The customer "
            "is unavailable and has not provided the recovery key."
        ),
    )


def _assessment_with_test(*instructions: str) -> Assessment:
    return Assessment(
        summary="The BitLocker volume is locked.",
        technician_message="Follow the proposed step.",
        next_test=Proposal(
            key="bitlocker-next-step",
            title="Continue BitLocker recovery",
            rationale="Proceed with the recovery workflow.",
            instructions=list(instructions),
        ),
    )


def _authorized_locked_case() -> DiagnosticCase:
    return DiagnosticCase(
        title="Authorized BitLocker recovery",
        complaint=(
            "The stable NVMe volume is locked by BitLocker. The customer "
            "has supplied the matching authorized 48-digit recovery key."
        ),
    )


def _authorized_intervention(
    *,
    risk: RiskLevel = RiskLevel.CAUTION,
    requires_confirmation: bool = True,
    prerequisites: list[str] | None = None,
    rollback: str | None = "Relock or safely disconnect the original volume.",
    steps: list[str] | None = None,
) -> Assessment:
    intervention = Intervention(
        title="Unlock the BitLocker volume and copy authorized folders",
        rationale="The matching authorized recovery key is available.",
        steps=steps
        or [
            "Unlock the BitLocker-protected drive through Windows.",
            "Copy only the authorized Documents and Pictures folders.",
        ],
        verification=["Verify only the authorized folders were copied."],
        risk=risk,
        requires_confirmation=requires_confirmation,
        prerequisites=prerequisites
        if prerequisites is not None
        else [
            "Confirm customer authorization.",
            "Confirm that the displayed recovery-key ID matches the supplied key ID.",
        ],
        rollback=rollback,
    )
    return Assessment(
        summary="The authorized BitLocker recovery key is available.",
        technician_message="Unlock only after confirmation.",
        intervention=intervention,
    )


def test_storage_health_test_is_rejected_when_bitlocker_key_is_missing() -> None:
    assessment = _assessment_with_test(
        "Run Get-Disk, Get-PhysicalDisk, and Get-StorageReliabilityCounter."
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(_locked_case(), assessment)


def test_no_action_cannot_hide_unsafe_bitlocker_access_in_summary() -> None:
    assessment = Assessment(
        summary="Use the customer password to unlock BitLocker and copy their files.",
        technician_message="No structured action is proposed.",
        disposition="escalate",
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(_locked_case(), assessment)


def test_negated_bitlocker_access_language_is_allowed_without_an_action() -> None:
    assessment = Assessment(
        summary="Do not unlock the volume or copy customer files without the key.",
        technician_message="Wait for authorized private key retrieval.",
        disposition="needs_information",
    )

    assert validate_assessment(_locked_case(), assessment) is assessment


@pytest.mark.parametrize(
    "summary",
    [
        "Ask anyone available to retrieve the BitLocker recovery key.",
        "Retrieve the BitLocker recovery key from the account.",
        "Have the customer retrieve the recovery key and tell it to the technician.",
    ],
)
def test_no_action_key_retrieval_requires_authorized_private_control(
    summary: str,
) -> None:
    assessment = Assessment(
        summary=summary,
        technician_message="Wait for more information.",
        disposition="needs_information",
    )

    with pytest.raises(GuardrailViolation, match="only private, authorized"):
        validate_assessment(_locked_case(), assessment)


def test_no_action_private_customer_key_retrieval_guidance_is_allowed() -> None:
    assessment = Assessment(
        summary=(
            "Have the customer privately retrieve the matching BitLocker recovery key "
            "on a device they control without sharing credentials."
        ),
        technician_message="Wait for the authorized customer to finish privately.",
        disposition="needs_information",
    )

    assert validate_assessment(_locked_case(), assessment) is assessment


def test_negated_key_retrieval_mention_does_not_require_retrieval_controls() -> None:
    assessment = Assessment(
        summary="Do not retrieve or disclose the recovery key. Wait for the customer.",
        technician_message="No action is proposed.",
        disposition="needs_information",
    )

    assert validate_assessment(_locked_case(), assessment) is assessment


def test_private_retrieval_cannot_disclose_key_to_technician() -> None:
    assessment = Assessment(
        summary=(
            "Have the customer privately retrieve the BitLocker recovery key, then "
            "show the recovery key to the technician."
        ),
        technician_message="Wait for more information.",
        disposition="needs_information",
    )

    with pytest.raises(GuardrailViolation, match="retained sensitive"):
        validate_assessment(_locked_case(), assessment)


def test_private_customer_recovery_key_guidance_is_allowed() -> None:
    assessment = _assessment_with_test(
        "Have the customer sign in privately at https://aka.ms/myrecoverykey, "
        "retrieve the matching recovery key on a device they control. Do not "
        "request their Microsoft password or record or retain the recovery key."
    )

    assert validate_assessment(_locked_case(), assessment) is assessment


def test_key_retrieval_cannot_unlock_in_the_same_missing_key_step() -> None:
    assessment = _assessment_with_test(
        "Have the customer privately retrieve the matching recovery key and enter "
        "it themselves to unlock the BitLocker volume."
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(_locked_case(), assessment)


def test_key_retrieval_without_private_customer_control_is_rejected() -> None:
    assessment = _assessment_with_test(
        "Ask anyone available to find the BitLocker recovery key."
    )

    with pytest.raises(GuardrailViolation, match="only private, authorized"):
        validate_assessment(_locked_case(), assessment)


def test_key_retrieval_cannot_request_the_customer_password() -> None:
    assessment = _assessment_with_test(
        "Have the customer privately retrieve the recovery key and provide their "
        "Microsoft account password to the technician."
    )

    with pytest.raises(GuardrailViolation, match="requested credentials"):
        validate_assessment(_locked_case(), assessment)


def test_key_retrieval_cannot_be_mixed_with_technical_access() -> None:
    assessment = _assessment_with_test(
        "Have the customer privately retrieve the recovery key at "
        "https://aka.ms/myrecoverykey, then run manage-bde -unlock D: with it."
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(_locked_case(), assessment)


def test_missing_or_mismatched_key_id_blocks_technical_access() -> None:
    case = DiagnosticCase(
        title="Wrong recovery key",
        complaint=(
            "The BitLocker volume is locked. A recovery key was supplied, but "
            "its recovery-key ID does not match the ID displayed by the device."
        ),
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(case, _assessment_with_test("Unlock the volume."))


@pytest.mark.parametrize(
    "evidence_source",
    ["observation", "completed_test_result", "completed_intervention_result"],
)
def test_missing_key_state_uses_all_case_evidence(evidence_source: str) -> None:
    evidence = (
        "The disk is at the BitLocker recovery screen and its recovery key "
        "is unavailable."
    )
    case = DiagnosticCase(title="Recovery", complaint="The customer needs files.")
    if evidence_source == "observation":
        case.observations.append(Observation(text=evidence))
    elif evidence_source == "completed_test_result":
        case.completed_tests.append(
            CompletedTest(
                proposal=Proposal(
                    key="inspect-volume",
                    title="Inspect the volume",
                    rationale="Determine access state.",
                    instructions=["Inspect the recovery screen."],
                ),
                result=evidence,
            )
        )
    else:
        case.completed_interventions.append(
            CompletedIntervention(
                intervention=Intervention(
                    title="Inspect the BitLocker recovery screen",
                    rationale="Record the access state without changing the volume.",
                    steps=["Read the recovery screen without entering credentials."],
                    verification=["Record whether a matching key is available."],
                    risk=RiskLevel.SAFE,
                ),
                result=evidence,
                technician_confirmed=True,
            )
        )

    with pytest.raises(GuardrailViolation, match="before an authorized recovery key"):
        validate_assessment(case, _assessment_with_test("Run Get-Disk."))


def test_completed_key_retrieval_supersedes_initial_missing_key_state() -> None:
    case = _locked_case()
    case.completed_tests.append(
        CompletedTest(
            proposal=Proposal(
                key="retrieve-key",
                title="Retrieve the recovery key",
                rationale="Obtain authorized access.",
                instructions=["Have the customer retrieve the key privately."],
            ),
            result=(
                "The authorized recovery key is now available and the displayed "
                "recovery-key ID was confirmed to match."
            ),
            outcome="pass",
        )
    )
    assessment = _authorized_intervention()

    assert validate_assessment(case, assessment) is assessment


def test_authorized_bitlocker_access_must_be_an_intervention() -> None:
    proposal = Proposal(
        key="authorized-bitlocker-access",
        title="Unlock the BitLocker volume and copy authorized folders",
        rationale="The matching authorized recovery key is available.",
        instructions=["Unlock BitLocker and copy the authorized Documents folder."],
        risk=RiskLevel.CAUTION,
        requires_confirmation=True,
        prerequisites=[
            "Confirm customer authorization and the matching recovery-key ID."
        ],
        rollback="Relock the volume.",
    )
    assessment = Assessment(
        summary="The key is available.",
        technician_message="Proceed only after confirmation.",
        next_test=proposal,
    )

    with pytest.raises(GuardrailViolation, match="must be an intervention"):
        validate_assessment(_authorized_locked_case(), assessment)


@pytest.mark.parametrize("risk", [RiskLevel.SAFE, RiskLevel.DESTRUCTIVE])
def test_authorized_bitlocker_intervention_must_be_exactly_caution(
    risk: RiskLevel,
) -> None:
    assessment = _authorized_intervention(risk=risk)

    with pytest.raises(GuardrailViolation, match="exactly CAUTION"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_requires_confirmation() -> None:
    assessment = _authorized_intervention()
    assessment = assessment.model_copy(
        update={
            "intervention": assessment.intervention.model_copy(
                update={"requires_confirmation": False}
            )
        }
    )

    with pytest.raises(
        GuardrailViolation,
        match="did not require technician confirmation",
    ):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_requires_customer_authorization() -> None:
    assessment = _authorized_intervention(
        prerequisites=["Confirm that the recovery-key ID matches the supplied key ID."]
    )

    with pytest.raises(GuardrailViolation, match="customer authorization"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_requires_matching_key_id() -> None:
    assessment = _authorized_intervention(
        prerequisites=["Confirm explicit customer authorization."]
    )

    with pytest.raises(GuardrailViolation, match="matching recovery-key ID"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_requires_rollback() -> None:
    assessment = _authorized_intervention()
    assessment = assessment.model_copy(
        update={
            "intervention": assessment.intervention.model_copy(update={"rollback": None})
        }
    )

    with pytest.raises(GuardrailViolation, match="did not define rollback"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_intervention_with_all_controls_is_allowed() -> None:
    assessment = _authorized_intervention()

    assert validate_assessment(_authorized_locked_case(), assessment) is assessment


@pytest.mark.parametrize(
    "unsafe_step",
    [
        "Run Disable-BitLocker to decrypt the original drive.",
        "Remove the BitLocker key protectors before copying.",
        "Run manage-bde -protectors -delete D: before copying.",
        "Enable automatic unlock for the original volume.",
    ],
)
def test_prohibited_bitlocker_changes_are_rejected(unsafe_step: str) -> None:
    assessment = _authorized_intervention(steps=[unsafe_step])

    with pytest.raises(GuardrailViolation, match="decrypt the original"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_safety_language_does_not_trigger_prohibited_change_guard() -> None:
    assessment = _authorized_intervention(
        steps=[
            "Unlock the BitLocker volume without decrypting the original drive.",
            "Copy the authorized folders; never remove protectors or enable auto-unlock.",
        ]
    )

    assert validate_assessment(_authorized_locked_case(), assessment) is assessment


def test_without_phrase_cannot_negate_a_later_destructive_action() -> None:
    assessment = _authorized_intervention(
        steps=[
            "Copy files without a backup and then format the original drive."
        ]
    )

    with pytest.raises(GuardrailViolation, match="decrypt the original"):
        validate_assessment(_authorized_locked_case(), assessment)


def test_non_bitlocker_auto_unlock_is_not_a_false_positive() -> None:
    case = DiagnosticCase(
        title="Password manager setup",
        complaint="The user wants their password manager to open after sign-in.",
    )
    assessment = Assessment(
        summary="Configure the password manager preference.",
        technician_message="Enable its sign-in preference.",
        next_test=Proposal(
            key="password-manager-auto-unlock",
            title="Enable password-manager auto-unlock",
            rationale="Test the requested application behavior.",
            instructions=["Enable automatic unlock in the password manager settings."],
        ),
    )

    assert validate_assessment(case, assessment) is assessment
