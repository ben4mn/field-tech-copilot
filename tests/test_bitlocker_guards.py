import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, DiagnosticCase
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
