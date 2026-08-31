from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def action_fingerprint(value: str) -> str:
    """Create a stable, human-auditable duplicate-test key."""
    return "-".join(re.findall(r"[a-z0-9]+", value.lower())).strip("-")


class RiskLevel(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    DESTRUCTIVE = "destructive"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HypothesisStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    ELIMINATED = "eliminated"
    CONFIRMED = "confirmed"


class Disposition(StrEnum):
    ACTIVE = "active"
    NEEDS_INFORMATION = "needs_information"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    READY_TO_INTERVENE = "ready_to_intervene"
    ESCALATE = "escalate"


class CaseStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class DeviceContext(BaseModel):
    manufacturer: str | None = None
    model: str | None = None
    operating_system: str | None = None
    notes: str | None = None


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("obs"))
    text: str = Field(min_length=1, max_length=8_000)
    source: Literal["customer", "technician", "system"] = "technician"
    created_at: datetime = Field(default_factory=utc_now)


class Hypothesis(BaseModel):
    id: str = Field(default_factory=lambda: new_id("hyp"))
    label: str = Field(min_length=1, max_length=500)
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    confidence: Confidence = Confidence.LOW
    evidence_for: list[str] = Field(default_factory=list, max_length=20)
    evidence_against: list[str] = Field(default_factory=list, max_length=20)


class TestProposal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("test"))
    key: str = Field(
        min_length=1,
        max_length=200,
        description="Stable action-target key, for example ping-default-gateway",
    )
    title: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=2_000)
    instructions: list[str] = Field(min_length=1, max_length=20)
    expected_results: list[str] = Field(default_factory=list, max_length=20)
    risk: RiskLevel = RiskLevel.SAFE
    prerequisites: list[str] = Field(default_factory=list, max_length=20)
    rollback: str | None = Field(default=None, max_length=2_000)
    requires_confirmation: bool = False
    repeat_reason: str | None = Field(default=None, max_length=1_000)
    cited_card_ids: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_risk_controls(self) -> TestProposal:
        self.key = action_fingerprint(self.key or self.title)
        if self.risk == RiskLevel.DESTRUCTIVE:
            if not self.requires_confirmation:
                raise ValueError("destructive tests must require confirmation")
            if not self.prerequisites:
                raise ValueError("destructive tests must state prerequisites")
            if not self.rollback:
                raise ValueError("destructive tests must state rollback or lack of rollback")
        return self


class CompletedTest(BaseModel):
    proposal: TestProposal
    result: str = Field(min_length=1, max_length=8_000)
    outcome: Literal["pass", "fail", "inconclusive", "blocked", "other"] = "other"
    completed_at: datetime = Field(default_factory=utc_now)


class Intervention(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=2_000)
    steps: list[str] = Field(min_length=1, max_length=30)
    verification: list[str] = Field(min_length=1, max_length=20)
    risk: RiskLevel = RiskLevel.CAUTION
    prerequisites: list[str] = Field(default_factory=list, max_length=20)
    rollback: str | None = Field(default=None, max_length=2_000)
    requires_confirmation: bool = False
    cited_card_ids: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_risk_controls(self) -> Intervention:
        if self.risk == RiskLevel.DESTRUCTIVE:
            if not self.requires_confirmation:
                raise ValueError("destructive interventions must require confirmation")
            if not self.prerequisites:
                raise ValueError("destructive interventions must state prerequisites")
            if not self.rollback:
                raise ValueError(
                    "destructive interventions must state rollback or explicitly state none"
                )
        return self


class Citation(BaseModel):
    card_id: str
    title: str
    source_title: str
    source_url: str | None = None
    section: str | None = None
    verified_at: str | None = None


class Assessment(BaseModel):
    summary: str = Field(min_length=1, max_length=4_000)
    technician_message: str = Field(min_length=1, max_length=4_000)
    disposition: Disposition = Disposition.ACTIVE
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=12)
    next_test: TestProposal | None = None
    intervention: Intervention | None = None
    clarifying_questions: list[str] = Field(default_factory=list, max_length=5)
    uncertainties: list[str] = Field(default_factory=list, max_length=12)
    cited_card_ids: list[str] = Field(default_factory=list, max_length=12)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    generated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_disposition(self) -> Assessment:
        if self.disposition == Disposition.READY_TO_INTERVENE and self.intervention is None:
            raise ValueError("ready_to_intervene requires an intervention")
        if self.next_test is not None and self.intervention is not None:
            raise ValueError("return a next test or an intervention, not both")
        return self


class DiagnosticCase(BaseModel):
    id: str = Field(default_factory=lambda: new_id("case"))
    title: str = Field(min_length=1, max_length=300)
    complaint: str = Field(min_length=1, max_length=8_000)
    device: DeviceContext = Field(default_factory=DeviceContext)
    status: CaseStatus = CaseStatus.ACTIVE
    observations: list[Observation] = Field(default_factory=list)
    completed_tests: list[CompletedTest] = Field(default_factory=list)
    assessment: Assessment | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def completed_test_keys(self) -> set[str]:
        return {item.proposal.key for item in self.completed_tests}

