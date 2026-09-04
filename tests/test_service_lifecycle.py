from datetime import UTC, datetime
from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.core.models import (
    Assessment,
    CaseStatus,
    Citation,
    DiagnosticCase,
    Hypothesis,
)
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.core.service import DiagnosticService, InvalidCaseAction
from fieldtech.knowledge.store import KnowledgeSnippet, KnowledgeStore


class FixedModel:
    name = "fixed"

    def __init__(self, assessment: Assessment) -> None:
        self.assessment = assessment

    def health(self) -> tuple[bool, str]:
        return True, "ready"

    def assess(self, case: DiagnosticCase, knowledge: list[object]) -> Assessment:
        return self.assessment.model_copy(deep=True)


def _assessment() -> Assessment:
    return Assessment(
        summary="Record the current state.",
        technician_message="Model-authored message.",
        hypotheses=[Hypothesis(id="model-hypothesis", label="Unscoped fault")],
        next_test=Proposal(
            id="model-test",
            key="record-current-state",
            title="Record current state",
            rationale="Preserve evidence.",
            instructions=["Record status without making a change."],
            cited_card_ids=["not-retrieved"],
        ),
        cited_card_ids=["not-retrieved"],
        citations=[
            Citation(
                card_id="not-retrieved",
                title="Invented citation",
                source_title="Invented source",
            )
        ],
        generated_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def _service(tmp_path: Path) -> DiagnosticService:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    return DiagnosticService(database, KnowledgeStore(database), FixedModel(_assessment()))


def test_application_replaces_model_owned_ids_time_and_citations(tmp_path: Path) -> None:
    case = _service(tmp_path).create_case("Laptop will not start")

    assert case.assessment is not None
    assert case.assessment.generated_at > datetime(2000, 1, 1, tzinfo=UTC)
    assert case.assessment.hypotheses[0].id != "model-hypothesis"
    assert case.assessment.next_test is not None
    assert case.assessment.next_test.id != "model-test"
    assert case.assessment.cited_card_ids == []
    assert case.assessment.next_test.cited_card_ids == []
    assert case.assessment.citations == []


def test_closed_case_has_no_action_and_rejects_further_turns(tmp_path: Path) -> None:
    service = _service(tmp_path)
    case = service.create_case("Laptop will not start")

    closed = service.close_case(case.id)

    assert closed.status == CaseStatus.CLOSED
    assert closed.assessment is not None
    assert closed.assessment.next_test is None
    assert closed.assessment.intervention is None
    with pytest.raises(InvalidCaseAction, match="case is closed"):
        service.refresh_assessment(closed)
    with pytest.raises(InvalidCaseAction, match="case is closed"):
        service.add_observation(closed.id, "A late observation")
    with pytest.raises(InvalidCaseAction, match="case is closed"):
        service.close_case(closed.id)


def test_citation_hydration_filters_unseen_top_level_and_nested_ids() -> None:
    assessment = _assessment()
    assert assessment.next_test is not None
    assessment.cited_card_ids = ["card-0", "card-4"]
    assessment.next_test.cited_card_ids = ["card-1", "card-4"]
    snippets = [
        KnowledgeSnippet(
            card_id=f"card-{index}",
            title=f"Card {index}",
            body="Synthetic body",
            source_title="Synthetic source",
            source_url=None,
            section=None,
            verified_at="2026-09-04",
            risk="safe",
            score=float(index),
        )
        for index in range(4)
    ]

    DiagnosticService._hydrate_citations(assessment, snippets)

    assert assessment.cited_card_ids == ["card-0", "card-1"]
    assert assessment.next_test.cited_card_ids == ["card-1"]
    assert [citation.card_id for citation in assessment.citations] == [
        "card-0",
        "card-1",
    ]
