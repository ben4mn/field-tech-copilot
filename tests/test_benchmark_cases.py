from pathlib import Path

import pytest

from fieldtech.config import Settings
from fieldtech.core.models import Assessment, DiagnosticCase, Disposition, Intervention
from fieldtech.core.models import TestProposal as Proposal
from scripts.benchmark_cases import (
    action_details,
    load_cases,
    quality_checks,
    run_benchmark,
    select_cases,
    settings_snapshot,
    validate_execution_policy,
    validate_identity,
    validate_run_request,
)


def test_field_suite_contains_only_synthetic_cases() -> None:
    cases = load_cases([Path("examples/gold-cases/qwen30b-field-suite.yaml")])

    assert len(cases) == 7
    assert {case["id"] for case in cases} == {
        "windows-apipa-dhcp-001",
        "windows-dns-only-001",
        "bitlocker-key-unavailable-001",
        "unstable-drive-irreplaceable-data-001",
        "windows-printer-queue-001",
        "blank-display-isolation-001",
        "windows-battery-shutdown-001",
    }


def test_non_synthetic_case_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "customer-case.yaml"
    path.write_text("id: real\ncomplaint: private\nsynthetic: false\n")

    with pytest.raises(ValueError, match="non-synthetic"):
        load_cases([path])


def test_quality_checks_score_action_and_forbidden_terms() -> None:
    case = DiagnosticCase(
        title="APIPA",
        complaint="169.254 address",
        assessment=Assessment(
            summary="Inspect DHCP state.",
            technician_message="Inspect DHCP state.",
            next_test=Proposal(
                key="inspect-ip",
                title="Inspect DHCP configuration",
                rationale="Collect addressing evidence.",
                instructions=["Run ipconfig /all."],
                cited_card_ids=["apipa-card"],
            ),
            cited_card_ids=["apipa-card"],
        ),
    )
    spec = {
        "expected_card_ids": ["apipa-card"],
        "acceptable_action_kinds": ["next_test"],
        "acceptable_terms_any": ["ipconfig /all"],
        "unacceptable_terms": ["public dns"],
    }

    assert action_details(case)[0] == "next_test"
    assert all(quality_checks(spec, case).values())


def test_quality_checks_accept_expected_stop_without_keyword_action() -> None:
    case = DiagnosticCase(
        title="Stop safely",
        complaint="Unstable original drive",
        assessment=Assessment(
            summary="Stop and escalate to professional recovery without another action.",
            technician_message="No action is proposed.",
            disposition=Disposition.ESCALATE,
        ),
    )
    spec = {
        "acceptable_action_kinds": ["none"],
        "acceptable_terms_any": ["professional recovery"],
    }

    checks = quality_checks(spec, case)

    assert checks["action_kind_allowed"] is True
    assert checks["acceptable_term_present"] is True
    assert checks["disposition_allowed"] is True


def test_quality_checks_do_not_count_negated_expected_behavior() -> None:
    case = DiagnosticCase(
        title="Unsafe continuation",
        complaint="Unstable original drive",
        assessment=Assessment(
            summary=(
                "Do not power off; do not stop; avoid professional recovery and "
                "never escalate."
            ),
            technician_message="Continue working on the original drive.",
            disposition=Disposition.ESCALATE,
        ),
    )

    checks = quality_checks(
        {
            "acceptable_action_kinds": ["none"],
            "acceptable_terms_any": ["power off", "stop", "professional recovery", "escalate"],
        },
        case,
    )

    assert checks["acceptable_term_present"] is False


def test_quality_checks_do_not_count_postfixed_negation() -> None:
    case = DiagnosticCase(
        title="Unsafe continuation",
        complaint="Unstable original drive",
        assessment=Assessment(
            summary="Power off is unnecessary; professional recovery is not required.",
            technician_message="Continue working on the original drive.",
            disposition=Disposition.ESCALATE,
        ),
    )

    checks = quality_checks(
        {"acceptable_terms_any": ["power off", "professional recovery"]},
        case,
    )

    assert checks["acceptable_term_present"] is False


def test_quality_checks_scan_summary_message_and_every_action_field() -> None:
    case = DiagnosticCase(
        title="Unsafe hidden text",
        complaint="Synthetic",
        assessment=Assessment(
            summary="Do not initialize the original disk.",
            technician_message="Escalate safely.",
            intervention=Intervention(
                key="controlled-recovery",
                title="Controlled recovery",
                rationale="Preserve evidence.",
                steps=["Power the device off."],
                verification=["Never use robocopy on the source."],
                prerequisites=["Customer authorization."],
                rollback="No rollback is available.",
                repeat_reason="The evidence materially changed.",
            ),
        ),
    )

    _, scanned_text, _ = action_details(case)
    checks = quality_checks(
        {
            "acceptable_action_kinds": ["intervention"],
            "acceptable_dispositions": ["active"],
            "unacceptable_terms": ["initialize", "robocopy", "no rollback"],
        },
        case,
    )

    assert "do not initialize" in scanned_text
    assert "never use robocopy" in scanned_text
    assert "no rollback" in scanned_text
    assert checks["unacceptable_terms_absent"] is False

    negated_only = quality_checks(
        {
            "acceptable_action_kinds": ["intervention"],
            "acceptable_dispositions": ["active"],
            "unacceptable_terms": ["initialize", "robocopy"],
        },
        case,
    )
    assert negated_only["unacceptable_terms_absent"] is True


def test_no_action_requires_an_allowed_disposition() -> None:
    case = DiagnosticCase(
        title="Incomplete no-action result",
        complaint="Synthetic",
        assessment=Assessment(
            summary="Wait.",
            technician_message="No action.",
            disposition=Disposition.ACTIVE,
        ),
    )

    assert (
        quality_checks({"acceptable_action_kinds": ["none"]}, case)["disposition_allowed"] is False
    )
    assert (
        quality_checks(
            {
                "acceptable_action_kinds": ["none"],
                "acceptable_dispositions": ["active"],
            },
            case,
        )["disposition_allowed"]
        is True
    )


def test_cold_run_requires_one_case_one_repetition_and_attestation() -> None:
    specs = [{"id": "one"}]

    with pytest.raises(ValueError, match="cold-start-method"):
        validate_run_request(
            specs=specs,
            repetitions=1,
            run_kind="cold",
            cold_start_method=None,
        )
    with pytest.raises(ValueError, match="exactly one selected case"):
        validate_run_request(
            specs=[*specs, {"id": "two"}],
            repetitions=1,
            run_kind="cold",
            cold_start_method="LM Studio model unloaded and reloaded",
        )
    with pytest.raises(ValueError, match="exactly one selected case"):
        validate_run_request(
            specs=specs,
            repetitions=2,
            run_kind="cold",
            cold_start_method="LM Studio model unloaded and reloaded",
        )


def test_case_id_selection_must_match_exactly_once() -> None:
    specs = [{"id": "one"}, {"id": "two"}]

    assert select_cases(specs, "two") == [{"id": "two"}]
    with pytest.raises(ValueError, match="found 0"):
        select_cases(specs, "missing")


def test_mock_and_dirty_strict_runs_require_explicit_truthful_inputs() -> None:
    with pytest.raises(ValueError, match="mock benchmark"):
        validate_execution_policy(provider="mock", allow_mock=False, strict=False, git_dirty=False)
    with pytest.raises(ValueError, match="dirty git worktree"):
        validate_execution_policy(
            provider="llama_cpp", allow_mock=False, strict=True, git_dirty=True
        )
    validate_execution_policy(provider="mock", allow_mock=True, strict=False, git_dirty=True)


def test_benchmark_identity_requires_exact_runtime_and_sha256() -> None:
    with pytest.raises(ValueError, match="runtime-version"):
        validate_identity("", "a" * 64)
    with pytest.raises(ValueError, match="64-character"):
        validate_identity("LM Studio 1.0.0", "not-a-digest")
    validate_identity("LM Studio 1.0.0", "a" * 64)


def test_settings_snapshot_removes_url_credentials_query_and_api_key() -> None:
    snapshot = settings_snapshot(
        Settings(
            model_provider="llama_cpp",
            model_base_url="https://user:secret@example.test:8443/v1?api_key=secret",
            model_api_key="also-secret",
            allow_remote=True,
        )
    )

    assert snapshot["base_url"] == "https://example.test:8443/v1"
    assert "secret" not in str(snapshot)
    assert "api_key" not in snapshot


def test_benchmark_record_contains_reproducibility_and_attempt_evidence(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture.yaml"
    fixture.write_text("id: evidence-001\nsynthetic: true\ncomplaint: Synthetic Wi-Fi failure\n")
    specs = load_cases([fixture])
    settings = Settings(model_provider="mock", model_name="fixture")

    records = run_benchmark(
        specs=specs,
        knowledge_root=Path("knowledge/josh-and-sons-fieldtech-knowledge-v1"),
        settings=settings,
        repetitions=1,
        run_kind="warm",
        runtime_version="test-runtime",
        model_sha256="a" * 64,
        allow_mock=True,
    )

    record = records[0]
    assert len(record["fixture_sha256"]) == 64
    assert len(record["knowledge_sha256"]) == 64
    assert record["code_commit"]
    assert isinstance(record["git_dirty"], bool)
    assert record["config"]["provider"] == "mock"
    assert "api_key" not in record["config"]
    assert record["provider_metrics"] == {"synthetic_provider": True}
    assert record["provider_metrics_history"] == [{"synthetic_provider": True}]
    assert (
        record["raw_accepted_assessment"]
        == record["assessment_attempt_events"][-1]["payload"]["assessment"]
    )
    assert record["assessment_attempt_events"][-1]["event_type"] == "assessment.accepted"
    assert record["guardrail_retry_count"] == 0
