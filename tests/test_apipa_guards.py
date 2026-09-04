import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal


def _assessment(proposal: Proposal) -> Assessment:
    return Assessment(
        summary="The computer has unresolved APIPA addressing.",
        technician_message="Continue with the safest discriminating test.",
        next_test=proposal,
    )


def _apipa_case(complaint: str | None = None) -> DiagnosticCase:
    return DiagnosticCase(
        title="APIPA test",
        complaint=complaint
        or (
            "Windows 11 is connected to Wi-Fi but has no internet. "
            "IPCONFIG shows a 169.254 APIPA address."
        ),
    )


def test_dns_test_is_rejected_while_apipa_is_unresolved() -> None:
    proposal = Proposal(
        key="test-alternate-dns",
        title="Test alternate DNS servers",
        rationale="Check name resolution.",
        instructions=["Run nslookup example.com using 1.1.1.1."],
    )

    with pytest.raises(
        GuardrailViolation,
        match="before APIPA addressing was resolved",
    ):
        validate_assessment(_apipa_case(), _assessment(proposal))


def test_no_action_cannot_hide_premature_dns_guidance_in_summary() -> None:
    assessment = Assessment(
        summary="Set public DNS to 8.8.8.8 first.",
        technician_message="No structured action is proposed.",
        disposition="needs_information",
    )

    with pytest.raises(
        GuardrailViolation,
        match="before APIPA addressing was resolved",
    ):
        validate_assessment(_apipa_case(), assessment)


def test_valid_ipconfig_action_cannot_mask_premature_dns_summary() -> None:
    proposal = Proposal(
        key="inspect-ip-configuration",
        title="Inspect the complete adapter configuration",
        rationale="Determine whether Windows obtained a DHCP lease.",
        instructions=["Run ipconfig /all."],
    )
    assessment = _assessment(proposal).model_copy(
        update={"summary": "Set public DNS to 8.8.8.8 first."}
    )

    with pytest.raises(
        GuardrailViolation,
        match="before APIPA addressing was resolved",
    ):
        validate_assessment(_apipa_case(), assessment)


def test_negated_dns_guidance_is_allowed_while_apipa_is_unresolved() -> None:
    assessment = Assessment(
        summary="Do not test DNS or public internet before APIPA is resolved.",
        technician_message="Wait for valid addressing and gateway reachability.",
        disposition="needs_information",
    )

    assert validate_assessment(_apipa_case(), assessment) is assessment


def test_read_only_ipconfig_test_is_allowed_for_apipa() -> None:
    proposal = Proposal(
        key="inspect-ip-configuration",
        title="Inspect the complete adapter configuration",
        rationale="Determine whether Windows obtained a DHCP lease.",
        instructions=[
            "Run ipconfig /all and record the IPv4 address, DHCP status, "
            "default gateway, DHCP server, and lease information."
        ],
    )
    assessment = _assessment(proposal)

    assert validate_assessment(_apipa_case(), assessment) is assessment


def test_dns_test_is_allowed_after_addressing_and_gateway_recover() -> None:
    case = _apipa_case(
        "The computer previously had a 169.254 APIPA address. It now has "
        "a valid non-APIPA IPv4 DHCP lease and the default gateway is reachable."
    )
    proposal = Proposal(
        key="test-name-resolution",
        title="Test DNS name resolution",
        rationale="Addressing and gateway reachability are now confirmed.",
        instructions=["Run nslookup example.com."],
    )
    assessment = _assessment(proposal)

    assert validate_assessment(case, assessment) is assessment


def test_dns_test_is_allowed_after_valid_lease_and_direct_ip_access() -> None:
    case = _apipa_case(
        "The computer previously had a 169.254 APIPA address. It now has a valid "
        "non-APIPA IPv4 DHCP lease and direct IP access works to 1.1.1.1."
    )
    proposal = Proposal(
        key="test-name-resolution",
        title="Test DNS name resolution",
        rationale="Addressing and direct-IP access are now confirmed.",
        instructions=["Run nslookup example.com."],
    )
    assessment = _assessment(proposal)

    assert validate_assessment(case, assessment) is assessment


def test_dns_test_remains_blocked_when_gateway_is_not_reachable() -> None:
    case = _apipa_case(
        "The computer previously had a 169.254 APIPA address. It now has a valid "
        "non-APIPA IPv4 DHCP lease, but the default gateway is not reachable."
    )
    proposal = Proposal(
        key="test-name-resolution",
        title="Test DNS name resolution",
        rationale="Check name resolution.",
        instructions=["Run nslookup example.com."],
    )

    with pytest.raises(GuardrailViolation, match="before APIPA addressing was resolved"):
        validate_assessment(case, _assessment(proposal))
