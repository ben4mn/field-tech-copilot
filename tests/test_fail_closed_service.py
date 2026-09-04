import json
import sqlite3
from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.core.models import Assessment, CompletedTest, DiagnosticCase
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.core.service import DiagnosticService, InvalidCaseAction
from fieldtech.knowledge.store import KnowledgeSnippet, KnowledgeStore


def _safe_assessment() -> Assessment:
    return Assessment(
        summary="Record the current state before making a change.",
        technician_message="This model-authored text must be replaced.",
        next_test=Proposal(
            key="record-current-state",
            title="Record the current state",
            rationale="Preserve evidence before making a change.",
            instructions=["Record the current status without changing it."],
        ),
    )


def _unsafe_assessment() -> Assessment:
    return Assessment(
        summary="Try an unsupported power source.",
        technician_message="Connect external power.",
        next_test=Proposal(
            key="connect-external-battery",
            title="Connect an external battery",
            rationale="Look for activity.",
            instructions=["Connect a 12V external battery pack to the USB-C port."],
        ),
    )


class SequenceModel:
    name = "sequence"

    def __init__(self, *responses: Assessment | Exception) -> None:
        self.responses = list(responses)
        self.calls = 0

    def health(self) -> tuple[bool, str]:
        return True, "ready"

    def assess(
        self,
        case: DiagnosticCase,
        knowledge: list[KnowledgeSnippet],
    ) -> Assessment:
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response.model_copy(deep=True)


def _build_service(
    tmp_path: Path,
    model: SequenceModel,
    *,
    guardrail_retry_budget_seconds: float = 30.0,
) -> tuple[DiagnosticService, Database]:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    service = DiagnosticService(
        database,
        KnowledgeStore(database),
        model,
        guardrail_retry_budget_seconds=guardrail_retry_budget_seconds,
    )
    return service, database


def test_timeout_after_observation_does_not_restore_previous_action(
    tmp_path: Path,
) -> None:
    service, _ = _build_service(
        tmp_path,
        SequenceModel(_safe_assessment(), TimeoutError("provider timed out")),
    )
    case = service.create_case("Laptop will not start")

    updated = service.add_observation(case.id, "The charge LED stays dark")
    reloaded = service.get_case(case.id)

    assert [item.text for item in reloaded.observations] == [
        "The charge LED stays dark"
    ]
    assert updated.assessment is not None
    assert updated.assessment.next_test is None
    assert updated.assessment.intervention is None
    assert reloaded.assessment is not None
    assert reloaded.assessment.next_test is None
    assert "TimeoutError: provider timed out" in (reloaded.last_error or "")


def test_timeout_after_completion_is_fail_closed_and_duplicate_submit_is_rejected(
    tmp_path: Path,
) -> None:
    service, _ = _build_service(
        tmp_path,
        SequenceModel(_safe_assessment(), TimeoutError("provider timed out")),
    )
    case = service.create_case("Laptop will not start")
    assert case.assessment is not None
    assert case.assessment.next_test is not None
    proposal_id = case.assessment.next_test.id

    updated = service.complete_test(case.id, proposal_id, "No status changed")

    assert len(updated.completed_tests) == 1
    assert updated.assessment is not None
    assert updated.assessment.next_test is None
    assert updated.assessment.intervention is None
    with pytest.raises(InvalidCaseAction, match="no longer|already"):
        service.complete_test(case.id, proposal_id, "Submitted a second time")
    assert len(service.get_case(case.id).completed_tests) == 1


def test_guardrail_retry_is_audited_and_provider_failure_is_not_retried(
    tmp_path: Path,
) -> None:
    model = SequenceModel(
        _safe_assessment(),
        _unsafe_assessment(),
        RuntimeError("repair provider failed"),
    )
    service, database = _build_service(tmp_path, model)
    case = service.create_case("Laptop will not start")

    updated = service.refresh_assessment(case)

    assert model.calls == 3
    assert updated.assessment is not None
    assert updated.assessment.next_test is None
    assert updated.assessment.intervention is None
    assert "RuntimeError: repair provider failed" in (updated.last_error or "")

    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT payload_json
            FROM case_events
            WHERE case_id = ? AND event_type = 'assessment.rejected'
            ORDER BY id
            """,
            (case.id,),
        ).fetchall()

    payloads = [json.loads(row["payload_json"]) for row in rows]
    assert len(payloads) == 2
    assert "Unsupported external-power" in payloads[0]["guardrail_reason"]
    assert payloads[0]["attempt"] == 1
    assert payloads[0]["guardrail_retry_count"] == 1
    assert payloads[0]["retry_scheduled"] is True
    assert payloads[1]["attempt"] == 2
    assert payloads[1]["guardrail_retry_count"] == 1
    assert payloads[1]["retry_scheduled"] is False


def test_expired_guardrail_retry_budget_stops_after_first_rejection(
    tmp_path: Path,
) -> None:
    model = SequenceModel(_unsafe_assessment())
    service, database = _build_service(
        tmp_path,
        model,
        guardrail_retry_budget_seconds=0,
    )

    case = service.create_case("Laptop will not start")

    assert model.calls == 1
    assert case.assessment is None
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT payload_json
            FROM case_events
            WHERE case_id = ? AND event_type = 'assessment.rejected'
            """,
            (case.id,),
        ).fetchone()
    payload = json.loads(row["payload_json"])
    assert payload["guardrail_retry_count"] == 0
    assert payload["retry_scheduled"] is False


def test_retrieval_query_includes_completed_test_results() -> None:
    proposal = _safe_assessment().next_test
    assert proposal is not None
    case = DiagnosticCase(
        title="Drive recovery",
        complaint="Recover customer data",
        completed_tests=[
            CompletedTest(
                proposal=proposal,
                result="The drive disappears during sustained reads",
            )
        ],
    )

    query = DiagnosticService._retrieval_query(case)

    assert "The drive disappears during sustained reads" in query


def test_sensitive_test_result_is_rejected_before_case_storage(tmp_path: Path) -> None:
    service, _ = _build_service(tmp_path, SequenceModel(_safe_assessment()))
    case = service.create_case("BitLocker recovery is authorized")
    assert case.assessment is not None
    assert case.assessment.next_test is not None

    with pytest.raises(InvalidCaseAction, match="Do not enter"):
        service.complete_test(
            case.id,
            case.assessment.next_test.id,
            "111111-222222-333333-444444-555555-666666-777777-888888",
        )

    reloaded = service.get_case(case.id)
    assert reloaded.completed_tests == []
    assert reloaded.assessment is not None
    assert reloaded.assessment.next_test is not None


def test_provider_error_cannot_return_or_persist_a_recovery_key(tmp_path: Path) -> None:
    recovery_key = "111111-222222-333333-444444-555555-666666-777777-888888"
    service, database = _build_service(
        tmp_path,
        SequenceModel(RuntimeError(f"provider echoed {recovery_key}")),
    )

    case = service.create_case("BitLocker volume is locked")

    assert recovery_key not in (case.last_error or "")
    with sqlite3.connect(database.path) as connection:
        state = connection.execute(
            "SELECT state_json FROM cases WHERE id = ?",
            (case.id,),
        ).fetchone()[0]
        payloads = connection.execute(
            "SELECT payload_json FROM case_events WHERE case_id = ?",
            (case.id,),
        ).fetchall()
    assert recovery_key not in state
    assert all(recovery_key not in payload[0] for payload in payloads)
