from __future__ import annotations

import json
import re
from dataclasses import dataclass

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import ProcedureCard


@dataclass(frozen=True, slots=True)
class KnowledgeSnippet:
    card_id: str
    title: str
    body: str
    source_title: str
    source_url: str | None
    section: str | None
    verified_at: str
    risk: str
    score: float


def _routed_card_ids(query: str) -> tuple[str, ...]:
    text = query.casefold()

    if re.search(r"\b(?:169[.]254|apipa)\b", text):
        return ("joshandsons.windows.apipa-dhcp-scope.v1",)

    if "bitlocker" in text:
        return ("joshandsons.data.bitlocker-authorized-recovery.v1",)

    if (
        "battery" in text
        and any(
            marker in text
            for marker in (
                "drain",
                "unplugged",
                "battery report",
                "battery diagnostic",
            )
        )
    ):
        return ("joshandsons.windows.battery-report.v1",)

    if (
        "printer" in text
        and any(marker in text for marker in ("offline", "queue", "stuck"))
    ):
        return ("joshandsons.windows.printer-scope-and-queue.v1",)

    if any(
        marker in text
        for marker in (
            "blank screen",
            "black screen",
            "no visible image",
            "no display",
        )
    ):
        return (
            "joshandsons.windows.blank-screen-isolation.v1",
            "joshandsons.dell.startup-symptom-classification.v1",
        )

    if (
        any(marker in text for marker in ("hard drive", "disk", "drive"))
        and any(
            marker in text
            for marker in (
                "clicks",
                "clicking",
                "smart warning",
                "smart warnings",
                "disconnects",
                "disappears during reads",
            )
        )
    ):
        return ("joshandsons.data.unstable-drive-recovery.v1",)

    if (
        "dns" in text
        or "by name" in text
        or "name resolution" in text
    ):
        if (
            "valid dhcp" in text
            or "valid address" in text
            or "default gateway" in text
            or "1.1.1.1" in text
            or "direct-ip" in text
            or "direct ip" in text
        ):
            return ("joshandsons.windows.connectivity-dns-scope.v1",)

    return ()


class KnowledgeStore:
    def __init__(self, database: Database):
        self.database = database

    def ingest(self, cards: list[ProcedureCard]) -> int:
        with self.database.connect() as connection:
            for card in cards:
                metadata = card.model_dump(mode="json", exclude={"body"})
                connection.execute(
                    """
                    INSERT INTO knowledge_cards(
                        id, title, body, metadata_json, checksum, indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        body=excluded.body,
                        metadata_json=excluded.metadata_json,
                        checksum=excluded.checksum,
                        indexed_at=excluded.indexed_at
                    """,
                    (
                        card.id,
                        card.title,
                        card.body,
                        json.dumps(metadata),
                        card.checksum,
                    ),
                )
                connection.execute(
                    "DELETE FROM knowledge_fts WHERE card_id = ?",
                    (card.id,),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_fts(card_id, title, topics, body)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        card.id,
                        card.title,
                        " ".join(card.topics),
                        card.body,
                    ),
                )
        return len(cards)

    def search(self, query: str, limit: int = 6) -> list[KnowledgeSnippet]:
        tokens = [
            token.lower()
            for token in re.findall(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*",
                query,
            )
            if len(token) >= 2
        ]
        tokens = list(dict.fromkeys(tokens))[:20]

        if not tokens:
            return []

        fts_query = " OR ".join(
            f'"{token.replace(chr(34), "")}"'
            for token in tokens
        )

        routed_ids = _routed_card_ids(query)
        candidate_limit = max(limit, 64) if routed_ids else limit

        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    k.id,
                    k.title,
                    k.body,
                    k.metadata_json,
                    bm25(knowledge_fts) AS score
                FROM knowledge_fts
                JOIN knowledge_cards k
                    ON k.id = knowledge_fts.card_id
                WHERE knowledge_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts_query, candidate_limit),
            ).fetchall()

        if routed_ids:
            rows_by_id = {row["id"]: row for row in rows}
            routed_rows = [
                rows_by_id[card_id]
                for card_id in routed_ids
                if card_id in rows_by_id
            ]

            if routed_rows:
                rows = routed_rows[:limit]

        snippets: list[KnowledgeSnippet] = []

        for row in rows:
            metadata = json.loads(row["metadata_json"])
            snippets.append(
                KnowledgeSnippet(
                    card_id=row["id"],
                    title=row["title"],
                    body=row["body"][:2_500],
                    source_title=metadata["source_title"],
                    source_url=metadata.get("source_url"),
                    section=None,
                    verified_at=metadata["verified_at"],
                    risk=metadata["risk"],
                    score=float(row["score"]),
                )
            )

        return snippets
