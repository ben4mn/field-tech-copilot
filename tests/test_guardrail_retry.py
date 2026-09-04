from pathlib import Path

from fieldtech.core.database import Database
from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.core.service import DiagnosticService
from fieldtech.knowledge.store import KnowledgeSnippet, KnowledgeStore
from fieldtech.providers.base import DiagnosticModel


class GuardrailThenSafeModel:
    name = "guardrail-then-safe"

    def __init__(self) -> None:
        self.calls = 0
        self.seen_last_errors: list[str | None] = []

    def health(self) -> tuple[bool, str]:
        return True, "ready"

    def assess(
        self,
        case: DiagnosticCase,
        knowledge: list[KnowledgeSnippet],
    ) -> Assessment:
        self.calls += 1
        self.seen_last_errors.append(case.last_error)

        if self.calls == 1:
            return Assessment(
                summary="Test DNS while APIPA remains unresolved.",
                technician_message="Run nslookup against a public resolver.",
                next_test=Proposal(
                    key="test-public-dns",
                    title="Test a public DNS resolver",
                    rationale="Check whether public name resolution works.",
                    instructions=["Run nslookup example.com using 1.1.1.1."],
                ),
            )

        return Assessment(
            summary="Inspect the unresolved APIPA configuration.",
            technician_message=(
                "Run ipconfig /all and record the adapter's DHCP state, "
                "IPv4 address, gateway, DHCP server, and lease information."
            ),
            next_test=Proposal(
                key="inspect-ip-configuration",
                title="Inspect the complete adapter configuration",
                rationale=(
                    "Confirm the DHCP lease state before testing higher "
                    "network layers."
                ),
                instructions=[
                    "Run ipconfig /all and record the adapter's DHCP state, "
                    "IPv4 address, gateway, DHCP server, and lease information."
                ],
            ),
        )


class FailingModel:
    name = "failing-model"

    def __init__(self) -> None:
        self.calls = 0

    def health(self) -> tuple[bool, str]:
        return False, "unavailable"

    def assess(
        self,
        case: DiagnosticCase,
        knowledge: list[KnowledgeSnippet],
    ) -> Assessment:
        self.calls += 1
        raise RuntimeError("backend unavailable")


class DeadlineAwareModel(GuardrailThenSafeModel):
    def __init__(self) -> None:
        super().__init__()
        self.seen_timeouts: list[float | None] = []

    def assess(
        self,
        case: DiagnosticCase,
        knowledge: list[KnowledgeSnippet],
        *,
        timeout_seconds: float | None = None,
    ) -> Assessment:
        self.seen_timeouts.append(timeout_seconds)
        return super().assess(case, knowledge)


def _build_service(
    tmp_path: Path,
    model: DiagnosticModel,
) -> DiagnosticService:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    knowledge = KnowledgeStore(database)
    return DiagnosticService(database, knowledge, model)


def test_guardrail_rejection_retries_once_with_feedback(
    tmp_path: Path,
) -> None:
    model = GuardrailThenSafeModel()
    service = _build_service(tmp_path, model)

    case = service.create_case(
        "Windows 11 has a 169.254 APIPA address and no internet."
    )

    assert model.calls == 2
    assert model.seen_last_errors[0] is None
    assert model.seen_last_errors[1] is not None
    assert "Guardrail rejected the model response" in model.seen_last_errors[1]
    assert "APIPA addressing was resolved" in model.seen_last_errors[1]

    assert case.last_error is None
    assert case.assessment is not None
    assert case.assessment.next_test is not None
    assert case.assessment.next_test.key == "inspect-ip-configuration"


def test_guardrail_retry_passes_only_the_remaining_deadline_to_capable_provider(
    tmp_path: Path,
) -> None:
    model = DeadlineAwareModel()
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    service = DiagnosticService(
        database,
        KnowledgeStore(database),
        model,
        guardrail_retry_budget_seconds=10,
    )

    service.create_case("Windows has a 169.254 APIPA address and no internet.")

    assert model.seen_timeouts[0] is None
    assert model.seen_timeouts[1] is not None
    assert 0 < model.seen_timeouts[1] <= 10


def test_non_guardrail_failure_is_not_retried(tmp_path: Path) -> None:
    model = FailingModel()
    service = _build_service(tmp_path, model)

    case = service.create_case("Printer disappeared")

    assert model.calls == 1
    assert case.assessment is None
    assert case.last_error is not None
    assert "RuntimeError: backend unavailable" in case.last_error
