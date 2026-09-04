import json
import sqlite3

import pytest

from fieldtech.core.database import Database
from fieldtech.core.models import DiagnosticCase
from fieldtech.core.privacy import (
    RECOVERY_KEY_REDACTION,
    SensitiveDataError,
    redact_sensitive_text,
    reject_sensitive_input,
)


@pytest.mark.parametrize(
    "value",
    [
        "111111-222222-333333-444444-555555-666666-777777-888888",
        "111111 222222 333333 444444 555555 666666 777777 888888",
        "111111222222333333444444555555666666777777888888",
    ],
)
def test_bitlocker_recovery_keys_are_rejected(value: str) -> None:
    with pytest.raises(SensitiveDataError, match="Do not enter"):
        reject_sensitive_input(value)


def test_ordinary_diagnostic_numbers_are_allowed() -> None:
    reject_sensitive_input("Windows 11, error 0x80070005, IP 169.254.10.4")


def test_recovery_key_is_redacted_at_database_boundaries(tmp_path) -> None:
    recovery_key = "111111-222222-333333-444444-555555-666666-777777-888888"
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    case = DiagnosticCase(
        title=f"Legacy case {recovery_key}",
        complaint=f"Key pasted: {recovery_key}",
    )

    database.save_case(
        case,
        event_type="legacy.imported",
        event_payload={"text": recovery_key},
    )

    with sqlite3.connect(database.path) as connection:
        title, state, event = connection.execute(
            "SELECT title, state_json, "
            "(SELECT payload_json FROM case_events WHERE case_id = cases.id) "
            "FROM cases WHERE id = ?",
            (case.id,),
        ).fetchone()
    assert recovery_key not in title
    assert recovery_key not in state
    assert recovery_key not in event
    assert RECOVERY_KEY_REDACTION in state
    assert RECOVERY_KEY_REDACTION in database.get_case(case.id).complaint


def test_redaction_handles_compact_and_spaced_keys() -> None:
    compact = "111111222222333333444444555555666666777777888888"
    spaced = "111111 222222 333333 444444 555555 666666 777777 888888"

    assert compact not in redact_sensitive_text(f"before {compact} after")
    assert spaced not in redact_sensitive_text(f"before {spaced} after")


@pytest.mark.parametrize("separator", ["\n", "\\n", "\t", "\\t"])
def test_redaction_handles_multiline_and_json_escaped_keys(separator: str) -> None:
    key = separator.join(str(index) * 6 for index in range(1, 9))

    with pytest.raises(SensitiveDataError, match="Do not enter"):
        reject_sensitive_input(key)
    assert key not in redact_sensitive_text(f"before {key} after")


def test_initialize_scrubs_legacy_case_and_event_rows(tmp_path) -> None:
    recovery_key = "111111-222222-333333-444444-555555-666666-777777-888888"
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    case = DiagnosticCase(title="Legacy", complaint="Safe placeholder")
    database.save_case(case, event_type="legacy.imported")

    legacy_state = case.model_dump(mode="json")
    legacy_state["complaint"] = f"Previously stored: {recovery_key}"
    with sqlite3.connect(database.path) as connection:
        connection.execute(
            "UPDATE cases SET title = ?, state_json = ? WHERE id = ?",
            (f"Legacy {recovery_key}", json.dumps(legacy_state), case.id),
        )
        connection.execute(
            "UPDATE case_events SET payload_json = ? WHERE case_id = ?",
            (json.dumps({"legacy": recovery_key}), case.id),
        )

    database.initialize()

    with sqlite3.connect(database.path) as connection:
        title, state = connection.execute(
            "SELECT title, state_json FROM cases WHERE id = ?",
            (case.id,),
        ).fetchone()
        events = connection.execute(
            "SELECT event_type, payload_json FROM case_events WHERE case_id = ?",
            (case.id,),
        ).fetchall()
    assert recovery_key not in title
    assert recovery_key not in state
    assert all(recovery_key not in payload for _, payload in events)
    assert any(event_type == "privacy.recovery_key_redacted" for event_type, _ in events)
    assert RECOVERY_KEY_REDACTION in database.get_case(case.id).complaint
