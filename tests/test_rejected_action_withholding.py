from pathlib import Path

from fieldtech.core.database import Database
from fieldtech.core.models import Assessment, DiagnosticCase, Disposition
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.core.service import DiagnosticService
from fieldtech.knowledge.store import KnowledgeStore


class UnsafeAfterFirstModel:
    name = "unsafe-after-first"

    def __init__(self) -> None:
        self.calls = 0

    def health(self) -> tuple[bool, str]:
        return True, "ready"

    def assess(self, case: DiagnosticCase, knowledge: list[object]) -> Assessment:
        self.calls += 1
        instruction = (
            "Observe the charger LED."
            if self.calls == 1
            else "Connect a 12V external battery pack to the USB-C port."
        )
        return Assessment(
            summary="No power",
            technician_message="Run the proposed test",
            next_test=Proposal(
                key=f"power-test-{self.calls}",
                title="Test laptop power",
                rationale="Look for activity",
                instructions=[instruction],
            ),
        )


def test_rejected_action_is_removed_from_case(tmp_path: Path) -> None:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    service = DiagnosticService(
        database,
        KnowledgeStore(database),
        UnsafeAfterFirstModel(),
    )

    case = service.create_case("Laptop has no power")
    assert case.assessment is not None
    assert case.assessment.next_test is not None

    case = service.refresh_assessment(case)

    assert case.last_error is not None
    assert "Unsupported external-power" in case.last_error
    assert case.assessment is not None
    assert case.assessment.next_test is None
    assert case.assessment.intervention is None
    assert case.assessment.disposition == Disposition.ESCALATE