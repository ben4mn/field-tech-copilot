from __future__ import annotations

import json
import re
from dataclasses import dataclass

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import ProcedureCard

_VALID_ADDRESS = re.compile(
    r"\b(?:valid|normal|non[- ]?apipa)\b.{0,40}"
    r"\b(?:dhcp|ipv4|ip address|address|lease)\b|\bvalid dhcp\b",
    re.IGNORECASE,
)
_WORKING_NETWORK_PATH = re.compile(
    r"\b(?:working|reachable|responds?|successful|accessible|access)\b.{0,40}"
    r"\b(?:default gateway|gateway|direct[- ]ip|1[.]1[.]1[.]1)\b|"
    r"\b(?:default gateway|gateway|direct[- ]ip|1[.]1[.]1[.]1)\b.{0,40}"
    r"\b(?:working|reachable|responds?|successful|accessible|access)\b",
    re.IGNORECASE,
)
_NEGATED_SIGNAL_PREFIX = re.compile(
    r"\b(?:no|not|without|missing|invalid|isn't|wasn't|unreachable)\b[^.;:\n]{0,45}$",
    re.IGNORECASE,
)
_NEGATIVE_ADDRESS = re.compile(
    r"\b(?:no|not|without|missing|invalid)\b.{0,40}"
    r"\b(?:valid|normal|ipv4|ip address|dhcp|lease|gateway)\b|"
    r"\b(?:gateway|direct[- ]ip)\b.{0,40}"
    r"\b(?:not reachable|unreachable|failed|no response|timed out)\b",
    re.IGNORECASE,
)
_UNSTABLE_MEDIA = re.compile(
    r"\b(?:drive|disk|storage|volume|nvme|ssd|hdd|media)\b.{0,90}"
    r"\b(?:unstable|click(?:s|ing)?|smart warning|disconnect(?:s|ed|ing)?|"
    r"disappears?|spins? down|spins? up then stops?|read errors?)\b|"
    r"\b(?:unstable|click(?:s|ing)?|smart warning|disconnect(?:s|ed|ing)?|"
    r"disappears?|spins? down|spins? up then stops?|read errors?)\b.{0,90}"
    r"\b(?:drive|disk|storage|volume|nvme|ssd|hdd|media)\b|"
    r"\bnot initialized\b",
    re.IGNORECASE | re.DOTALL,
)


def _latest_positive_end(text: str, pattern: re.Pattern[str]) -> int:
    latest = -1
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 50) : match.start()]
        if not _NEGATED_SIGNAL_PREFIX.search(prefix):
            latest = match.end()
    return latest


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
    requires_elevation: bool = False
    prerequisites: tuple[str, ...] = ()
    rollback: str | None = None


def _routed_card_ids(query: str) -> tuple[str, ...]:
    text = query.casefold()
    routed: list[str] = []

    def add(*card_ids: str) -> None:
        for card_id in card_ids:
            if card_id not in routed:
                routed.append(card_id)

    has_apipa = bool(re.search(r"\b(?:169[.]254|apipa)\b", text))
    latest_negative_network = max(
        (match.end() for match in _NEGATIVE_ADDRESS.finditer(text)),
        default=-1,
    )
    latest_valid_address = _latest_positive_end(text, _VALID_ADDRESS)
    latest_working_path = _latest_positive_end(text, _WORKING_NETWORK_PATH)
    has_valid_network_path = (
        latest_valid_address > latest_negative_network
        and latest_working_path > latest_negative_network
    )
    has_dns_symptom = any(
        marker in text
        for marker in (
            "dns",
            "by name",
            "name resolution",
            "names fail",
            "websites fail by name",
        )
    )
    apipa_transitioned_to_dns = has_apipa and has_valid_network_path and has_dns_symptom

    # A later valid address/direct-IP observation can legitimately move an APIPA case
    # into DNS scoping. Put the current layer first while retaining the DHCP card as
    # historical context; unresolved APIPA remains DHCP-first.
    if apipa_transitioned_to_dns:
        add(
            "joshandsons.windows.connectivity-dns-scope.v1",
            "joshandsons.windows.apipa-dhcp-scope.v1",
        )
    else:
        if has_apipa:
            add("joshandsons.windows.apipa-dhcp-scope.v1")
        if has_dns_symptom and has_valid_network_path:
            add("joshandsons.windows.connectivity-dns-scope.v1")

    has_unstable_media = _UNSTABLE_MEDIA.search(text) is not None
    if has_unstable_media:
        add("joshandsons.data.unstable-drive-recovery.v1")

    if "bitlocker" in text:
        add("joshandsons.data.bitlocker-authorized-recovery.v1")

    # Ordinary file-copy guidance is safe only when the query does not also describe
    # the original medium as unstable. Imaging/recovery must win that conflict.
    has_copy_intent = any(
        marker in text
        for marker in (
            "copy customer",
            "copy files",
            "data copy",
            "data transfer",
            "file transfer",
            "robocopy",
            "verified duplicate",
            "recover files",
            "recover data",
        )
    )
    has_recovery_artifact = bool(
        re.search(r"\b(?:recovery |disk |drive |forensic )?image\b|\b(?:clone|duplicate)\b", text)
    )
    has_completed_artifact = bool(
        re.search(r"\b(?:completed|finished|successfully created)\b", text)
    )
    has_verified_artifact = bool(
        re.search(
            r"\b(?:verified|validated|checksum matched|hash matched|integrity confirmed)\b",
            text,
        )
    )
    verified_recovery_source = (
        has_recovery_artifact and has_completed_artifact and has_verified_artifact
    )
    if has_copy_intent and (not has_unstable_media or verified_recovery_source):
        add("joshandsons.windows.data-copy-verification.v1")

    if "battery" in text and any(
        marker in text
        for marker in (
            "drain",
            "unplugged",
            "battery report",
            "battery diagnostic",
        )
    ):
        add("joshandsons.windows.battery-report.v1")

    if "printer" in text and any(marker in text for marker in ("offline", "queue", "stuck")):
        add("joshandsons.windows.printer-scope-and-queue.v1")

    if any(
        marker in text
        for marker in (
            "blank screen",
            "black screen",
            "no visible image",
            "no display",
        )
    ):
        add(
            "joshandsons.windows.blank-screen-isolation.v1",
            "joshandsons.dell.startup-symptom-classification.v1",
        )

    return tuple(routed)


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
        if limit <= 0:
            return []

        tokens = [
            token.lower()
            for token in re.findall(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*",
                query,
            )
            if len(token) >= 2
        ]
        tokens = list(dict.fromkeys(tokens))[:20]

        routed_ids = _routed_card_ids(query)

        with self.database.connect() as connection:
            routed_rows = []
            if routed_ids:
                placeholders = ", ".join("?" for _ in routed_ids)
                direct_rows = connection.execute(
                    f"""
                    SELECT
                        id,
                        title,
                        body,
                        metadata_json,
                        -1000000.0 AS score
                    FROM knowledge_cards
                    WHERE id IN ({placeholders})
                    """,
                    routed_ids,
                ).fetchall()
                direct_rows_by_id = {row["id"]: row for row in direct_rows}
                routed_rows = [
                    direct_rows_by_id[card_id]
                    for card_id in routed_ids
                    if card_id in direct_rows_by_id
                ]

            fts_rows = []
            if tokens and not routed_rows:
                fts_query = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)
                fts_rows = connection.execute(
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
                    ORDER BY score, k.id
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()

        rows = []
        seen_ids: set[str] = set()
        for row in [*routed_rows, *fts_rows]:
            if row["id"] in seen_ids:
                continue
            seen_ids.add(row["id"])
            rows.append(row)
            if len(rows) == limit:
                break

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
                    requires_elevation=bool(metadata.get("requires_elevation", False)),
                    prerequisites=tuple(metadata.get("prerequisites", ())),
                    rollback=metadata.get("rollback"),
                )
            )

        return snippets
