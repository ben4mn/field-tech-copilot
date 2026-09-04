import json
from dataclasses import replace

from fieldtech.core.models import (
    Assessment,
    CompletedIntervention,
    CompletedTest,
    DiagnosticCase,
    Hypothesis,
    Intervention,
    Observation,
)
from fieldtech.core.models import TestProposal as Proposal
from fieldtech.knowledge.store import KnowledgeSnippet
from fieldtech.providers.prompt import (
    MAX_CASE_CONTEXT_CHARS,
    MAX_KNOWLEDGE_CARDS,
    MAX_KNOWLEDGE_CONTENT_CHARS,
    MAX_KNOWLEDGE_CONTEXT_CHARS,
    build_context,
)


def _section(context: str, heading: str) -> object:
    value = context.split(f"{heading}\n", 1)[1].split("\n\n", 1)[0]
    return json.loads(value)


def _snippet(index: int) -> KnowledgeSnippet:
    return KnowledgeSnippet(
        card_id=f"test.card.{index}",
        title=f"Card {index}",
        body=f"card-{index}-content " + ("x" * 3_000),
        source_title="Test source",
        source_url=None,
        section=None,
        verified_at="2026-09-04",
        risk="safe",
        score=float(index),
        prerequisites=("Record current state before testing.",),
        rollback="No changes are made.",
    )


def test_context_is_compact_without_duplicating_case_history() -> None:
    completed_test = CompletedTest(
        proposal=Proposal(
            key="inspect-adapter",
            title="Inspect the adapter",
            rationale="Capture the complete adapter state.",
            instructions=["Run ipconfig /all."],
        ),
        result="completed-result-sentinel",
        outcome="pass",
    )
    completed_intervention = CompletedIntervention(
        intervention=Intervention(
            title="Apply the approved repair",
            rationale="The completed tests isolated the fault.",
            steps=["Apply only the approved change."],
            verification=["Verify the original symptom."],
            prerequisites=["Obtain technician approval."],
            rollback="Restore the recorded original state.",
            requires_confirmation=True,
        ),
        result="intervention-result-sentinel",
        outcome="pass",
        technician_confirmed=True,
    )
    case = DiagnosticCase(
        title="Compact context",
        complaint="The current complaint is authoritative.",
        observations=[Observation(text=f"observation-{index}-sentinel") for index in range(6)],
        completed_tests=[completed_test],
        completed_interventions=[completed_intervention],
        assessment=Assessment(
            summary="Current assessment",
            technician_message="No action yet.",
            hypotheses=[Hypothesis(label="hypothesis-sentinel")],
        ),
        last_error="repair-feedback-sentinel",
    )

    context = build_context(
        case,
        [_snippet(index) for index in range(6)],
        "medium",
    )

    case_state = _section(context, "CASE_STATE")
    assert "assessment" not in case_state
    assert "completed_tests" not in case_state
    assert "completed_interventions" not in case_state
    assert case_state["older_observation_count"] == 2
    assert [item["text"] for item in case_state["recent_observations"]] == [
        f"observation-{index}-sentinel" for index in range(2, 6)
    ]
    assert case_state["current_hypotheses"][0]["label"] == "hypothesis-sentinel"
    assert "observation-0-sentinel" not in context
    assert context.count("observation-5-sentinel") == 1
    assert context.count("completed-result-sentinel") == 1
    assert context.count("intervention-result-sentinel") == 1
    assert context.count("hypothesis-sentinel") == 1
    assert context.count("repair-feedback-sentinel") == 1

    tests = _section(context, "COMPLETED_TESTS_DO_NOT_REPEAT")
    assert tests[0]["key"] == "inspect-adapter"
    assert tests[0]["procedure"] == "Run ipconfig /all."
    interventions = _section(context, "COMPLETED_INTERVENTIONS_DO_NOT_REPEAT")
    assert interventions[0]["id"] == completed_intervention.intervention.id
    assert interventions[0]["technician_confirmed"] is True
    assert _section(context, "MODEL_REPAIR_FEEDBACK") == "repair-feedback-sentinel"


def test_context_enforces_knowledge_card_and_character_budgets() -> None:
    case = DiagnosticCase(title="Budget test", complaint="Test the prompt budget.")

    context = build_context(
        case,
        [_snippet(index) for index in range(MAX_KNOWLEDGE_CARDS + 2)],
        "low",
    )

    knowledge_heading = next(
        line for line in context.splitlines() if line.startswith("KNOWLEDGE (")
    )
    knowledge = _section(context, knowledge_heading)
    allowed_ids = _section(context, "ALLOWED_CITATION_IDS")

    assert len(knowledge) == MAX_KNOWLEDGE_CARDS
    assert len(json.dumps(knowledge, ensure_ascii=False, separators=(",", ":"))) <= (
        MAX_KNOWLEDGE_CONTEXT_CHARS
    )
    assert sum(len(item["content"]) for item in knowledge) <= (MAX_KNOWLEDGE_CONTENT_CHARS)
    assert allowed_ids == [item["card_id"] for item in knowledge]
    assert f"test.card.{MAX_KNOWLEDGE_CARDS}" not in context


def test_context_redacts_recovery_keys_from_legacy_case_state() -> None:
    recovery_key = "111111-222222-333333-444444-555555-666666-777777-888888"
    case = DiagnosticCase(
        title="Legacy BitLocker case",
        complaint=f"A historical note contained {recovery_key}",
    )

    context = build_context(case, [], "low")

    assert recovery_key not in context
    assert "[REDACTED BITLOCKER RECOVERY KEY]" in context


def test_entire_context_is_bounded_and_preserves_latest_and_card_tail() -> None:
    proposal = Proposal(
        key="bounded-history-test",
        title="Inspect bounded history",
        rationale="Exercise prompt compaction.",
        instructions=["Record the current state without changing it."],
    )
    case = DiagnosticCase(
        title="Large synthetic case",
        complaint="complaint-head " + ("c" * 7_900) + " complaint-tail",
        observations=[
            Observation(text=f"observation-{index} " + ("o" * 1_000))
            for index in range(30)
        ],
        completed_tests=[
            CompletedTest(
                proposal=proposal.model_copy(update={"id": f"test-{index}"}),
                result=f"result-{index} " + ("r" * 1_000),
                outcome="other",
            )
            for index in range(20)
        ],
        completed_interventions=[
            CompletedIntervention(
                intervention=Intervention(
                    key=f"intervention-{index}",
                    title=f"Synthetic intervention {index}",
                    rationale="Exercise bounded history.",
                    steps=["Apply the synthetic step."],
                    verification=["Verify the synthetic result."],
                    risk="safe",
                ),
                result=f"intervention-result-{index} " + ("i" * 1_000),
                outcome="other",
            )
            for index in range(20)
        ],
    )
    snippet = replace(
        _snippet(0),
        body="card-head " + ("k" * 5_000) + " card-tail-safety",
    )

    context = build_context(case, [snippet], "low")

    assert len(context) <= MAX_CASE_CONTEXT_CHARS
    assert "observation-29" in context
    assert "result-19" in context
    assert "intervention-result-19" in context
    assert "card-head" in context
    assert "card-tail-safety" in context
