from __future__ import annotations

from fieldtech.core.models import Assessment, DiagnosticCase, RiskLevel


class GuardrailViolation(ValueError):
    """A model proposal violated deterministic workflow or safety policy."""


def validate_assessment(case: DiagnosticCase, assessment: Assessment) -> Assessment:
    proposal = assessment.next_test
    if (
        proposal is not None
        and proposal.key in case.completed_test_keys
        and (not proposal.repeat_reason or len(proposal.repeat_reason.strip()) < 12)
    ):
        raise GuardrailViolation(
            f"Model proposed completed test '{proposal.title}' without a specific repeat reason"
        )

    actions = [item for item in (assessment.next_test, assessment.intervention) if item is not None]
    for action in actions:
        if action.risk == RiskLevel.DESTRUCTIVE and not action.requires_confirmation:
            raise GuardrailViolation("Destructive action did not require technician confirmation")

    return assessment
