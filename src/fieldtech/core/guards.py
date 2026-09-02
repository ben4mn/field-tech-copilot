from __future__ import annotations

import re

from fieldtech.core.models import Assessment, DiagnosticCase, RiskLevel


class GuardrailViolation(ValueError):
    """A model proposal violated deterministic workflow or safety policy."""


_UNSUPPORTED_POWER_TECHNIQUES = (
    re.compile(r"\bpowered\s+usb[ -]?c\s+hub\b", re.IGNORECASE),
    re.compile(r"\bexternal\s+battery(?:\s+pack)?\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(?:switch|circuit|method|power)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:inject|apply|feed)\w*\s+(?:external\s+)?(?:power|voltage|current)\b",
        re.IGNORECASE,
    ),
)

_INTRUSIVE_HARDWARE_STEPS = (
    re.compile(
        r"\b(?:open|remove)\s+(?:the\s+)?(?:laptop|computer|base cover|bottom cover)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdisconnect\s+(?:the\s+)?(?:internal\s+)?battery\b", re.IGNORECASE),
    re.compile(
        r"\b(?:probe|measure|test)\w*\s+(?:the\s+)?"
        r"(?:motherboard|system board|power rail)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:short|jump)\w*\s+(?:the\s+)?(?:pins|contacts|pads)\b", re.IGNORECASE),
)


def _procedure_text(action: object) -> str:
    instructions = getattr(action, "instructions", [])
    steps = getattr(action, "steps", [])
    return " ".join([getattr(action, "title", ""), *instructions, *steps])


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
        procedure = _procedure_text(action)

        if any(pattern.search(procedure) for pattern in _UNSUPPORTED_POWER_TECHNIQUES):
            raise GuardrailViolation(
                "Unsupported external-power or power-bypass technique was proposed"
            )

        if any(pattern.search(procedure) for pattern in _INTRUSIVE_HARDWARE_STEPS):
            if action.risk == RiskLevel.SAFE:
                raise GuardrailViolation(
                    "Intrusive hardware action was incorrectly marked safe"
                )
            if not action.requires_confirmation:
                raise GuardrailViolation(
                    "Intrusive hardware action did not require technician confirmation"
                )

        if action.risk == RiskLevel.DESTRUCTIVE and not action.requires_confirmation:
            raise GuardrailViolation(
                "Destructive action did not require technician confirmation"
            )

    return assessment