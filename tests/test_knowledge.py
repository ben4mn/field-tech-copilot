from pathlib import Path

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import find_cards, parse_card
from fieldtech.knowledge.store import KnowledgeStore

EXAMPLE_ROOT = Path(__file__).parents[1] / "examples" / "knowledge"


def test_example_card_parses() -> None:
    card = parse_card(EXAMPLE_ROOT / "windows" / "connectivity-scope.md")

    assert card.id == "internal.windows.connectivity-scope.v1"
    assert card.risk.value == "safe"
    assert card.checksum


def test_card_can_be_indexed_and_retrieved(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    store = KnowledgeStore(database)

    assert store.ingest(find_cards(EXAMPLE_ROOT)) == 1
    results = store.search("Wi-Fi drops and DNS fails")

    assert results
    assert results[0].card_id == "internal.windows.connectivity-scope.v1"
    assert database.count_knowledge_cards() == 1

