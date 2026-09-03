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


_UNSTABLE_STORAGE_EVIDENCE = re.compile(
    r"(?:not initialized|uninitialized|unknown partition|"
    r"disappears?|disconnects?|drops? offline|"
    r"spins?(?: up)?.{0,80}(?:stops?|down|disappears?)|"
    r"stops? spinning|clicking|read errors?|i/o errors?|"
    r"no (?:stable )?(?:mounted )?volume|"
    r"cannot stay (?:online|detected|enumerated))",
    re.IGNORECASE | re.DOTALL,
)

_FILE_LEVEL_COPY_ACTIONS = re.compile(
    r"(?:\brobocopy\b|\bxcopy\b|\bcopy-item\b|"
    r"\bfile explorer\b|\bdrag(?:-and-| and )drop\b|"
    r"\bcopy(?:ing)? (?:customer |user |readable |all )?files?\b)",
    re.IGNORECASE,
)

_BITLOCKER_LOCKED = re.compile(
    r"(?:\bbitlocker\b.{0,160}\blocked\b|"
    r"\blocked\b.{0,160}\bbitlocker\b)",
    re.IGNORECASE | re.DOTALL,
)

_MISSING_BITLOCKER_KEY = re.compile(
    r"\b(?:no|without|missing|unavailable|not provided|"
    r"has not provided|cannot find|does not have|don't have)\b"
    r".{0,120}\b(?:recovery )?key\b",
    re.IGNORECASE | re.DOTALL,
)

_PREMATURE_BITLOCKER_ACTION = re.compile(
    r"\b(?:get-disk|get-physicaldisk|get-storagereliabilitycounter|"
    r"robocopy|xcopy|copy-item|chkdsk|initialize-disk|"
    r"format-volume|unlock-bitlocker|bypass|password[- ]?crack)\b"
    r"|manage-bde\s+-unlock",
    re.IGNORECASE,
)

_BITLOCKER_KEY_REQUEST = re.compile(
    r"(?:request|obtain|retrieve|locate|provide|find)"
    r".{0,100}(?:bitlocker )?recovery key"
    r"|aka\.ms/(?:myrecoverykey|aadrecoverykey)"
    r"|customer.{0,100}(?:sign in|recovery key)"
    r"|(?:organization|company).{0,100}(?:IT|administrator)",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_DATA_ACCESS = re.compile(
    r"(?:\bunlock(?:ing)?\b.{0,120}\bbitlocker\b|"
    r"\bbitlocker\b.{0,120}\bunlock(?:ing)?\b|"
    r"\b(?:robocopy|xcopy|copy-item)\b|"
    r"\bcopy(?:ing)?\b.{0,120}\b(?:files?|folders?|documents?|pictures?)\b)",
    re.IGNORECASE | re.DOTALL,
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

    case_evidence = "\n".join(
        [case.complaint]
        + [
            observation.model_dump_json()
            for observation in case.observations
        ]
    )

    bitlocker_action = assessment.next_test or assessment.intervention

    if bitlocker_action is not None:
        bitlocker_action_text = "\n".join(
            [
                bitlocker_action.title,
                *(getattr(bitlocker_action, "instructions", None) or []),
                *(getattr(bitlocker_action, "steps", None) or []),
            ]
        )

        if (
            _BITLOCKER_LOCKED.search(case_evidence)
            and _MISSING_BITLOCKER_KEY.search(case_evidence)
            and _PREMATURE_BITLOCKER_ACTION.search(bitlocker_action_text)
            and not _BITLOCKER_KEY_REQUEST.search(bitlocker_action_text)
        ):
            raise GuardrailViolation(
                "Technical access was proposed for a locked BitLocker volume "
                "before an authorized recovery key was available"
            )

        if (
            _BITLOCKER_LOCKED.search(case_evidence)
            and _BITLOCKER_DATA_ACCESS.search(bitlocker_action_text)
        ):
            if bitlocker_action.risk == RiskLevel.SAFE:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access was incorrectly marked safe"
                )

            if not bitlocker_action.requires_confirmation:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not require "
                    "technician confirmation"
                )
    actions = [
        item
        for item in (assessment.next_test, assessment.intervention)
        if item is not None
    ]

    for action in actions:
        procedure = _procedure_text(action)
        storage_action_text = "\n".join(
            [
                action.title,
                *(getattr(action, "instructions", None) or []),
                *(getattr(action, "steps", None) or []),
            ]
        )

        if (
            _UNSTABLE_STORAGE_EVIDENCE.search(case_evidence)
            and _FILE_LEVEL_COPY_ACTIONS.search(storage_action_text)
        ):
            raise GuardrailViolation(
                "File-level copy was proposed for an unstable, disappearing, "
                "or inaccessible source drive"
            )

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