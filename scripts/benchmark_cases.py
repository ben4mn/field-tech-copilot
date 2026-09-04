from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml

from fieldtech.config import Settings
from fieldtech.core.database import Database
from fieldtech.core.models import DeviceContext, DiagnosticCase
from fieldtech.core.service import DiagnosticService
from fieldtech.knowledge.cards import find_cards
from fieldtech.knowledge.store import KnowledgeStore
from fieldtech.providers import build_provider

NO_ACTION_DISPOSITIONS = {
    "needs_information",
    "insufficient_evidence",
    "escalate",
}
_NEGATED_BENCHMARK_TERM = re.compile(
    r"\b(?:do not|don't|must not|should not|never|avoid)\b[^.;:\n]{0,50}$",
    re.IGNORECASE,
)
_NEGATED_BENCHMARK_TERM_SUFFIX = re.compile(
    r"^\s*(?:(?:is|was|would be|remains?|seems?)\s+)?"
    r"(?:not\s+(?:needed|required|necessary|recommended)|unnecessary|unsafe|optional)\b",
    re.IGNORECASE,
)


def load_cases(paths: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = payload.get("cases", []) if isinstance(payload, dict) else []
        if isinstance(payload, dict) and "complaint" in payload:
            entries = [payload]
        if not isinstance(entries, list):
            raise ValueError(f"{path} must contain a case or a cases list")
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("synthetic"):
                raise ValueError(f"{path} contains a non-synthetic or invalid case")
            entry = dict(entry)
            entry["_source"] = str(path)
            cases.append(entry)
    return cases


def knowledge_checksum(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_metadata() -> tuple[str, bool]:
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        check=True,
        capture_output=True,
        text=True,
    )
    return commit_result.stdout.strip(), bool(status_result.stdout.strip())


def settings_snapshot(settings: Settings) -> dict[str, object]:
    """Record reproducibility inputs without persisting the optional API key."""
    parsed_url = urlsplit(settings.model_base_url)
    hostname = parsed_url.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    safe_netloc = hostname
    if parsed_url.port is not None:
        safe_netloc = f"{safe_netloc}:{parsed_url.port}"
    safe_base_url = urlunsplit((parsed_url.scheme, safe_netloc, parsed_url.path, "", ""))
    return {
        "provider": settings.model_provider,
        "base_url": safe_base_url,
        "model": settings.model_name,
        "timeout_seconds": settings.model_timeout_seconds,
        "reasoning_effort": settings.model_reasoning_effort,
        "allow_remote": settings.allow_remote,
    }


def select_cases(specs: list[dict[str, Any]], case_id: str | None) -> list[dict[str, Any]]:
    if case_id is None:
        return specs
    selected = [spec for spec in specs if spec.get("id") == case_id]
    if len(selected) != 1:
        raise ValueError(f"--case-id must match exactly one synthetic case; found {len(selected)}")
    return selected


def validate_run_request(
    *,
    specs: list[dict[str, Any]],
    repetitions: int,
    run_kind: str,
    cold_start_method: str | None,
) -> None:
    if repetitions < 1:
        raise ValueError("--repetitions must be at least 1")
    if run_kind == "cold":
        if repetitions != 1 or len(specs) != 1:
            raise ValueError("a cold run must contain exactly one selected case and one repetition")
        if not cold_start_method or not cold_start_method.strip():
            raise ValueError(
                "a cold run requires --cold-start-method describing how the runtime "
                "and model were restarted or unloaded"
            )


def validate_execution_policy(
    *, provider: str, allow_mock: bool, strict: bool, git_dirty: bool
) -> None:
    if provider == "mock" and not allow_mock:
        raise ValueError(
            "Refusing a mock benchmark; configure a real provider or pass --allow-mock"
        )
    if strict and git_dirty:
        raise ValueError("Refusing a strict benchmark from a dirty git worktree")


def validate_identity(runtime_version: str, model_sha256: str) -> None:
    if not runtime_version.strip():
        raise ValueError("--runtime-version must record the exact local runtime version")
    if re.fullmatch(r"[0-9a-fA-F]{64}", model_sha256.strip()) is None:
        raise ValueError("--model-sha256 must be the model file's 64-character SHA-256")


def action_details(case: DiagnosticCase) -> tuple[str, str, str | None]:
    assessment = case.assessment
    if assessment is None:
        return "none", "", None
    text_parts = [assessment.summary, assessment.technician_message]
    if assessment.next_test is not None:
        action = assessment.next_test
        text_parts.extend(_text_values(action.model_dump(mode="json")))
        text = "\n".join(text_parts)
        return "next_test", text.casefold(), action.risk.value
    if assessment.intervention is not None:
        action = assessment.intervention
        text_parts.extend(_text_values(action.model_dump(mode="json")))
        text = "\n".join(text_parts)
        return "intervention", text.casefold(), action.risk.value
    return "none", "\n".join(text_parts).casefold(), None


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _text_values(item)]
    if isinstance(value, list):
        return [text for item in value for text in _text_values(item)]
    return []


def _contains_unnegated_term(text: str, term: str) -> bool:
    for match in re.finditer(re.escape(term), text, re.IGNORECASE):
        prefix = text[max(0, match.start() - 60) : match.start()]
        suffix = text[match.end() : match.end() + 60]
        if (
            not _NEGATED_BENCHMARK_TERM.search(prefix)
            and not _NEGATED_BENCHMARK_TERM_SUFFIX.search(suffix)
        ):
            return True
    return False


def quality_checks(spec: dict[str, Any], case: DiagnosticCase) -> dict[str, bool]:
    action_kind, action_text, _ = action_details(case)
    assessment = case.assessment
    actual_cards = set(assessment.cited_card_ids if assessment else [])
    expected_cards = set(spec.get("expected_card_ids", []))
    allowed_kinds = set(spec.get("acceptable_action_kinds", []))
    allowed_dispositions = set(spec.get("acceptable_dispositions", []))
    expected_terms = [str(value).casefold() for value in spec.get("acceptable_terms_any", [])]
    forbidden_terms = [str(value).casefold() for value in spec.get("unacceptable_terms", [])]
    disposition = assessment.disposition.value if assessment else None
    disposition_allowed = (
        disposition in allowed_dispositions
        if allowed_dispositions
        else action_kind != "none" or disposition in NO_ACTION_DISPOSITIONS
    )

    return {
        "assessment_accepted": assessment is not None and case.last_error is None,
        "expected_cards_cited": not expected_cards or expected_cards <= actual_cards,
        "action_kind_allowed": not allowed_kinds or action_kind in allowed_kinds,
        "disposition_allowed": disposition_allowed,
        "acceptable_term_present": (
            not expected_terms
            or any(_contains_unnegated_term(action_text, term) for term in expected_terms)
        ),
        "unacceptable_terms_absent": not any(
            _contains_unnegated_term(action_text, term) for term in forbidden_terms
        ),
    }


def assessment_attempt_events(database: Database, case_id: str) -> list[dict[str, Any]]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT event_type, payload_json, created_at
            FROM case_events
            WHERE case_id = ? AND event_type IN ('assessment.accepted', 'assessment.rejected')
            ORDER BY id
            """,
            (case_id,),
        ).fetchall()
    return [
        {
            "event_type": row["event_type"],
            "created_at": row["created_at"],
            "payload": json.loads(row["payload_json"]),
        }
        for row in rows
    ]


def run_benchmark(
    *,
    specs: list[dict[str, Any]],
    knowledge_root: Path,
    settings: Settings,
    repetitions: int,
    run_kind: str,
    runtime_version: str,
    model_sha256: str,
    cold_start_method: str | None = None,
    allow_mock: bool = False,
) -> list[dict[str, Any]]:
    validate_identity(runtime_version, model_sha256)
    validate_run_request(
        specs=specs,
        repetitions=repetitions,
        run_kind=run_kind,
        cold_start_method=cold_start_method,
    )
    validate_execution_policy(
        provider=settings.model_provider,
        allow_mock=allow_mock,
        strict=False,
        git_dirty=False,
    )
    provider = build_provider(settings)
    records: list[dict[str, Any]] = []
    code_commit, git_dirty = git_metadata()
    config = settings_snapshot(settings)
    knowledge_sha256 = knowledge_checksum(knowledge_root)
    fixture_checksums = {
        source: file_checksum(Path(source)) for source in {spec["_source"] for spec in specs}
    }

    with tempfile.TemporaryDirectory(prefix="fieldtech-benchmark-") as directory:
        for repetition in range(1, repetitions + 1):
            for spec in specs:
                database = Database(Path(directory) / f"{spec['id']}-{repetition}.sqlite")
                database.initialize()
                knowledge = KnowledgeStore(database)
                knowledge.ingest(find_cards(knowledge_root))
                service = DiagnosticService(database, knowledge, provider)
                device = DeviceContext.model_validate(spec.get("device", {}))
                if hasattr(provider, "last_metrics"):
                    provider.last_metrics = {}
                if hasattr(provider, "metrics_history"):
                    provider.metrics_history = []

                started = time.perf_counter()
                case = service.create_case(
                    complaint=str(spec["complaint"]),
                    title=str(spec.get("title") or spec["id"]),
                    device=device,
                )
                elapsed = time.perf_counter() - started
                kind, action_text, risk = action_details(case)
                checks = quality_checks(spec, case)
                attempt_events = assessment_attempt_events(database, case.id)
                accepted_events = [
                    event
                    for event in attempt_events
                    if event["event_type"] == "assessment.accepted"
                ]
                accepted_assessment = (
                    accepted_events[-1]["payload"].get("assessment") if accepted_events else None
                )
                retry_count = max(
                    (
                        int(event["payload"].get("guardrail_retry_count", 0))
                        for event in attempt_events
                    ),
                    default=0,
                )

                records.append(
                    {
                        "case_id": spec["id"],
                        "case_source": spec["_source"],
                        "repetition": repetition,
                        "run_kind": run_kind,
                        "cold_start_method": cold_start_method,
                        "elapsed_seconds": round(elapsed, 3),
                        "provider": settings.model_provider,
                        "model": settings.model_name,
                        "reasoning_effort": settings.model_reasoning_effort,
                        "runtime_version": runtime_version,
                        "model_sha256": model_sha256,
                        "config": config,
                        "code_commit": code_commit,
                        "git_dirty": git_dirty,
                        "fixture_sha256": fixture_checksums[spec["_source"]],
                        "knowledge_sha256": knowledge_sha256,
                        "provider_metrics": getattr(provider, "last_metrics", {}),
                        "provider_metrics_history": getattr(provider, "metrics_history", []),
                        "assessment_attempt_events": attempt_events,
                        "raw_accepted_assessment": accepted_assessment,
                        "guardrail_retry_count": retry_count,
                        "last_error": case.last_error,
                        "disposition": (
                            case.assessment.disposition.value if case.assessment else None
                        ),
                        "action_kind": kind,
                        "action_risk": risk,
                        "action_text": action_text,
                        "cited_card_ids": (
                            case.assessment.cited_card_ids if case.assessment else []
                        ),
                        "checks": checks,
                        "passed": all(checks.values()),
                    }
                )
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run synthetic Field Tech Copilot cases and write auditable JSONL results."
    )
    parser.add_argument("cases", type=Path, nargs="+")
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=Path("knowledge/josh-and-sons-fieldtech-knowledge-v1"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--run-kind", choices=("cold", "warm"), required=True)
    parser.add_argument(
        "--case-id",
        help="Select exactly one case by ID (required in practice for a cold run).",
    )
    parser.add_argument(
        "--cold-start-method",
        help=(
            "Operator attestation describing how the runtime/model was restarted or "
            "unloaded before this cold request."
        ),
    )
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="Explicitly permit the deterministic mock fixture instead of a real model.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        specs = select_cases(load_cases(args.cases), args.case_id)
        if args.run_kind == "cold" and args.case_id is None:
            raise ValueError("a cold run requires an explicit --case-id selection")
        validate_run_request(
            specs=specs,
            repetitions=args.repetitions,
            run_kind=args.run_kind,
            cold_start_method=args.cold_start_method,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    settings = Settings.from_env()
    try:
        validate_identity(args.runtime_version, args.model_sha256)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    _, git_dirty = git_metadata()
    try:
        validate_execution_policy(
            provider=settings.model_provider,
            allow_mock=args.allow_mock,
            strict=args.strict,
            git_dirty=git_dirty,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    records = run_benchmark(
        specs=specs,
        knowledge_root=args.knowledge,
        settings=settings,
        repetitions=args.repetitions,
        run_kind=args.run_kind,
        runtime_version=args.runtime_version,
        model_sha256=args.model_sha256,
        cold_start_method=args.cold_start_method,
        allow_mock=args.allow_mock,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "benchmark_metadata",
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(specs),
        "repetitions": args.repetitions,
        "run_kind": args.run_kind,
        "cold_start_method": args.cold_start_method,
        "config": settings_snapshot(settings),
        "code_commit": records[0]["code_commit"] if records else None,
        "git_dirty": records[0]["git_dirty"] if records else None,
    }
    lines = [json.dumps(header), *(json.dumps(record) for record in records)]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    failures = sum(not record["passed"] for record in records)
    print(f"Wrote {len(records)} results to {args.output}; {failures} failed checks")
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
