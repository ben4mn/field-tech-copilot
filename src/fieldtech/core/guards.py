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


def _action_text(action: object) -> str:
    """Return all model-authored action text relevant to a safety decision."""
    return "\n".join(
        [
            getattr(action, "title", ""),
            getattr(action, "rationale", "") or "",
            *(getattr(action, "instructions", None) or []),
            *(getattr(action, "steps", None) or []),
        ]
    )


def _case_safety_evidence(case: DiagnosticCase) -> str:
    """Combine the complaint and all timestamped diagnostic result evidence."""
    events = [
        (observation.created_at, observation.text)
        for observation in case.observations
    ]
    events.extend(
        (completed.completed_at, completed.result)
        for completed in case.completed_tests
    )
    events.extend(
        (completed.completed_at, completed.result)
        for completed in case.completed_interventions
    )
    return "\n".join(
        [
            case.complaint,
            *(text for _, text in sorted(events, key=lambda event: event[0])),
        ]
    )


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
    r"(?:\b(?:drive|disk|ssd|hdd|media|volume|storage device)\b"
    r"[^.;:\n]{0,80}\b(?:unstable|failing|intermittent(?:ly)?|disappears?|vanishes?|"
    r"disconnect(?:s|ed|ing)?|drops? (?:offline|out)|inaccessible|unreadable)\b|"
    r"\b(?:unstable|failing|intermittent(?:ly)?|disappears?|vanishes?|"
    r"disconnect(?:s|ed|ing)?|"
    r"drops? (?:offline|out)|inaccessible|unreadable)\b[^.;:\n]{0,80}"
    r"\b(?:drive|disk|ssd|hdd|media|volume|storage device)\b|"
    r"not initialized|uninitialized|unknown partition|"
    r"\b(?:raw|unknown) (?:file ?system|volume|partition)\b|"
    r"spins?(?: up)?.{0,80}(?:stops?|down|disappears?)|"
    r"stops? spinning|clicking|read errors?|i/o (?:device )?errors?|"
    r"crc errors?|bad sectors?|smart (?:failure|failing)|device not ready|"
    r"no (?:stable )?(?:mounted )?volume|"
    r"cannot stay (?:online|detected|enumerated))",
    re.IGNORECASE | re.DOTALL,
)

_FILE_LEVEL_COPY_ACTIONS = re.compile(
    r"(?:\brobocopy\b|\bxcopy\b|\bcopy-item\b|"
    r"\bfile explorer\b|\bdrag(?:-and-| and )drop\b|"
    r"\bcopy(?:ing)? (?:customer |user |readable |all |authorized )?"
    r"(?:files?|folders?|data|documents?|pictures?)\b|"
    r"\b(?:extract|recover)(?:ing)? (?:customer |user |readable |all |authorized )?"
    r"(?:files?|folders?|data|documents?|pictures?)\b)",
    re.IGNORECASE,
)

_RECOVERY_ARTIFACT = re.compile(
    r"\b(?:disk|drive|forensic|recovery|sector[- ]by[- ]sector)?\s*image\b|"
    r"\b(?:verified |working |stable )?(?:clone|duplicate)\b|"
    r"\bstable (?:copy|working copy)\b",
    re.IGNORECASE,
)

_ARTIFACT_COMPLETED = re.compile(
    r"\b(?:complete|completed|finished|successfully created|creation succeeded)\b",
    re.IGNORECASE,
)

_ARTIFACT_VERIFIED = re.compile(
    r"\b(?:verified|validated|checksum(?:s)? matched|hash(?:es)? matched|"
    r"integrity (?:was )?(?:verified|confirmed)|verification (?:passed|succeeded))\b",
    re.IGNORECASE,
)

_COPY_FROM_RECOVERY_ARTIFACT = re.compile(
    r"(?:\b(?:copy|extract|recover)(?:ing)?\b.{0,100}"
    r"\b(?:files?|folders?|data)\b.{0,60}\bfrom\s+"
    r"(?:the |that )?(?:(?:completed|verified|mounted|read-only|working|stable) )*"
    r"(?:(?:disk|drive|forensic|recovery|sector[- ]by[- ]sector)\s+image|"
    r"image|clone|duplicate|stable (?:copy|working copy))\b|"
    r"\brobocopy\b.{0,80}\bfrom\s+(?:the |that )?"
    r"(?:(?:completed|verified|mounted|read-only|working|stable) )*"
    r"(?:image|clone|duplicate|stable (?:copy|working copy))\b|"
    r"\b(?:image|clone|duplicate|stable (?:copy|working copy))\b.{0,60}"
    r"\bas (?:the )?(?:read-only )?source\b.{0,100}"
    r"\b(?:copy|extract|recover|robocopy)\b)",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_LOCKED = re.compile(
    r"(?:\bbitlocker\b.{0,160}\blocked\b|"
    r"\blocked\b.{0,160}\bbitlocker\b|"
    r"\bbitlocker recovery (?:screen|prompt)\b|"
    r"\bbitlocker\b.{0,160}\bprompts? for\b.{0,80}\brecovery key\b|"
    r"\bbitlocker(?:-encrypted)?\b.{0,160}"
    r"\b(?:(?:cannot|can't) (?:be )?accessed|inaccessible|access denied)\b)",
    re.IGNORECASE | re.DOTALL,
)

_MISSING_BITLOCKER_KEY = re.compile(
    r"(?:\b(?:no|without|missing|unavailable|not provided|"
    r"has not provided|cannot find|does not have|doesn't have|don't have)\b"
    r".{0,120}\b(?:bitlocker |recovery )?key\b|"
    r"\b(?:bitlocker |recovery )?key\b.{0,80}"
    r"\b(?:is |was |remains? |has not been )?"
    r"(?:missing|unavailable|not available|not provided|not found|not supplied|"
    r"incorrect|wrong|does not match|doesn't match)\b|"
    r"\b(?:recovery[- ]key )?id mismatch\b)",
    re.IGNORECASE | re.DOTALL,
)

_AVAILABLE_BITLOCKER_KEY = re.compile(
    r"(?:\b(?:authorized|matching|correct)\b.{0,80}"
    r"\b(?:bitlocker |recovery )?key\b|"
    r"\b(?:bitlocker |recovery )?key\b.{0,80}"
    r"\b(?:available|provided|supplied|retrieved|obtained|confirmed|matches?)\b|"
    r"\b(?:provided|supplied|retrieved|obtained|confirmed)\b.{0,80}"
    r"\b(?:bitlocker |recovery )?key\b)",
    re.IGNORECASE | re.DOTALL,
)

_TECHNICAL_BITLOCKER_ACTION = re.compile(
    r"\b(?:get-disk|get-physicaldisk|get-storagereliabilitycounter|"
    r"get-bitlockervolume|robocopy|xcopy|copy-item|chkdsk|initialize-disk|"
    r"format-volume|unlock-bitlocker|mount|bypass|password[- ]?crack)\b|"
    r"\bmanage-bde\b|\bunlock(?:ing)?\b.{0,100}\b(?:volume|drive|disk)\b|"
    r"\b(?:volume|drive|disk)\b.{0,100}\bunlock(?:ing)?\b|"
    r"\b(?:open|access|browse|copy|read|transfer|move|export)\b.{0,100}"
    r"\b(?:volume|drive|files?|folders?|documents?|pictures?)\b",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_KEY_RETRIEVAL = re.compile(
    r"(?:request|obtain|retrieve|locate|provide|find|look up|recover)"
    r".{0,100}(?:bitlocker )?recovery key"
    r"|aka\.ms/(?:myrecoverykey|aadrecoverykey)",
    re.IGNORECASE | re.DOTALL,
)

_AUTHORIZED_KEY_RETRIEVER = re.compile(
    r"\b(?:customer|client|device owner|account owner|authorized (?:user|representative)|"
    r"authorized (?:IT|administrator)|organization(?:'s)?.{0,30}(?:IT|administrator)|"
    r"company(?:'s)?.{0,30}(?:IT|administrator))\b",
    re.IGNORECASE,
)

_PRIVATE_KEY_RETRIEVAL = re.compile(
    r"\b(?:privately|private (?:browser|session|device)|securely|secure channel|"
    r"themselves|their own (?:trusted )?device|a device only they control|"
    r"without shar(?:e|ing) (?:their )?(?:password|credentials))\b",
    re.IGNORECASE,
)

_FORBIDDEN_CREDENTIAL_HANDLING = re.compile(
    r"\b(?:ask|request|collect|provide|share|send|disclose)\b.{0,80}"
    r"\b(?:microsoft |account )?(?:password|credentials)\b|"
    r"\b(?:record|store|retain|save|photograph|email|message|upload|send|share|disclose)\b"
    r".{0,80}"
    r"\b(?:bitlocker |recovery )?key\b|"
    r"\b(?:paste|write)\b.{0,80}\b(?:bitlocker |recovery )?key\b.{0,30}"
    r"\b(?:ticket|notes?|record|chat)\b|"
    r"\b(?:take|keep)\b.{0,30}\b(?:photo|copy)\b.{0,80}"
    r"\b(?:bitlocker |recovery )?key\b",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_DATA_ACCESS = re.compile(
    r"(?:\bunlock(?:ing)?\b.{0,120}\bbitlocker\b|"
    r"\bbitlocker\b.{0,120}\bunlock(?:ing)?\b|"
    r"\b(?:unlock-bitlocker|manage-bde\s+-unlock)\b|"
    r"\bunlock(?:ing)?\b.{0,100}\b(?:volume|drive|disk)\b|"
    r"\b(?:volume|drive|disk)\b.{0,100}\bunlock(?:ing)?\b|"
    r"\b(?:robocopy|xcopy|copy-item)\b|"
    r"\bfile explorer\b|"
    r"\b(?:copy|open|access|browse|extract|transfer|move|export)(?:ing)?\b.{0,120}"
    r"\b(?:files?|folders?|documents?|pictures?|customer data)\b)",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_AUTHORIZATION_PREREQUISITE = re.compile(
    r"\b(?:customer|client|owner)\s+(?:authorization|authorisation|consent|approval)\b|"
    r"\b(?:authorization|authorisation|consent|approval)\b.{0,60}"
    r"\b(?:customer|client|owner)\b",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_KEY_ID_PREREQUISITE = re.compile(
    r"\b(?:match|matching|verify|verified|confirm|confirmed)\b.{0,80}"
    r"\b(?:recovery[- ]key|bitlocker|displayed)\s+(?:key )?id(?:entifier)?\b|"
    r"\b(?:recovery[- ]key|bitlocker|displayed)\s+(?:key )?id(?:entifier)?\b.{0,80}"
    r"\b(?:match|matching|verify|verified|confirm|confirmed)\b",
    re.IGNORECASE | re.DOTALL,
)

_PROHIBITED_BITLOCKER_CHANGES = (
    re.compile(r"\bdisable-bitlocker\b", re.IGNORECASE),
    re.compile(r"\bmanage-bde\b.{0,100}\s-off\b", re.IGNORECASE),
    re.compile(r"\bremove-bitlockerkeyprotector\b", re.IGNORECASE),
    re.compile(
        r"\bmanage-bde\b.{0,100}-protectors\b.{0,60}-(?:delete|disable)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:remove|delete|clear|disable)\b.{0,80}"
        r"\b(?:bitlocker |key )?protector(?:s)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\benable-bitlockerautounlock\b", re.IGNORECASE),
    re.compile(r"\bmanage-bde\b.{0,100}-autounlock\b.{0,40}-enable\b", re.IGNORECASE),
    re.compile(
        r"\b(?:enable|turn on)\b.{0,60}"
        r"\bauto(?:matic)?(?:[- ]bitlocker)?[- ]?unlock\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bturn off\b.{0,60}\bbitlocker\b", re.IGNORECASE),
    re.compile(
        r"\bremove\b.{0,60}\bencryption\b.{0,60}\b(?:original|source)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdecrypt(?:ing|ion)?\b.{0,100}\b(?:original|source)\b"
        r"|\b(?:original|source)\b.{0,100}\bdecrypt(?:ing|ion)?\b",
        re.IGNORECASE,
    ),
)

_NEGATED_DIRECTIVE = re.compile(
    r"\b(?:do not|don't|must not|should not|never|avoid|without)\b[^.;:\n]{0,80}$",
    re.IGNORECASE,
)

_NEGATED_EVIDENCE = re.compile(
    r"\b(?:not|never|no longer|failed to|could not|couldn't|unable to)\b"
    r"[^.;:\n]{0,40}$",
    re.IGNORECASE,
)

_APIPA_EVIDENCE = re.compile(
    r"(?:\bAPIPA\b|\b169\.254(?:\.\d{1,3}){0,2}\b)",
    re.IGNORECASE,
)

_PREMATURE_APIPA_DNS_TEST = re.compile(
    r"(?:\bDNS\b|\bname[- ]resolution\b|\bnslookup\b|"
    r"\bresolve-dnsname\b|\bset-dnsclientserveraddress\b|"
    r"\b(?:alternate|public)\s+DNS\b|"
    r"\b(?:8\.8\.8\.8|1\.1\.1\.1)\b|"
    r"\b(?:public internet|internet reachability|public IP)\b)",
    re.IGNORECASE | re.DOTALL,
)

_APIPA_ADDRESSING_RECOVERED = re.compile(
    r"(?:\b(?:valid|normal|non[- ]?APIPA)\b.{0,160}"
    r"\b(?:IPv4|IP address|DHCP lease|lease)\b.{0,240}"
    r"\b(?:default gateway|gateway|direct IP)\b.{0,100}"
    r"\b(?:reachable|responded|responds|successful)\b|"
    r"\b(?:default gateway|gateway|direct IP)\b.{0,100}"
    r"\b(?:reachable|responded|responds|successful)\b.{0,240}"
    r"\b(?:valid|normal|non[- ]?APIPA)\b.{0,160}"
    r"\b(?:IPv4|IP address|DHCP lease|lease)\b)",
    re.IGNORECASE | re.DOTALL,
)


def _contains_nonnegated_pattern(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
) -> bool:
    for pattern in patterns:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 90) : match.start()]
            if not _NEGATED_DIRECTIVE.search(prefix):
                return True
    return False


def _latest_nonnegated_match_end(text: str, pattern: re.Pattern[str]) -> int:
    latest = -1
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 50) : match.start()]
        if not _NEGATED_EVIDENCE.search(prefix):
            latest = match.end()
    return latest


def _bitlocker_key_is_missing(evidence: str) -> bool:
    missing = _latest_nonnegated_match_end(evidence, _MISSING_BITLOCKER_KEY)
    available = _latest_nonnegated_match_end(evidence, _AVAILABLE_BITLOCKER_KEY)
    return missing >= 0 and missing >= available


def _has_completed_verified_recovery_artifact(evidence: str) -> bool:
    for artifact in _RECOVERY_ARTIFACT.finditer(evidence):
        start = max(0, artifact.start() - 220)
        end = min(len(evidence), artifact.end() + 220)
        window = evidence[start:end]
        completed = _latest_nonnegated_match_end(window, _ARTIFACT_COMPLETED) >= 0
        verified = _latest_nonnegated_match_end(window, _ARTIFACT_VERIFIED) >= 0
        if completed and verified:
            return True
    return False


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

    case_evidence = _case_safety_evidence(case)
    apipa_action = assessment.next_test or assessment.intervention

    if apipa_action is not None:
        apipa_action_text = _action_text(apipa_action)

        if (
            _APIPA_EVIDENCE.search(case_evidence)
            and _PREMATURE_APIPA_DNS_TEST.search(apipa_action_text)
            and not _APIPA_ADDRESSING_RECOVERED.search(case_evidence)
        ):
            raise GuardrailViolation(
                "DNS or public-internet testing was proposed before "
                "APIPA addressing was resolved"
            )

    bitlocker_action = assessment.next_test or assessment.intervention

    if bitlocker_action is not None:
        bitlocker_action_text = _action_text(bitlocker_action)
        bitlocker_locked = _BITLOCKER_LOCKED.search(case_evidence) is not None
        bitlocker_context = bitlocker_locked or "bitlocker" in case_evidence.lower()

        if bitlocker_context and _contains_nonnegated_pattern(
            bitlocker_action_text, _PROHIBITED_BITLOCKER_CHANGES
        ):
            raise GuardrailViolation(
                "BitLocker action attempted to decrypt the original, remove "
                "protectors, or enable automatic unlocking"
            )

        if bitlocker_locked and _bitlocker_key_is_missing(case_evidence):
            if _contains_nonnegated_pattern(
                bitlocker_action_text,
                (_TECHNICAL_BITLOCKER_ACTION,),
            ):
                raise GuardrailViolation(
                    "Technical access was proposed for a locked BitLocker volume "
                    "before an authorized recovery key was available"
                )

            if _contains_nonnegated_pattern(
                bitlocker_action_text,
                (_FORBIDDEN_CREDENTIAL_HANDLING,),
            ):
                raise GuardrailViolation(
                    "BitLocker key retrieval requested credentials or retained "
                    "sensitive recovery-key material"
                )

            if not (
                _BITLOCKER_KEY_RETRIEVAL.search(bitlocker_action_text)
                and _AUTHORIZED_KEY_RETRIEVER.search(bitlocker_action_text)
                and _PRIVATE_KEY_RETRIEVAL.search(bitlocker_action_text)
            ):
                raise GuardrailViolation(
                    "A locked BitLocker volume without a key permits only private, "
                    "authorized recovery-key retrieval guidance"
                )

        if bitlocker_context and _BITLOCKER_DATA_ACCESS.search(bitlocker_action_text):
            if assessment.intervention is None:
                raise GuardrailViolation(
                    "BitLocker unlocking or customer-data access must be an intervention"
                )

            if bitlocker_action.risk != RiskLevel.CAUTION:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access must be exactly CAUTION, never SAFE "
                    "or DESTRUCTIVE"
                )

            if not bitlocker_action.requires_confirmation:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not require "
                    "technician confirmation"
                )

            prerequisites = "\n".join(bitlocker_action.prerequisites)
            if not _BITLOCKER_AUTHORIZATION_PREREQUISITE.search(prerequisites):
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not require explicit "
                    "customer authorization"
                )

            if not _BITLOCKER_KEY_ID_PREREQUISITE.search(prerequisites):
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not require a matching "
                    "recovery-key ID"
                )

            if not (bitlocker_action.rollback or "").strip():
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not define rollback"
                )

    actions = [
        item
        for item in (assessment.next_test, assessment.intervention)
        if item is not None
    ]

    for action in actions:
        procedure = _procedure_text(action)
        storage_action_text = _action_text(action)

        if (
            _UNSTABLE_STORAGE_EVIDENCE.search(case_evidence)
            and _FILE_LEVEL_COPY_ACTIONS.search(storage_action_text)
            and not (
                _has_completed_verified_recovery_artifact(case_evidence)
                and _COPY_FROM_RECOVERY_ARTIFACT.search(storage_action_text)
            )
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
