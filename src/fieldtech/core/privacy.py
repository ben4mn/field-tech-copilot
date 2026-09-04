from __future__ import annotations

import json
import re


class SensitiveDataError(ValueError):
    """User input contains a secret that must not enter case storage or prompts."""


_BITLOCKER_RECOVERY_KEY = re.compile(
    r"(?<!\d)(?:\d{6}(?:(?:[\s-]|\\[nrt])*)){7}\d{6}(?!\d)",
)
RECOVERY_KEY_REDACTION = "[REDACTED BITLOCKER RECOVERY KEY]"


def redact_sensitive_text(value: str) -> str:
    """Remove recognized recovery keys from defensive storage/read boundaries."""
    return _BITLOCKER_RECOVERY_KEY.sub(RECOVERY_KEY_REDACTION, value)


def redact_sensitive_value(value: object) -> object:
    """Recursively redact secrets without relying on JSON escape behavior."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {key: redact_sensitive_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_value(item) for item in value)
    return value


def redact_json_document(value: str) -> str:
    """Redact string values in a serialized JSON document, including old rows."""
    if not _BITLOCKER_RECOVERY_KEY.search(value):
        return value
    try:
        payload = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return redact_sensitive_text(value)
    return json.dumps(redact_sensitive_value(payload), ensure_ascii=False, default=str)


def reject_sensitive_input(*values: str | None) -> None:
    for value in values:
        if value and _BITLOCKER_RECOVERY_KEY.search(value):
            raise SensitiveDataError(
                "Do not enter or paste a BitLocker recovery key. "
                "Have the customer enter it privately in the trusted Windows prompt."
            )
