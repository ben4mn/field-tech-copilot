from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fieldtech.core.models import DiagnosticCase, utc_now

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases(updated_at DESC);

CREATE TABLE IF NOT EXISTS case_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_case_events_case_id ON case_events(case_id, id);

CREATE TABLE IF NOT EXISTS knowledge_cards (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    checksum TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    card_id UNINDEXED,
    title,
    topics,
    body,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def save_case(
        self,
        case: DiagnosticCase,
        event_type: str | None = None,
        event_payload: dict[str, object] | None = None,
    ) -> DiagnosticCase:
        case.updated_at = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO cases(id, title, status, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    status=excluded.status,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (
                    case.id,
                    case.title,
                    case.status.value,
                    case.model_dump_json(),
                    case.created_at.isoformat(),
                    case.updated_at.isoformat(),
                ),
            )
            if event_type:
                connection.execute(
                    """
                    INSERT INTO case_events(case_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        case.id,
                        event_type,
                        json.dumps(event_payload or {}, default=str),
                        utc_now().isoformat(),
                    ),
                )
        return case

    def save_case_if_unmodified(
        self,
        case: DiagnosticCase,
        expected_updated_at: str,
        event_type: str | None = None,
        event_payload: dict[str, object] | None = None,
    ) -> DiagnosticCase | None:
        """Persist a case only when nobody has changed it since it was loaded.

        The conditional update and its audit event share one transaction. This is
        used for completing proposed actions, where a normal read-then-write could
        otherwise accept two submissions for the same proposal.
        """
        previous_updated_at = case.updated_at
        case.updated_at = utc_now()

        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE cases SET
                    title = ?,
                    status = ?,
                    state_json = ?,
                    updated_at = ?
                WHERE id = ? AND updated_at = ?
                """,
                (
                    case.title,
                    case.status.value,
                    case.model_dump_json(),
                    case.updated_at.isoformat(),
                    case.id,
                    expected_updated_at,
                ),
            )
            if cursor.rowcount != 1:
                case.updated_at = previous_updated_at
                return None

            if event_type:
                connection.execute(
                    """
                    INSERT INTO case_events(case_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        case.id,
                        event_type,
                        json.dumps(event_payload or {}, default=str),
                        utc_now().isoformat(),
                    ),
                )

        return case

    def get_case(self, case_id: str) -> DiagnosticCase | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        return DiagnosticCase.model_validate_json(row["state_json"]) if row else None

    def list_cases(self) -> list[DiagnosticCase]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT state_json FROM cases ORDER BY updated_at DESC"
            ).fetchall()
        return [DiagnosticCase.model_validate_json(row["state_json"]) for row in rows]

    def delete_case(self, case_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        return cursor.rowcount > 0

    def count_knowledge_cards(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM knowledge_cards").fetchone()
        return int(row["count"])

    def get_meta(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_meta WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO app_meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )
