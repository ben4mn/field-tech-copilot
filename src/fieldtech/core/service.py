from __future__ import annotations

import time

from fieldtech.core.database import Database
from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import (
    Assessment,
    CaseStatus,
    Citation,
    CompletedTest,
    DeviceContext,
    DiagnosticCase,
    Disposition,
    Observation,
)
from fieldtech.core.privacy import SensitiveDataError, reject_sensitive_input
from fieldtech.knowledge.store import KnowledgeSnippet, KnowledgeStore
from fieldtech.providers.base import DiagnosticModel


class CaseNotFound(LookupError):
    pass


class InvalidCaseAction(ValueError):
    pass


class DiagnosticService:
    DEFAULT_GUARDRAIL_RETRY_BUDGET_SECONDS = 30.0

    def __init__(
        self,
        database: Database,
        knowledge: KnowledgeStore,
        model: DiagnosticModel,
        guardrail_retry_budget_seconds: float = DEFAULT_GUARDRAIL_RETRY_BUDGET_SECONDS,
    ):
        self.database = database
        self.knowledge = knowledge
        self.model = model
        self.guardrail_retry_budget_seconds = max(
            0.0,
            float(guardrail_retry_budget_seconds),
        )

    def create_case(
        self,
        complaint: str,
        title: str | None = None,
        device: DeviceContext | None = None,
    ) -> DiagnosticCase:
        clean_complaint = complaint.strip()
        case_device = device or DeviceContext()
        self._reject_sensitive_input(
            clean_complaint,
            title,
            case_device.manufacturer,
            case_device.model,
            case_device.operating_system,
            case_device.notes,
        )
        case = DiagnosticCase(
            title=(title or clean_complaint[:80]).strip(),
            complaint=clean_complaint,
            device=case_device,
        )
        self.database.save_case(
            case,
            event_type="case.created",
            event_payload={"complaint": clean_complaint, "device": case.device.model_dump()},
        )
        return self.refresh_assessment(case)

    def list_cases(self) -> list[DiagnosticCase]:
        return self.database.list_cases()

    def get_case(self, case_id: str) -> DiagnosticCase:
        case = self.database.get_case(case_id)
        if case is None:
            raise CaseNotFound(case_id)
        return case

    def add_observation(
        self, case_id: str, text: str, source: str = "technician"
    ) -> DiagnosticCase:
        case = self.get_case(case_id)
        self._require_active(case)
        clean_text = text.strip()
        self._reject_sensitive_input(clean_text)
        expected_updated_at = case.updated_at.isoformat()
        observation = Observation(text=clean_text, source=source)
        self._invalidate_current_actions(
            case,
            uncertainty="New evidence invalidated the previous proposed action",
            technician_message=(
                "No technician action is proposed while the new observation is assessed."
            ),
        )
        case.observations.append(observation)
        saved = self.database.save_case_if_unmodified(
            case,
            expected_updated_at,
            event_type="observation.recorded",
            event_payload=observation.model_dump(mode="json"),
        )
        if saved is None:
            raise InvalidCaseAction(
                "The case changed before the observation could be recorded; retry it"
            )
        return self.refresh_assessment(saved)

    def complete_test(
        self,
        case_id: str,
        test_id: str,
        result: str,
        outcome: str = "other",
        confirmed: bool = False,
    ) -> DiagnosticCase:
        case = self.get_case(case_id)
        self._require_active(case)
        proposal = case.assessment.next_test if case.assessment else None
        if proposal is None or proposal.id != test_id:
            raise InvalidCaseAction("That test is no longer the current proposed test")
        if any(item.proposal.id == proposal.id for item in case.completed_tests):
            raise InvalidCaseAction("That proposed test has already been completed")
        if proposal.requires_confirmation and not confirmed:
            raise InvalidCaseAction("This test requires explicit technician confirmation")
        clean_result = result.strip()
        self._reject_sensitive_input(clean_result)
        expected_updated_at = case.updated_at.isoformat()
        completed = CompletedTest(proposal=proposal, result=clean_result, outcome=outcome)
        case.completed_tests.append(completed)
        self._invalidate_current_actions(
            case,
            uncertainty="The completed test invalidated the previous proposed action",
            technician_message=(
                "No technician action is proposed while the completed test is assessed."
            ),
        )
        saved = self.database.save_case_if_unmodified(
            case,
            expected_updated_at,
            event_type="test.completed",
            event_payload=completed.model_dump(mode="json"),
        )
        if saved is None:
            raise InvalidCaseAction("That test is no longer the current proposed test")
        return self.refresh_assessment(saved)

    def close_case(self, case_id: str) -> DiagnosticCase:
        case = self.get_case(case_id)
        case.status = CaseStatus.CLOSED
        return self.database.save_case(case, event_type="case.closed")

    def delete_case(self, case_id: str) -> bool:
        if self.database.get_case(case_id) is None:
            raise CaseNotFound(case_id)
        return self.database.delete_case(case_id)

    def refresh_assessment(self, case: DiagnosticCase) -> DiagnosticCase:
        expected_updated_at = case.updated_at.isoformat()
        if self._invalidate_current_actions(
            case,
            uncertainty="Refreshing the assessment invalidated the previous proposed action",
            technician_message=(
                "No technician action is proposed while the assessment is refreshed."
            ),
        ):
            saved = self.database.save_case_if_unmodified(
                case,
                expected_updated_at,
                event_type="assessment.invalidated",
                event_payload={"reason": "assessment refresh started"},
            )
            if saved is None:
                return self.get_case(case.id)
            case = saved
            expected_updated_at = case.updated_at.isoformat()

        started_at = time.monotonic()
        retry_deadline = started_at + self.guardrail_retry_budget_seconds
        guardrail_retry_count = 0

        try:
            query = self._retrieval_query(case)
            snippets = self.knowledge.search(query)
        except Exception as exc:
            return self._record_assessment_failure(
                case,
                expected_updated_at,
                exc,
                attempt=1,
                guardrail_retry_count=guardrail_retry_count,
            )

        for attempt in range(2):
            try:
                if attempt > 0 and time.monotonic() >= retry_deadline:
                    raise TimeoutError(
                        "guardrail repair exceeded the total retry time budget"
                    )
                assessment = self.model.assess(case, snippets)
                if attempt > 0 and time.monotonic() > retry_deadline:
                    raise TimeoutError(
                        "guardrail repair exceeded the total retry time budget"
                    )
                self._hydrate_citations(assessment, snippets)
                validate_assessment(case, assessment)
                self._synchronize_technician_message(assessment)
                case.assessment = assessment
                case.last_error = None
                saved = self.database.save_case_if_unmodified(
                    case,
                    expected_updated_at,
                    event_type="assessment.accepted",
                    event_payload={
                        "model": self.model.name,
                        "assessment": assessment.model_dump(mode="json"),
                        "attempt": attempt + 1,
                        "guardrail_retry_count": guardrail_retry_count,
                    },
                )
                return saved if saved is not None else self.get_case(case.id)
            except GuardrailViolation as exc:
                self._withhold_stale_actions(case, str(exc))
                case.last_error = self._safe_error(exc)
                retry_scheduled = attempt == 0 and time.monotonic() < retry_deadline
                next_retry_count = 1 if retry_scheduled else guardrail_retry_count
                saved = self.database.save_case_if_unmodified(
                    case,
                    expected_updated_at,
                    event_type="assessment.rejected",
                    event_payload={
                        "model": self.model.name,
                        "error": case.last_error,
                        "guardrail_reason": str(exc),
                        "attempt": attempt + 1,
                        "guardrail_retry_count": next_retry_count,
                        "retry_scheduled": retry_scheduled,
                        "elapsed_seconds": round(time.monotonic() - started_at, 3),
                    },
                )
                if saved is None:
                    return self.get_case(case.id)
                case = saved
                expected_updated_at = case.updated_at.isoformat()

                if retry_scheduled:
                    guardrail_retry_count = next_retry_count
                    continue

                return case
            except Exception as exc:
                return self._record_assessment_failure(
                    case,
                    expected_updated_at,
                    exc,
                    attempt=attempt + 1,
                    guardrail_retry_count=guardrail_retry_count,
                )

        raise RuntimeError("Assessment retry loop ended unexpectedly")

    def export_markdown(self, case_id: str) -> str:
        case = self.get_case(case_id)
        lines = [
            f"# {case.title}",
            "",
            f"- Case ID: `{case.id}`",
            f"- Status: {case.status.value}",
            f"- Created: {case.created_at.isoformat()}",
            f"- Updated: {case.updated_at.isoformat()}",
            "",
            "## Complaint",
            "",
            case.complaint,
            "",
            "## Device",
            "",
            f"- Manufacturer: {case.device.manufacturer or 'Not recorded'}",
            f"- Model: {case.device.model or 'Not recorded'}",
            f"- Operating system: {case.device.operating_system or 'Not recorded'}",
            f"- Notes: {case.device.notes or 'None'}",
            "",
            "## Observations",
            "",
        ]
        lines.extend(
            f"- {item.created_at.isoformat()} — {item.source}: {item.text}"
            for item in case.observations
        )
        if not case.observations:
            lines.append("- None recorded")

        lines.extend(["", "## Completed tests", ""])
        for item in case.completed_tests:
            lines.extend(
                [
                    f"### {item.proposal.title}",
                    "",
                    f"- Key: `{item.proposal.key}`",
                    f"- Outcome: {item.outcome}",
                    f"- Result: {item.result}",
                    f"- Completed: {item.completed_at.isoformat()}",
                    "",
                ]
            )
        if not case.completed_tests:
            lines.append("- None recorded")

        if case.assessment:
            lines.extend(["", "## Latest assessment", "", case.assessment.summary, ""])
            lines.append("### Hypotheses")
            lines.append("")
            for item in case.assessment.hypotheses:
                lines.append(
                    f"- **{item.label}** — {item.status.value}, confidence {item.confidence.value}"
                )
            if case.assessment.intervention:
                lines.extend(
                    [
                        "",
                        "### Proposed intervention",
                        "",
                        f"**{case.assessment.intervention.title}:** "
                        f"{case.assessment.intervention.rationale}",
                    ]
                )
            lines.extend(["", "### Sources", ""])
            lines.extend(
                f"- {item.title} — {item.source_title}"
                for item in case.assessment.citations
            )
            if not case.assessment.citations:
                lines.append("- No local sources cited")

        lines.extend(
            [
                "",
                "---",
                "Generated by Field Tech Copilot. Technician decision support only; "
                "verify all work.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _synchronize_technician_message(assessment: Assessment) -> None:
        if assessment.next_test is not None:
            action_title = assessment.next_test.title.strip().rstrip(".")
            action_steps = assessment.next_test.instructions
            message_label = "Next test"
            requires_confirmation = assessment.next_test.requires_confirmation
        elif assessment.intervention is not None:
            action_title = assessment.intervention.title.strip().rstrip(".")
            action_steps = assessment.intervention.steps
            message_label = "Proposed intervention"
            requires_confirmation = assessment.intervention.requires_confirmation
        elif assessment.disposition == Disposition.ESCALATE:
            assessment.technician_message = (
                "No technician action is proposed. "
                "The structured disposition is escalation."
            )
            return
        elif assessment.clarifying_questions:
            assessment.technician_message = (
                "No technician action is proposed until the listed "
                "clarifying questions are resolved."
            )
            return
        else:
            assessment.technician_message = (
                "No technician action is proposed from the current evidence."
            )
            return

        message_parts = [f"{message_label}: {action_title}."]

        if requires_confirmation:
            message_parts.append(
                "Technician confirmation is required before starting."
            )

        for step in action_steps:
            clean_step = step.strip()
            if not clean_step:
                continue

            candidate = " ".join([*message_parts, clean_step])
            if len(candidate) > 4_000:
                break

            message_parts.append(clean_step)

        assessment.technician_message = " ".join(message_parts)

    @staticmethod
    def _withhold_stale_actions(case: DiagnosticCase, reason: str) -> None:
        DiagnosticService._invalidate_current_actions(
            case,
            uncertainty=f"Latest model action was withheld by a safety guard: {reason}",
            technician_message=(
                "The latest proposed action was withheld by a safety guard. "
                "Do not perform the previous action; review the recorded evidence "
                "and use a supported procedure or escalate."
            ),
            disposition=Disposition.ESCALATE,
            force=True,
        )

    @staticmethod
    def _invalidate_current_actions(
        case: DiagnosticCase,
        *,
        uncertainty: str,
        technician_message: str,
        disposition: Disposition = Disposition.NEEDS_INFORMATION,
        force: bool = False,
    ) -> bool:
        if case.assessment is None:
            return False

        had_action = (
            case.assessment.next_test is not None
            or case.assessment.intervention is not None
        )
        if not had_action and not force:
            return False

        uncertainties = [*case.assessment.uncertainties]
        if uncertainty not in uncertainties:
            uncertainties.append(uncertainty)

        case.assessment = case.assessment.model_copy(
            update={
                "next_test": None,
                "intervention": None,
                "disposition": disposition,
                "technician_message": technician_message,
                "uncertainties": uncertainties[-12:],
            }
        )
        return had_action

    def _record_assessment_failure(
        self,
        case: DiagnosticCase,
        expected_updated_at: str,
        exc: Exception,
        *,
        attempt: int,
        guardrail_retry_count: int,
    ) -> DiagnosticCase:
        case.last_error = self._safe_error(exc)
        self._invalidate_current_actions(
            case,
            uncertainty=f"Assessment failed: {type(exc).__name__}",
            technician_message=(
                "The assessment failed. Do not perform a previously proposed action; "
                "review the recorded evidence and retry or escalate."
            ),
            disposition=Disposition.ESCALATE,
            force=True,
        )
        saved = self.database.save_case_if_unmodified(
            case,
            expected_updated_at,
            event_type="assessment.rejected",
            event_payload={
                "model": self.model.name,
                "error": case.last_error,
                "attempt": attempt,
                "guardrail_retry_count": guardrail_retry_count,
                "retry_scheduled": False,
            },
        )
        return saved if saved is not None else self.get_case(case.id)

    @staticmethod
    def _require_active(case: DiagnosticCase) -> None:
        if case.status != CaseStatus.ACTIVE:
            raise InvalidCaseAction("The case is closed")

    @staticmethod
    def _retrieval_query(case: DiagnosticCase) -> str:
        parts = [case.complaint]
        parts.extend(item.text for item in case.observations[-3:])
        parts.extend(item.result for item in case.completed_tests[-3:])
        if case.assessment:
            parts.extend(item.label for item in case.assessment.hypotheses[:5])
        return " ".join(parts)

    @staticmethod
    def _reject_sensitive_input(*values: str | None) -> None:
        try:
            reject_sensitive_input(*values)
        except SensitiveDataError as exc:
            raise InvalidCaseAction(str(exc)) from exc

    @staticmethod
    def _hydrate_citations(assessment: object, snippets: list[KnowledgeSnippet]) -> None:
        requested = set(assessment.cited_card_ids)
        if assessment.next_test:
            requested.update(assessment.next_test.cited_card_ids)
        if assessment.intervention:
            requested.update(assessment.intervention.cited_card_ids)
        allowed = {item.card_id: item for item in snippets}
        assessment.cited_card_ids = [card_id for card_id in requested if card_id in allowed]
        assessment.citations = [
            Citation(
                card_id=item.card_id,
                title=item.title,
                source_title=item.source_title,
                source_url=item.source_url,
                section=item.section,
                verified_at=item.verified_at,
            )
            for card_id in assessment.cited_card_ids
            if (item := allowed.get(card_id)) is not None
        ]

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, GuardrailViolation):
            return f"Guardrail rejected the model response: {exc}"
        return f"Local reasoning failed; recorded data is safe: {type(exc).__name__}: {exc}"
