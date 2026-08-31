from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.core.service import DiagnosticService, InvalidCaseAction
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore
from fieldtech.providers.mock import MockDiagnosticModel


def build_service(tmp_path: Path) -> DiagnosticService:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    knowledge = KnowledgeStore(database)
    knowledge.ingest(
        find_cards(Path(__file__).parents[1] / "examples" / "knowledge")
    )
    return DiagnosticService(database, knowledge, MockDiagnosticModel())


def test_case_flow_persists_test_results(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    case = service.create_case("Wi-Fi drops after a Windows update")

    assert case.assessment is not None
    assert case.assessment.next_test is not None
    first_test = case.assessment.next_test
    case = service.complete_test(
        case.id,
        first_test.id,
        "Only this laptop drops; a phone remains connected",
        outcome="fail",
    )
    reloaded = service.get_case(case.id)

    assert len(reloaded.completed_tests) == 1
    assert reloaded.completed_tests[0].proposal.key == "scope-the-reported-failure"
    assert reloaded.assessment is not None
    assert reloaded.assessment.next_test is not None
    assert reloaded.assessment.next_test.key == "compare-a-known-good-path"


def test_stale_test_result_is_rejected(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    case = service.create_case("Printer disappeared")

    with pytest.raises(InvalidCaseAction, match="no longer"):
        service.complete_test(case.id, "test_stale", "It worked")


def test_case_exports_without_customer_identity(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    case = service.create_case("Printer disappeared", title="Printer case")

    exported = service.export_markdown(case.id)

    assert "# Printer case" in exported
    assert "## Complaint" in exported
    assert "Technician decision support only" in exported

