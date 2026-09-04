from __future__ import annotations

import re

from fieldtech.core.models import (
    Assessment,
    DiagnosticCase,
    Disposition,
    RiskLevel,
    action_fingerprint,
)
from fieldtech.core.privacy import SensitiveDataError, reject_sensitive_input


class GuardrailViolation(ValueError):
    """A model proposal violated deterministic workflow or safety policy."""


_UNSUPPORTED_POWER_TECHNIQUES = (
    re.compile(r"\bpowered\s+usb[ -]?c\s+hub\b", re.IGNORECASE),
    re.compile(r"\bexternal\s+battery(?:\s+pack)?\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(?:switch|circuit|method|power)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:inject|apply|feed)\w*\s+(?:external\s+)?"
        r"(?:power|voltage|current|\d+(?:[.]\d+)?\s*(?:v|volts?))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:bench|laboratory|lab|external|dc)\s+(?:dc\s+)?(?:power\s+)?supply\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:connect|attach|wire)\w*\b.{0,80}\b(?:power|voltage|current)\b"
        r".{0,80}\b(?:motherboard|system board|power rail|pins?|pads?)\b",
        re.IGNORECASE | re.DOTALL,
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
_READ_ONLY_COMMAND = re.compile(
    r"\b(get-disk|get-physicaldisk|get-storagereliabilitycounter|"
    r"get-bitlockervolume|get-volume)\b",
    re.IGNORECASE,
)
_POWERCFG_COMMAND = re.compile(r"\bpowercfg(?:\.exe)?\s+(/[a-z]+)", re.IGNORECASE)


def _procedure_text(action: object) -> str:
    instructions = getattr(action, "instructions", [])
    steps = getattr(action, "steps", [])
    return "\n".join(
        [
            getattr(action, "title", ""),
            *instructions,
            *steps,
            *(getattr(action, "verification", None) or []),
        ]
    )


def _action_text(action: object) -> str:
    """Return all model-authored action text relevant to a safety decision."""
    return "\n".join(
        [
            getattr(action, "title", ""),
            getattr(action, "rationale", "") or "",
            *(getattr(action, "instructions", None) or []),
            *(getattr(action, "steps", None) or []),
            *(getattr(action, "expected_results", None) or []),
            *(getattr(action, "verification", None) or []),
            *(getattr(action, "prerequisites", None) or []),
            getattr(action, "rollback", "") or "",
            getattr(action, "repeat_reason", "") or "",
        ]
    )


def _assessment_narrative_text(assessment: Assessment) -> str:
    """Return model-authored narrative that can reach the UI or an export."""
    return "\n".join(
        [
            assessment.summary,
            assessment.technician_message,
            *assessment.clarifying_questions,
            *assessment.uncertainties,
            *(
                value
                for hypothesis in assessment.hypotheses
                for value in (
                    hypothesis.label,
                    *hypothesis.evidence_for,
                    *hypothesis.evidence_against,
                )
            ),
        ]
    )


def _case_safety_evidence(case: DiagnosticCase) -> str:
    """Combine only observed facts, never aspirational proposal wording."""
    events = [
        (observation.created_at, observation.text)
        for observation in case.observations
    ]
    events.extend(
        (
            completed.completed_at,
            f"Recorded test outcome: {completed.outcome}. Result: {completed.result}",
        )
        for completed in case.completed_tests
    )
    events.extend(
        (
            completed.completed_at,
            "Recorded intervention outcome: "
            f"{completed.outcome}. Result: {completed.result}",
        )
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

    for match in _READ_ONLY_COMMAND.finditer(procedure):
        signatures.add(f"command:{match.group(1).lower()}")

    for match in _POWERCFG_COMMAND.finditer(procedure):
        signatures.add(f"powercfg:{match.group(1).lower()}")

    return signatures


def _procedure_fingerprint(action: object) -> str:
    steps = [
        *(getattr(action, "instructions", None) or []),
        *(getattr(action, "steps", None) or []),
    ]
    return action_fingerprint(" | ".join(steps))


def _require_material_repeat_reason(
    title: str,
    repeat_reason: str | None,
    action_kind: str = "test",
) -> None:
    reason = (repeat_reason or "").strip()

    if len(reason) < 12:
        raise GuardrailViolation(
            f"Model proposed completed {action_kind} '{title}' without a specific repeat reason"
        )

    if not _MATERIAL_REPEAT_CHANGE.search(reason):
        raise GuardrailViolation(
            f"Model proposed completed {action_kind} '{title}' without naming a material "
            "changed condition"
        )


_UNSTABLE_STORAGE_EVIDENCE = re.compile(
    r"(?:\b(?:drive|disk|ssd|hdd|media|volume|storage device)\b"
    r"[^.;:\n]{0,80}\b(?:unstable|failing|intermittent(?:ly)?|"
    r"disappear(?:s|ed|ing)?|vanish(?:es|ed|ing)?|"
    r"disconnect(?:s|ed|ing)?|drops? (?:offline|out)|inaccessible|unreadable)\b|"
    r"\b(?:unstable|failing|intermittent(?:ly)?|disappear(?:s|ed|ing)?|"
    r"vanish(?:es|ed|ing)?|"
    r"disconnect(?:s|ed|ing)?|"
    r"drops? (?:offline|out)|inaccessible|unreadable)\b[^.;:\n]{0,80}"
    r"\b(?:drive|disk|ssd|hdd|media|volume|storage device)\b|"
    r"not initialized|uninitialized|unknown partition|"
    r"\b(?:raw|unknown) (?:file ?system|volume|partition)\b|"
    r"spins?(?: up)?.{0,80}(?:stops?|down|disappears?)|"
    r"stops? spinning|click(?:s|ing)?|"
    r"(?:makes?|making)\s+(?:a\s+)?click(?:ing)?(?:\s+sounds?)?|"
    r"click(?:ing)?\s+sounds?|"
    r"(?:drops?|goes?|went)\s+offline|read errors?|i/o (?:device )?errors?|"
    r"crc errors?|bad sectors?|smart (?:failure|failing)|device not ready|"
    r"no (?:stable )?(?:mounted )?volume|"
    r"cannot stay (?:online|detected|enumerated))",
    re.IGNORECASE | re.DOTALL,
)

_FILE_LEVEL_COPY_ACTIONS = re.compile(
    r"(?:\brobocopy\b|\bxcopy\b|\bcopy-item\b|\bteracopy\b|\bfastcopy\b|\brsync\b|"
    r"\bfile explorer\b|\bdrag(?:-and-| and )drop\b|"
    r"\b(?:copy|extract|recover|transfer|move|mirror|sync|backup)(?:ing)?\b.{0,80}"
    r"(?:files?|folders?|data|documents?|pictures?)\b)",
    re.IGNORECASE | re.DOTALL,
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
    r"(?:\b(?:copy|extract|recover|transfer|move|mirror|sync|backup)(?:ing)?\b.{0,100}"
    r"\b(?:files?|folders?|data)\b.{0,60}\bfrom\s+"
    r"(?:the |that )?(?:(?:completed|verified|mounted|read-only|working|stable) )*"
    r"(?:(?:disk|drive|forensic|recovery|sector[- ]by[- ]sector)\s+image|"
    r"image|clone|duplicate|stable (?:copy|working copy))\b|"
    r"\b(?:robocopy|xcopy|copy-item|teracopy|fastcopy|rsync)\b.{0,100}"
    r"\bfrom\s+(?:the |that )?"
    r"(?:(?:completed|verified|mounted|read-only|working|stable) )*"
    r"(?:image|clone|duplicate|stable (?:copy|working copy))\b|"
    r"\b(?:image|clone|duplicate|stable (?:copy|working copy))\b.{0,60}"
    r"\bas (?:the )?(?:read-only )?source\b.{0,100}"
    r"\b(?:copy|extract|recover|transfer|move|mirror|sync|backup|robocopy|xcopy|"
    r"copy-item|teracopy|fastcopy|rsync)\b)",
    re.IGNORECASE | re.DOTALL,
)

_COPY_FROM_ORIGINAL_MEDIA = re.compile(
    r"\b(?:copy|extract|recover|transfer|move|mirror|sync|backup)(?:ing)?\b.{0,100}"
    r"\b(?:files?|folders?|data|documents?|pictures?)\b.{0,80}\bfrom\s+"
    r"(?:the )?(?:original|source|failing|unstable)\s+(?:drive|disk|media|volume)\b|"
    r"\b(?:original|source|failing|unstable)\s+(?:drive|disk|media|volume)\b.{0,80}"
    r"\bas (?:the )?source\b",
    re.IGNORECASE | re.DOTALL,
)

_DESTRUCTIVE_MEDIA_ACTION = re.compile(
    r"\b(?:format|initialize|initialise|erase|wipe|repartition)\w*\b|"
    r"\brepair\w*\b.{0,50}\b(?:file ?system|volume|drive|disk|it|this)\b|"
    r"\brepair-volume\b|"
    r"\bdelete\b.{0,60}\bpartition\b|"
    r"\bchkdsk\b.{0,80}\s/(?:f|r|x)\b",
    re.IGNORECASE | re.DOTALL,
)

_SECTOR_IMAGING_ACTION = re.compile(
    r"\bddrescue\b|"
    r"\b(?:create|capture|make|acquire|clone)\w*\b.{0,80}"
    r"\b(?:sector(?:[- ]by[- ]sector|[- ]level)?\s+)?(?:disk |drive |recovery )?image\b|"
    r"\b(?:image|clone)\s+(?:the\s+)?"
    r"(?:(?:original|source|failing|unstable)\s+)?(?:drive|disk|media)\b|"
    r"\bclone\w*\b.{0,60}\b(?:original|source|failing|unstable)\s+(?:drive|disk|media)\b",
    re.IGNORECASE | re.DOTALL,
)

_SEVERE_MECHANICAL_FAILURE = re.compile(
    r"\b(?:click(?:s|ing)?|grind(?:s|ing)?|overheat(?:s|ing|ed)?|"
    r"repeatedly spins? (?:up and down|down)|disappears? within seconds|"
    r"cannot remain detected|will not remain detected)\b",
    re.IGNORECASE,
)

_IRREPLACEABLE_DATA = re.compile(
    r"\b(?:irreplaceable|no backup|without (?:a )?backup|only copy|"
    r"cannot be replaced|can't be replaced|unique customer data)\b",
    re.IGNORECASE,
)

_POWER_OFF_FAILED_MEDIA = re.compile(
    r"\b(?:power|turn|switch|shut)\w*\s+(?:the\s+)?"
    r"(?:(?:original|source|failing|unstable)\s+)?"
    r"(?:drive|disk|media|device|system|computer|machine|it)\s+off\b|"
    r"\bpower[- ]off\b",
    re.IGNORECASE,
)

_PROFESSIONAL_DATA_RECOVERY = re.compile(
    r"\b(?:professional|specialist|laboratory|lab)(?:\s+data)?\s+recovery\b|"
    r"\bdata\s+recovery\s+(?:professional|specialist|laboratory|lab)\b",
    re.IGNORECASE,
)

_CONTINUE_FAILED_MEDIA_ACCESS = re.compile(
    r"\b(?:continue|keep|resume|retry|repeat|attempt|try)\w*\b.{0,100}"
    r"\b(?:read|access|scan|test|diagnos|image|clone|copy|recover)\w*\b|"
    r"\b(?:read|access|scan|test|diagnos|benchmark|query|inspect)\w*\b.{0,100}"
    r"\b(?:original|source|failing|unstable)\s+(?:drive|disk|media)\b|"
    r"\b(?:get-disk|get-physicaldisk|get-storagereliabilitycounter|smartctl|"
    r"crystaldiskinfo)\b",
    re.IGNORECASE | re.DOTALL,
)

_IMAGING_RISK_ACCEPTANCE = re.compile(
    r"\b(?:customer|client|owner)\b.{0,80}\b(?:accept|acknowledge|approve|consent)\w*\b"
    r".{0,80}\b(?:risk|further degradation|data loss|recoverability)\b|"
    r"\b(?:accept|acknowledge|approve|consent)\w*\b.{0,80}\b(?:risk|data loss)\b"
    r".{0,80}\b(?:customer|client|owner)\b",
    re.IGNORECASE | re.DOTALL,
)

_IMAGING_SOURCE_IDENTITY = re.compile(
    r"\b(?:verify|confirm|record)\w*\b.{0,100}\bsource\b.{0,100}"
    r"\b(?:model|serial|capacity|device path|identity)\b|"
    r"\bsource\b.{0,100}\b(?:model|serial|capacity|device path|identity)\b"
    r".{0,100}\b(?:verify|confirm|record)\w*\b",
    re.IGNORECASE | re.DOTALL,
)

_IMAGING_DESTINATION = re.compile(
    r"\b(?:verify|confirm)\w*\b.{0,100}\bdestination\b.{0,100}"
    r"\b(?:healthy|empty|larger|capacity)\b|"
    r"\bdestination\b.{0,100}\b(?:healthy|empty|larger|capacity)\b",
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
    r"\b(?:format|initialize|initialise|erase|wipe|repartition|repair)\w*\b.{0,100}"
    r"\b(?:locked|bitlocker|drive|disk|volume|media)\b|"
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
    r"\b(?:ask|request|collect|provide|share|send|disclose|tell|give|hand|show)\b.{0,80}"
    r"\b(?:microsoft |account )?(?:password|credentials)\b|"
    r"\b(?:record|store|retain|save|photograph|email|message|upload|send|share|"
    r"disclose|tell|give|hand|show)\b"
    r".{0,80}"
    r"\b(?:bitlocker |recovery )?key\b|"
    r"\b(?:paste|write)\b.{0,80}\b(?:bitlocker |recovery )?key\b.{0,30}"
    r"\b(?:ticket|notes?|record|chat)\b|"
    r"\b(?:take|keep)\b.{0,30}\b(?:photo|copy)\b.{0,80}"
    r"\b(?:bitlocker |recovery )?key\b",
    re.IGNORECASE | re.DOTALL,
)

_BITLOCKER_DATA_ACCESS = re.compile(
    r"(?:\bunlock(?:ing)?\b|"
    r"\b(?:unlock-bitlocker|manage-bde\s+-unlock)\b|"
    r"\b(?:robocopy|xcopy|copy-item)\b|"
    r"\bfile explorer\b|"
    r"\b(?:enter|input|type|submit|use)(?:ing)?\b.{0,120}"
    r"\b(?:bitlocker )?recovery key\b|"
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
    _DESTRUCTIVE_MEDIA_ACTION,
)

_NEGATED_DIRECTIVE = re.compile(
    r"(?:\b(?:do not|don't|must not|should not|never|avoid)\b[^.;:\n]{0,45}|"
    r"\bwithout(?:\s+first)?\s*)$",
    re.IGNORECASE,
)

_NEGATED_ASSERTION_SUFFIX = re.compile(
    r"^\s*(?:(?:is|was|would be|remains?|seems?)\s+)?"
    r"(?:not\s+(?:needed|required|necessary|recommended)|unnecessary|unsafe|optional)\b",
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
    r"\b(?:reachable|responded|responds|successful|accessible|"
    r"access (?:works|worked|succeeded))\b|"
    r"\b(?:default gateway|gateway|direct IP)\b.{0,100}"
    r"\b(?:reachable|responded|responds|successful|accessible|"
    r"access (?:works|worked|succeeded))\b.{0,240}"
    r"\b(?:valid|normal|non[- ]?APIPA)\b.{0,160}"
    r"\b(?:IPv4|IP address|DHCP lease|lease)\b)",
    re.IGNORECASE | re.DOTALL,
)

_NEGATED_NETWORK_RECOVERY = re.compile(
    r"\b(?:no|not|without|missing|invalid)\b.{0,40}"
    r"\b(?:valid|normal|non[- ]?APIPA|IPv4|IP address|DHCP lease|gateway)\b|"
    r"\b(?:gateway|direct IP)\b.{0,40}"
    r"\b(?:not reachable|unreachable|failed|no response|timed out)\b",
    re.IGNORECASE | re.DOTALL,
)


def _contains_nonnegated_pattern(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
) -> bool:
    for segment in text.splitlines():
        for pattern in patterns:
            for match in pattern.finditer(segment):
                prefix = segment[max(0, match.start() - 90) : match.start()]
                if not _NEGATED_DIRECTIVE.search(prefix):
                    return True
    return False


def _contains_affirmative_pattern(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
) -> bool:
    """Require a positive assertion, not merely a non-prefixed keyword."""
    for segment in text.splitlines():
        for pattern in patterns:
            for match in pattern.finditer(segment):
                prefix = segment[max(0, match.start() - 90) : match.start()]
                suffix = segment[match.end() : match.end() + 60]
                if _NEGATED_DIRECTIVE.search(prefix):
                    continue
                if _NEGATED_ASSERTION_SUFFIX.search(suffix):
                    continue
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


def _has_completed_verified_recovery_artifact(case: DiagnosticCase) -> bool:
    completed_actions = [
        *(
            (item.outcome, item.proposal, item.result)
            for item in case.completed_tests
        ),
        *(
            (item.outcome, item.intervention, item.result)
            for item in case.completed_interventions
        ),
    ]
    for outcome, action, result in completed_actions:
        normalized_outcome = outcome.casefold()
        if normalized_outcome in {"fail", "failed", "blocked", "inconclusive"}:
            continue
        procedure = _procedure_text(action)
        combined = f"{procedure}\n{result}"
        if not _RECOVERY_ARTIFACT.search(combined):
            continue
        if re.search(
            r"\b(?:not|never|isn't|wasn't|failed to|could not|unable to)\b.{0,60}"
            r"\b(?:verify|verified|validate|validated|checksum|hash|integrity)\w*\b|"
            r"\bverification\b.{0,40}\b(?:failed|incomplete|not performed)\b",
            result,
            re.IGNORECASE | re.DOTALL,
        ):
            continue
        result_verified = _latest_nonnegated_match_end(result, _ARTIFACT_VERIFIED) >= 0
        result_completed = _latest_nonnegated_match_end(result, _ARTIFACT_COMPLETED) >= 0
        if normalized_outcome == "pass":
            if result_verified:
                return True
            # A recorded pass plus an explicit completion result means the named
            # create-and-verify procedure, including its verification step, passed.
            if result_completed and _ARTIFACT_VERIFIED.search(procedure):
                return True
        elif result_completed and result_verified:
            # Legacy records used the default "other" outcome. Require both facts
            # explicitly in their result before trusting them as a recovery source.
            return True
    return False


def _apipa_addressing_recovered(evidence: str) -> bool:
    latest_positive = -1
    for match in _APIPA_ADDRESSING_RECOVERED.finditer(evidence):
        prefix = evidence[max(0, match.start() - 60) : match.start()]
        if _NEGATED_EVIDENCE.search(prefix):
            continue
        if _NEGATED_NETWORK_RECOVERY.search(match.group()):
            continue
        latest_positive = match.end()
    latest_negative = max(
        (match.end() for match in _NEGATED_NETWORK_RECOVERY.finditer(evidence)),
        default=-1,
    )
    return latest_positive > latest_negative


def validate_assessment(
    case: DiagnosticCase,
    assessment: Assessment,
) -> Assessment:
    try:
        reject_sensitive_input(assessment.model_dump_json())
    except SensitiveDataError as exc:
        raise GuardrailViolation(
            "Model output contained a BitLocker recovery key and was withheld"
        ) from exc

    proposal = assessment.next_test
    intervention = assessment.intervention
    actions = [item for item in (proposal, intervention) if item is not None]
    action_text = "\n".join(_action_text(action) for action in actions)
    narrative_text = _assessment_narrative_text(assessment)
    visible_guidance = "\n".join((narrative_text, action_text))

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

        proposed_procedure = _procedure_fingerprint(proposal)
        completed_procedures = {
            _procedure_fingerprint(completed.proposal)
            for completed in case.completed_tests
        }
        if proposed_procedure and proposed_procedure in completed_procedures:
            _require_material_repeat_reason(
                proposal.title,
                proposal.repeat_reason,
            )

    if (
        intervention is not None
        and intervention.key in case.completed_intervention_keys
    ):
        _require_material_repeat_reason(
            intervention.title,
            intervention.repeat_reason,
            "intervention",
        )

    if (
        intervention is not None
        and intervention.key not in case.completed_intervention_keys
    ):
        proposed_procedure = _procedure_fingerprint(intervention)
        completed_procedures = {
            _procedure_fingerprint(completed.intervention)
            for completed in case.completed_interventions
        }
        if proposed_procedure and proposed_procedure in completed_procedures:
            _require_material_repeat_reason(
                intervention.title,
                intervention.repeat_reason,
                "intervention",
            )

    case_evidence = _case_safety_evidence(case)
    if (
        _APIPA_EVIDENCE.search(case_evidence)
        and _contains_nonnegated_pattern(
            visible_guidance,
            (_PREMATURE_APIPA_DNS_TEST,),
        )
        and not _apipa_addressing_recovered(case_evidence)
    ):
        raise GuardrailViolation(
            "DNS or public-internet testing was proposed before "
            "APIPA addressing was resolved"
        )

    bitlocker_action = proposal or intervention
    bitlocker_locked = _BITLOCKER_LOCKED.search(case_evidence) is not None
    bitlocker_context = bitlocker_locked or "bitlocker" in case_evidence.lower()

    if bitlocker_context:
        if _contains_nonnegated_pattern(
            visible_guidance, _PROHIBITED_BITLOCKER_CHANGES
        ):
            raise GuardrailViolation(
                "BitLocker action attempted to decrypt the original, remove "
                "protectors, or enable automatic unlocking"
            )

        if bitlocker_locked and _bitlocker_key_is_missing(case_evidence):
            if _contains_nonnegated_pattern(
                visible_guidance,
                (_TECHNICAL_BITLOCKER_ACTION, _BITLOCKER_DATA_ACCESS),
            ):
                raise GuardrailViolation(
                    "Technical access was proposed for a locked BitLocker volume "
                    "before an authorized recovery key was available"
                )

            credential_handling_text = re.sub(
                r"\b(?:bitlocker |recovery[- ]?)key\s+id(?:entifier)?\b",
                "recovery identifier",
                visible_guidance,
                flags=re.IGNORECASE,
            )
            if _contains_nonnegated_pattern(
                credential_handling_text,
                (_FORBIDDEN_CREDENTIAL_HANDLING,),
            ):
                raise GuardrailViolation(
                    "BitLocker key retrieval requested credentials or retained "
                    "sensitive recovery-key material"
                )

            retrieval_guidance = _contains_nonnegated_pattern(
                visible_guidance,
                (_BITLOCKER_KEY_RETRIEVAL,),
            )
            retrieval_policy_text = (
                action_text if bitlocker_action is not None else visible_guidance
            )
            if (bitlocker_action is not None or retrieval_guidance) and not (
                _BITLOCKER_KEY_RETRIEVAL.search(retrieval_policy_text)
                and _AUTHORIZED_KEY_RETRIEVER.search(retrieval_policy_text)
                and _PRIVATE_KEY_RETRIEVAL.search(retrieval_policy_text)
            ):
                raise GuardrailViolation(
                    "A locked BitLocker volume without a key permits only private, "
                    "authorized recovery-key retrieval guidance"
                )

        if _contains_nonnegated_pattern(
            visible_guidance,
            (_BITLOCKER_DATA_ACCESS,),
        ):
            if intervention is None:
                raise GuardrailViolation(
                    "BitLocker unlocking or customer-data access must be an intervention"
                )

            if not _contains_nonnegated_pattern(
                _action_text(intervention),
                (_BITLOCKER_DATA_ACCESS,),
            ):
                raise GuardrailViolation(
                    "BitLocker unlocking or customer-data access was not represented "
                    "in the controlled intervention"
                )

            if intervention.risk != RiskLevel.CAUTION:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access must be exactly CAUTION, never SAFE "
                    "or DESTRUCTIVE"
                )

            if not intervention.requires_confirmation:
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not require "
                    "technician confirmation"
                )

            prerequisites = "\n".join(intervention.prerequisites)
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

            if not (intervention.rollback or "").strip():
                raise GuardrailViolation(
                    "BitLocker unlocking or data access did not define rollback"
                )

    unstable_storage = (
        _latest_nonnegated_match_end(case_evidence, _UNSTABLE_STORAGE_EVIDENCE) >= 0
    )
    severe_irreplaceable_failure = bool(
        unstable_storage
        and _latest_nonnegated_match_end(
            case_evidence,
            _SEVERE_MECHANICAL_FAILURE,
        )
        >= 0
        and _IRREPLACEABLE_DATA.search(case_evidence)
    )
    sector_imaging = _contains_nonnegated_pattern(
        visible_guidance,
        (_SECTOR_IMAGING_ACTION,),
    )

    if severe_irreplaceable_failure:
        safe_escalation = (
            assessment.disposition == Disposition.ESCALATE
            and proposal is None
            and _contains_affirmative_pattern(
                visible_guidance,
                (_POWER_OFF_FAILED_MEDIA,),
            )
            and _contains_affirmative_pattern(
                visible_guidance,
                (_PROFESSIONAL_DATA_RECOVERY,),
            )
            and not _contains_nonnegated_pattern(
                visible_guidance,
                (_CONTINUE_FAILED_MEDIA_ACCESS,),
            )
        )
        safe_power_off_intervention = (
            intervention is None
            or (
                _contains_affirmative_pattern(
                    _action_text(intervention),
                    (_POWER_OFF_FAILED_MEDIA,),
                )
                and not _contains_nonnegated_pattern(
                    _action_text(intervention),
                    (
                        _CONTINUE_FAILED_MEDIA_ACCESS,
                        _SECTOR_IMAGING_ACTION,
                        _FILE_LEVEL_COPY_ACTIONS,
                        _DESTRUCTIVE_MEDIA_ACTION,
                    ),
                )
            )
        )
        if not (safe_escalation and safe_power_off_intervention):
            raise GuardrailViolation(
                "severe mechanical symptoms with irreplaceable data require power-off "
                "and professional-recovery escalation without further media access"
            )

    if unstable_storage and sector_imaging:
        if intervention is None:
            raise GuardrailViolation(
                "Controlled imaging of unstable media must be a caution intervention"
            )
        if not _contains_nonnegated_pattern(
            _action_text(intervention),
            (_SECTOR_IMAGING_ACTION,),
        ):
            raise GuardrailViolation(
                "Controlled imaging of unstable media was not represented in the "
                "controlled intervention"
            )
        if intervention.risk != RiskLevel.CAUTION:
            raise GuardrailViolation(
                "Controlled imaging of unstable media must be exactly CAUTION"
            )
        if not intervention.requires_confirmation:
            raise GuardrailViolation(
                "Controlled imaging requires explicit technician confirmation"
            )
        prerequisites = "\n".join(intervention.prerequisites)
        if not _IMAGING_RISK_ACCEPTANCE.search(prerequisites):
            raise GuardrailViolation(
                "Controlled imaging requires recorded customer risk acceptance"
            )
        if not _IMAGING_SOURCE_IDENTITY.search(prerequisites):
            raise GuardrailViolation(
                "Controlled imaging requires verified source identity"
            )
        if not _IMAGING_DESTINATION.search(prerequisites):
            raise GuardrailViolation(
                "Controlled imaging requires a verified healthy destination"
            )

    if (
        unstable_storage
        and _contains_nonnegated_pattern(
            visible_guidance,
            (_FILE_LEVEL_COPY_ACTIONS,),
        )
        and not (
            _has_completed_verified_recovery_artifact(case)
            and _contains_nonnegated_pattern(
                visible_guidance,
                (_COPY_FROM_RECOVERY_ARTIFACT,),
            )
            and not _contains_nonnegated_pattern(
                visible_guidance,
                (_COPY_FROM_ORIGINAL_MEDIA,),
            )
        )
    ):
        raise GuardrailViolation(
            "File-level copy was proposed for an unstable, disappearing, "
            "or inaccessible source drive"
        )

    if (
        unstable_storage
        and _contains_nonnegated_pattern(
            visible_guidance,
            (_DESTRUCTIVE_MEDIA_ACTION,),
        )
    ):
        raise GuardrailViolation(
            "Destructive repair or initialization was proposed for unstable media"
        )

    if _contains_nonnegated_pattern(visible_guidance, _UNSUPPORTED_POWER_TECHNIQUES):
        raise GuardrailViolation(
            "Unsupported external-power or power-bypass technique was proposed"
        )

    intrusive_hardware = _contains_nonnegated_pattern(
        visible_guidance,
        _INTRUSIVE_HARDWARE_STEPS,
    )
    if intrusive_hardware:
        if len(actions) != 1 or not _contains_nonnegated_pattern(
            _action_text(actions[0]),
            _INTRUSIVE_HARDWARE_STEPS,
        ):
            raise GuardrailViolation(
                "Intrusive hardware work was not represented in the controlled action"
            )

        action = actions[0]
        if action.risk == RiskLevel.SAFE:
            raise GuardrailViolation(
                "Intrusive hardware action was incorrectly marked safe"
            )

        if not action.requires_confirmation:
            raise GuardrailViolation(
                "Intrusive hardware action did not require technician confirmation"
            )

    for action in actions:
        if (
            action.risk == RiskLevel.DESTRUCTIVE
            and not action.requires_confirmation
        ):
            raise GuardrailViolation(
                "Destructive action did not require technician confirmation"
            )

    if intervention is not None and intervention.risk != RiskLevel.SAFE:
        if not intervention.requires_confirmation:
            raise GuardrailViolation(
                "Non-safe intervention did not require technician confirmation"
            )
        if not intervention.prerequisites:
            raise GuardrailViolation("Non-safe intervention did not state prerequisites")
        if not (intervention.rollback or "").strip():
            raise GuardrailViolation(
                "Non-safe intervention did not state rollback or explicitly state none"
            )

    return assessment
