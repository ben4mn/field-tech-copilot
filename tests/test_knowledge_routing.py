from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore


KNOWLEDGE_ROOT = (
    Path(__file__).parents[1]
    / "knowledge"
    / "josh-and-sons-fieldtech-knowledge-v1"
)


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
            "The stable NVMe volume is locked by BitLocker and the "
            "recovery key is unavailable.",
            ["joshandsons.data.bitlocker-authorized-recovery.v1"],
        ),
        (
            "The customer hard drive clicks, disconnects, and reports "
            "SMART warnings.",
            ["joshandsons.data.unstable-drive-recovery.v1"],
        ),
        (
            "The Windows printer is offline and documents are stuck "
            "in its queue.",
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
