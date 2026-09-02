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
    re.compile(
        r"\b(?:short|jump)\w*\s+(?:the\s+)?(?:pins|contacts|pads)\b",
        re.IGNORECASE,
    ),
)

_MATERIAL_REPEAT_CHANGE = re.compile(
    r"\b(?:after|since|following|changed|reconfigured|replaced|restarted|rebooted|"
    r"reset|reconnected|reseated|swapped|installed|removed|enabled|disabled|updated|repaired)\b",
    re.IGNORECASE,
)

_NSLOOKUP_COMMAND = re.compile(
    r"\bnslookup\s+([a-z0-9_.:-]+)"
    r"(?:\s+((?:\d{1,3}\.){3}\d{1,3}|[0-9a-f:]{2,}))?",
    re.IGNORECASE,
)
_PING_COMMAND = re.compile(r"\bping\s+([a-z0-9_.:-]+)", re.IGNORECASE)
_IPCONFIG_COMMAND = re.compile(
    r"\bipconfig(?:\.exe)?\s*(/[a-z]+)?",
    re.IGNORECASE,
)


def _procedure_text(action: object) -> str:
    instructions = getattr(action, "instructions", [])
    steps = getattr(action, "steps", [])
    return " ".join([getattr(action, "title", ""), *instructions, *steps])


def _command_signatures(action: object) -> set[str]:
    procedure = _procedure_text(action)
    signatures: set[str] = set()

    for match in _NSLOOKUP_COMMAND.finditer(procedure):
        target = match.group(1).lower().rstrip(".")
        server = (match.group(2) or "default").lower()
        signatures.add(f"nslookup:{target}:{server}")

    for match in _PING_COMMAND.finditer(procedure):
        signatures.add(f"ping:{match.group(1).lower().rstrip('.')}")

    for match in _IPCONFIG_COMMAND.finditer(procedure):
        signatures.add(f"ipconfig:{(match.group(1) or 'default').lower()}")

    return signatures


def _require_material_repeat_reason(
    title: str,
    repeat_reason: str | None,
) -> None:
    reason = (repeat_reason or "").strip()

    if len(reason) < 12:
        raise GuardrailViolation(
            f"Model proposed completed test '{title}' without a specific repeat reason"
        )

    if not _MATERIAL_REPEAT_CHANGE.search(reason):
        raise GuardrailViolation(
            f"Model proposed completed test '{title}' without naming a material "
            "changed condition"
        )


def validate_assessment(
    case: DiagnosticCase,
    assessment: Assessment,
) -> Assessment:
    proposal = assessment.next_test

    if proposal is not None and proposal.key in case.completed_test_keys:
        _require_material_repeat_reason(
            proposal.title,
            proposal.repeat_reason,
        )

    if proposal is not None and proposal.key not in case.completed_test_keys:
        proposed_commands = _command_signatures(proposal)
        completed_commands = {
            signature
            for completed in case.completed_tests
            for signature in _command_signatures(completed.proposal)
        }

        if proposed_commands and proposed_commands.issubset(completed_commands):
            _require_material_repeat_reason(
                proposal.title,
                proposal.repeat_reason,
            )

    actions = [
        item
        for item in (assessment.next_test, assessment.intervention)
        if item is not None
    ]

    for action in actions:
        procedure = _procedure_text(action)

        if any(
            pattern.search(procedure)
            for pattern in _UNSUPPORTED_POWER_TECHNIQUES
        ):
            raise GuardrailViolation(
                "Unsupported external-power or power-bypass technique was proposed"
            )

        if any(
            pattern.search(procedure)
            for pattern in _INTRUSIVE_HARDWARE_STEPS
        ):
            if action.risk == RiskLevel.SAFE:
                raise GuardrailViolation(
                    "Intrusive hardware action was incorrectly marked safe"
                )

            if not action.requires_confirmation:
                raise GuardrailViolation(
                    "Intrusive hardware action did not require technician confirmation"
                )

        if (
            action.risk == RiskLevel.DESTRUCTIVE
            and not action.requires_confirmation
        ):
            raise GuardrailViolation(
                "Destructive action did not require technician confirmation"
            )

    return assessment