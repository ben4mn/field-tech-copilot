import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, DiagnosticCase, RiskLevel
from fieldtech.core.models import TestProposal as Proposal


def _locked_case() -> DiagnosticCase:
    return DiagnosticCase(
        title="BitLocker data transfer",
        complaint=(
            "The stable NVMe volume is locked by BitLocker. The customer "
            "is unavailable and has not provided the recovery key."
        ),
    )


def test_storage_health_test_is_rejected_when_bitlocker_key_is_missing() -> None:
    proposal = Proposal(
        key="collect-storage-health",
        title="Collect storage health information",
        rationale="Check the stable SSD.",
        instructions=[
            "Run Get-Disk, Get-PhysicalDisk, and Get-StorageReliabilityCounter."
        ],
    )
    assessment = Assessment(
        summary="The BitLocker volume is locked.",
        technician_message="Check storage health.",
        next_test=proposal,
    )

    with pytest.raises(
        GuardrailViolation,
        match="before an authorized recovery key was available",
    ):
        validate_assessment(_locked_case(), assessment)


def test_customer_recovery_key_request_is_allowed() -> None:
    proposal = Proposal(
        key="obtain-bitlocker-recovery-key",
        title="Have the customer retrieve the BitLocker recovery key",
        rationale="Authorized key access is required.",
        instructions=[
            "Have the customer sign in privately at "
            "https://aka.ms/myrecoverykey and provide the matching "
            "48-digit recovery key."
        ],
    )
    assessment = Assessment(
        summary="The BitLocker volume is locked.",
        technician_message="Request the authorized recovery key.",
        next_test=proposal,
    )

    assert validate_assessment(_locked_case(), assessment) is assessment


def _authorized_bitlocker_assessment(
    *,
    risk: RiskLevel,
    requires_confirmation: bool,
) -> Assessment:
    proposal = Proposal(
        key="authorized-bitlocker-access",
        title="Unlock the BitLocker volume and copy authorized folders",
        rationale="The matching authorized recovery key is available.",
        instructions=[
            "Unlock the BitLocker-protected drive through Windows.",
            "Copy only the authorized Documents and Pictures folders.",
        ],
        risk=risk,
        requires_confirmation=requires_confirmation,
        prerequisites=[
            "Confirm customer authorization and match the recovery-key ID."
        ],
        rollback="Relock or safely disconnect the original volume.",
    )
    return Assessment(
        summary="The authorized BitLocker recovery key is available.",
        technician_message="Unlock only after confirmation.",
        next_test=proposal,
    )


def _authorized_locked_case() -> DiagnosticCase:
    return DiagnosticCase(
        title="Authorized BitLocker recovery",
        complaint=(
            "The stable NVMe volume is locked by BitLocker. The customer "
            "has supplied the matching authorized 48-digit recovery key."
        ),
    )


def test_authorized_bitlocker_access_cannot_be_marked_safe() -> None:
    assessment = _authorized_bitlocker_assessment(
        risk=RiskLevel.SAFE,
        requires_confirmation=True,
    )

    with pytest.raises(
        GuardrailViolation,
        match="incorrectly marked safe",
    ):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_requires_confirmation() -> None:
    assessment = _authorized_bitlocker_assessment(
        risk=RiskLevel.CAUTION,
        requires_confirmation=False,
    )

    with pytest.raises(
        GuardrailViolation,
        match="did not require technician confirmation",
    ):
        validate_assessment(_authorized_locked_case(), assessment)


def test_authorized_bitlocker_access_with_confirmation_is_allowed() -> None:
    assessment = _authorized_bitlocker_assessment(
        risk=RiskLevel.CAUTION,
        requires_confirmation=True,
    )

    assert (
        validate_assessment(_authorized_locked_case(), assessment)
        is assessment
    )
