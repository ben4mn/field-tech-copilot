from __future__ import annotations

from fieldtech.core.models import (
    Assessment,
    Confidence,
    DiagnosticCase,
    Disposition,
    Hypothesis,
    TestProposal,
)
from fieldtech.knowledge.store import KnowledgeSnippet


class MockDiagnosticModel:
    """Deterministic workflow fixture. It is not diagnostic intelligence."""

    name = "mock"

    def health(self) -> tuple[bool, str]:
        return True, "Mock provider is ready"

    def assess(self, case: DiagnosticCase, knowledge: list[KnowledgeSnippet]) -> Assessment:
        candidates = [
            TestProposal(
                key="scope-the-reported-failure",
                title="Scope the failure before changing configuration",
                rationale=(
                    "Separating device-only, application-only, and shared-network symptoms "
                    "will remove several broad hypothesis families at low risk."
                ),
                instructions=[
                    "Record the exact symptom and error text.",
                    "Check whether the problem affects one application or the whole device.",
                    "Check whether another device on the same network has the same symptom.",
                ],
                expected_results=[
                    "Only this device is affected",
                    "Multiple devices are affected",
                    "Only one application or destination is affected",
                ],
            ),
            TestProposal(
                key="compare-a-known-good-path",
                title="Compare a known-good connection or device",
                rationale=(
                    "A controlled comparison helps localize the fault to the device, link, "
                    "network, or destination without making a state change."
                ),
                instructions=[
                    "Keep the current configuration unchanged.",
                    "Test the same destination from a known-good device or connection.",
                    "Record which combinations work and fail.",
                ],
                expected_results=[
                    "The known-good path also fails",
                    "Only the affected device or connection fails",
                    "The comparison is inconclusive",
                ],
            ),
            TestProposal(
                key="capture-current-device-and-network-state",
                title="Capture current device and network state",
                rationale=(
                    "Recording state before a reset preserves evidence and exposes obvious "
                    "address, gateway, DNS, adapter, or driver anomalies."
                ),
                instructions=[
                    "Record the device model, OS build, and recent changes.",
                    "Record adapter/link state and relevant configuration.",
                    "Do not reset or remove anything yet.",
                ],
                expected_results=["A clear state anomaly is present", "State appears normal"],
            ),
        ]
        next_test = next(
            (item for item in candidates if item.key not in case.completed_test_keys), None
        )
        card_ids = [item.card_id for item in knowledge[:2]]
        if next_test:
            next_test.cited_card_ids = card_ids

        return Assessment(
            summary=(
                "The complaint is recorded, but the mock provider cannot diagnose it. "
                "It is demonstrating persistent state and safe test progression."
            ),
            technician_message=(
                "Start with the proposed low-risk scoping step and record the result. "
                "Switch to a local model for real diagnostic assistance."
            ),
            disposition=(
                Disposition.ACTIVE if next_test else Disposition.INSUFFICIENT_EVIDENCE
            ),
            hypotheses=[
                Hypothesis(
                    label="The fault domain is not yet localized",
                    confidence=Confidence.HIGH,
                    evidence_for=[case.complaint],
                    evidence_against=[],
                )
            ],
            next_test=next_test,
            uncertainties=["A real model has not assessed this case"],
            cited_card_ids=card_ids,
        )

