from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore

KNOWLEDGE_ROOT = Path(__file__).parents[1] / "knowledge" / "josh-and-sons-fieldtech-knowledge-v1"


@pytest.mark.parametrize(
    ("query", "expected_ids"),
    [
        (
            "Windows 11 Wi-Fi has a 169.254 APIPA address and no internet.",
            ["joshandsons.windows.apipa-dhcp-scope.v1"],
        ),
        (
            "Windows 11 has valid DHCP and a default gateway. "
            "1.1.1.1 responds, but websites fail by name. "
            "Determine the safest DNS diagnostic.",
            ["joshandsons.windows.connectivity-dns-scope.v1"],
        ),
        (
            "The stable NVMe volume is locked by BitLocker and the recovery key is unavailable.",
            ["joshandsons.data.bitlocker-authorized-recovery.v1"],
        ),
        (
            "The customer hard drive clicks, disconnects, and reports SMART warnings.",
            ["joshandsons.data.unstable-drive-recovery.v1"],
        ),
        (
            "The Windows printer is offline and documents are stuck in its queue.",
            ["joshandsons.windows.printer-scope-and-queue.v1"],
        ),
        (
            "The Dell powers on but has a black screen and no visible image.",
            [
                "joshandsons.windows.blank-screen-isolation.v1",
                "joshandsons.dell.startup-symptom-classification.v1",
            ],
        ),
        (
            "The Windows laptop battery drains quickly and shuts down "
            "when unplugged. Run a read-only battery diagnostic.",
            ["joshandsons.windows.battery-report.v1"],
        ),
    ],
)
def test_clear_symptoms_route_to_relevant_cards(
    tmp_path: Path,
    query: str,
    expected_ids: list[str],
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()

    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(query, limit=6)

    assert [result.card_id for result in results] == expected_ids


def test_apipa_case_can_transition_to_dns_without_losing_dhcp_context(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The case began with a 169.254 APIPA address. It now has valid DHCP, "
        "a default gateway, and direct IP access to 1.1.1.1, but names fail.",
        limit=6,
    )

    assert [result.card_id for result in results] == [
        "joshandsons.windows.connectivity-dns-scope.v1",
        "joshandsons.windows.apipa-dhcp-scope.v1",
    ]


def test_unresolved_apipa_does_not_route_to_dns_from_negative_gateway_text(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The adapter still has APIPA, no default gateway, and DNS fails.",
        limit=6,
    )

    assert [result.card_id for result in results] == ["joshandsons.windows.apipa-dhcp-scope.v1"]


def test_bitlocker_on_unstable_media_routes_both_safety_cards(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The BitLocker hard drive clicks and disconnects during reads.",
        limit=6,
    )

    assert [result.card_id for result in results] == [
        "joshandsons.data.unstable-drive-recovery.v1",
        "joshandsons.data.bitlocker-authorized-recovery.v1",
    ]


def test_verified_image_transition_adds_copy_guidance_after_unstable_media(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The original disk was unstable and disconnected. A recovery image completed, "
        "its hash matched, and it was verified. Copy customer files from the image.",
        limit=6,
    )

    assert [result.card_id for result in results] == [
        "joshandsons.data.unstable-drive-recovery.v1",
        "joshandsons.windows.data-copy-verification.v1",
    ]


def test_non_storage_disconnect_does_not_trigger_unstable_drive_route(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The network printer disconnects and its queue is stuck.",
        limit=6,
    )

    assert [result.card_id for result in results] == [
        "joshandsons.windows.printer-scope-and-queue.v1"
    ]


def test_routed_results_never_exceed_requested_limit(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search(
        "The BitLocker hard drive clicks and disconnects during reads.",
        limit=1,
    )

    assert [result.card_id for result in results] == ["joshandsons.data.unstable-drive-recovery.v1"]
    assert store.search("APIPA", limit=0) == []
    assert store.search("APIPA", limit=-1) == []


def test_routed_card_does_not_depend_on_fts_candidates(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))
    with database.connect() as connection:
        connection.execute(
            "DELETE FROM knowledge_fts WHERE card_id = ?",
            ("joshandsons.windows.apipa-dhcp-scope.v1",),
        )

    results = store.search("Windows has a 169.254 APIPA address.", limit=6)

    assert [result.card_id for result in results] == ["joshandsons.windows.apipa-dhcp-scope.v1"]


def test_missing_route_card_falls_back_to_full_text_search(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    example_root = Path(__file__).parents[1] / "examples" / "knowledge"
    store.ingest(find_cards(example_root))

    results = store.search("APIPA Wi-Fi connectivity", limit=6)

    assert [result.card_id for result in results] == ["internal.windows.connectivity-scope.v1"]
