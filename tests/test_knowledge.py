from pathlib import Path

import pytest
from pydantic import ValidationError

from fieldtech.core.database import Database
from fieldtech.knowledge.cards import ProcedureCard, find_cards, parse_card
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


def test_card_id_is_bounded_for_prompt_and_persistence_safety() -> None:
    card = parse_card(EXAMPLE_ROOT / "windows" / "connectivity-scope.md")

    with pytest.raises(ValidationError, match="at most 200 characters"):
        ProcedureCard.model_validate({**card.model_dump(), "id": "a" * 201})
