import pytest

from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import Assessment, CompletedTest, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal


def completed_dns_case() -> DiagnosticCase:
    proposal = Proposal(
        key="initial-dns-scope",
        title="Check DNS resolution",
        rationale="Test the configured resolver",
        instructions=["Run nslookup google.com"],
    )
    return DiagnosticCase(
        title="DNS failure",
        complaint="Names do not resolve",
        completed_tests=[
            CompletedTest(
                proposal=proposal,
                result="DNS request timed out",
            )
        ],
    )


def test_vague_repeat_reason_is_rejected() -> None:
    proposal = Proposal(
        key="initial-dns-scope",
        title="Check DNS resolution",
        rationale="Test the configured resolver",
        instructions=["Run nslookup google.com"],
        repeat_reason=(
            "Re-validate current resolver behavior and isolate configuration."
        ),
    )
    assessment = Assessment(
        summary="DNS still fails",
        technician_message="Repeat the lookup",
        next_test=proposal,
    )

    with pytest.raises(GuardrailViolation, match="material changed condition"):
        validate_assessment(completed_dns_case(), assessment)


def test_rephrased_completed_command_is_rejected() -> None:
    proposal = Proposal(
        key="test-configured-dns-server",
        title="Test the configured DNS server",
        rationale="Confirm resolver behavior",
        instructions=[
            "Run nslookup google.com and record the response"
        ],
    )
    assessment = Assessment(
        summary="DNS still fails",
        technician_message="Check the configured resolver",
        next_test=proposal,
    )

    with pytest.raises(GuardrailViolation, match="specific repeat reason"):
        validate_assessment(completed_dns_case(), assessment)


def test_explicit_alternate_resolver_is_distinct() -> None:
    proposal = Proposal(
        key="compare-alternate-resolver",
        title="Query an alternate resolver",
        rationale="Compare resolver behavior",
        instructions=["Run nslookup google.com 1.1.1.1"],
    )
    assessment = Assessment(
        summary="Compare DNS servers",
        technician_message="Query the alternate resolver",
        next_test=proposal,
    )

    assert validate_assessment(completed_dns_case(), assessment) is assessment