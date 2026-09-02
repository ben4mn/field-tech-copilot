from __future__ import annotations

from fieldtech.core.database import Database
from fieldtech.core.guards import GuardrailViolation, validate_assessment
from fieldtech.core.models import (
    CaseStatus,
    Citation,
    CompletedTest,
    DeviceContext,
    DiagnosticCase,
    Disposition,
    Observation,
)
from fieldtech.knowledge.store import KnowledgeSnippet, KnowledgeStore
from fieldtech.providers.base import DiagnosticModel


class CaseNotFound(LookupError):
    pass


class InvalidCaseAction(ValueError):
    pass


class DiagnosticService:
    def __init__(
        self,
        database: Database,
        knowledge: KnowledgeStore,
        model: DiagnosticModel,
    ):
        self.database = database
        self.knowledge = knowledge
        self.model = model

    def create_case(
        self,
        complaint: str,
        title: str | None = None,
        device: DeviceContext | None = None,
    ) -> DiagnosticCase:
        clean_complaint = complaint.strip()
        case = DiagnosticCase(
            title=(title or clean_complaint[:80]).strip(),
            complaint=clean_complaint,
            device=device or DeviceContext(),
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
        observation = Observation(text=text.strip(), source=source)
        case.observations.append(observation)
        self.database.save_case(
            case,
            event_type="observation.recorded",
            event_payload=observation.model_dump(mode="json"),
        )
        return self.refresh_assessment(case)

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
        if proposal.requires_confirmation and not confirmed:
            raise InvalidCaseAction("This test requires explicit technician confirmation")
        completed = CompletedTest(proposal=proposal, result=result.strip(), outcome=outcome)
        case.completed_tests.append(completed)
        self.database.save_case(
            case,
            event_type="test.completed",
            event_payload=completed.model_dump(mode="json"),
        )
        return self.refresh_assessment(case)

    def close_case(self, case_id: str) -> DiagnosticCase:
        case = self.get_case(case_id)
        case.status = CaseStatus.CLOSED
        return self.database.save_case(case, event_type="case.closed")

    def delete_case(self, case_id: str) -> bool:
        if self.database.get_case(case_id) is None:
            raise CaseNotFound(case_id)
        return self.database.delete_case(case_id)

    def refresh_assessment(self, case: DiagnosticCase) -> DiagnosticCase:
        query = self._retrieval_query(case)
        snippets = self.knowledge.search(query)
        try:
            assessment = self.model.assess(case, snippets)
            self._hydrate_citations(assessment, snippets)
            validate_assessment(case, assessment)
            case.assessment = assessment
            case.last_error = None
            return self.database.save_case(
                case,
                event_type="assessment.accepted",
                event_payload={
                    "model": self.model.name,
                    "assessment": assessment.model_dump(mode="json"),
                },
            )
        except Exception as exc:
            if isinstance(exc, GuardrailViolation):
                self._withhold_stale_actions(case, str(exc))
            case.last_error = self._safe_error(exc)
            return self.database.save_case(
                case,
                event_type="assessment.rejected",
                event_payload={"model": self.model.name, "error": case.last_error},
            )

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
    def _withhold_stale_actions(case: DiagnosticCase, reason: str) -> None:
        if case.assessment is None:
            return

        uncertainty = f"Latest model action was withheld by a safety guard: {reason}"
        uncertainties = [*case.assessment.uncertainties]
        if uncertainty not in uncertainties:
            uncertainties.append(uncertainty)

        case.assessment = case.assessment.model_copy(
            update={
                "next_test": None,
                "intervention": None,
                "disposition": Disposition.ESCALATE,
                "technician_message": (
                    "The latest proposed action was withheld by a safety guard. "
                    "Do not perform the previous action; review the recorded evidence "
                    "and use a supported procedure or escalate."
                ),
                "uncertainties": uncertainties[-12:],
            }
        )

    @staticmethod
    def _require_active(case: DiagnosticCase) -> None:
        if case.status != CaseStatus.ACTIVE:
            raise InvalidCaseAction("The case is closed")

    @staticmethod
    def _retrieval_query(case: DiagnosticCase) -> str:
        parts = [case.complaint]
        parts.extend(item.text for item in case.observations[-3:])
        if case.assessment:
            parts.extend(item.label for item in case.assessment.hypotheses[:5])
        return " ".join(parts)

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
