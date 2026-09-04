from pathlib import Path

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore

KNOWLEDGE_ROOT = Path(__file__).parents[1] / "knowledge" / "josh-and-sons-fieldtech-knowledge-v1"


def test_apipa_card_ranks_first_for_169_254_dhcp_case(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.ingest(find_cards(KNOWLEDGE_ROOT))

    results = store.search("Windows 11 Wi-Fi 169.254 APIPA failed DHCP no internet")

    assert results
    assert results[0].card_id == "joshandsons.windows.apipa-dhcp-scope.v1"
