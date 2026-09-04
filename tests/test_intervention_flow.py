import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldtech.api.app import create_app
from fieldtech.config import Settings
from fieldtech.core.database import Database
from fieldtech.core.models import (
    Assessment,
    DiagnosticCase,
    Disposition,
    Intervention,
    RiskLevel,
)
from fieldtech.core.service import DiagnosticService, InvalidCaseAction
from fieldtech.knowledge.store import KnowledgeStore


class InterventionThenDoneModel:
    name = "intervention-then-done"

    def health(self) -> tuple[bool, str]:
        return True, "ready"

    def assess(self, case: DiagnosticCase, knowledge: list[object]) -> Assessment:
        if case.completed_interventions:
            return Assessment(
                summary="The intervention result is recorded.",
                technician_message="No further action is proposed.",
                disposition=Disposition.INSUFFICIENT_EVIDENCE,
            )
        return Assessment(
            summary="The evidence supports a controlled intervention.",
            technician_message="Perform the controlled intervention.",
            disposition=Disposition.READY_TO_INTERVENE,
            intervention=Intervention(
                title="Unlock the authorized BitLocker volume",
                rationale="The customer is authorized and the matching key ID is verified.",
                steps=["Have the customer enter the key privately in Windows."],
                verification=["Confirm only the authorized folders are accessible."],
                risk=RiskLevel.CAUTION,
                prerequisites=[
                    "Record customer authorization.",
                    "Match the recovery-key ID without recording the key.",
                ],
                rollback="Relock or safely disconnect the volume.",
                requires_confirmation=True,
            ),
        )


def build_service(tmp_path: Path) -> DiagnosticService:
    database = Database(tmp_path / "fieldtech.db")
    database.initialize()
    return DiagnosticService(
        database,
        KnowledgeStore(database),
        InterventionThenDoneModel(),
    )


def test_intervention_requires_confirmation_and_records_audit(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    case = service.create_case("Authorized BitLocker recovery")
    intervention = case.assessment.intervention
    assert intervention is not None

    with pytest.raises(InvalidCaseAction, match="explicit technician confirmation"):
        service.complete_intervention(
            case.id,
            intervention.id,
            "Customer folders were copied and verified.",
        )

    case = service.complete_intervention(
        case.id,
        intervention.id,
        "Customer folders were copied and verified.",
        outcome="pass",
        confirmed=True,
    )

    assert len(case.completed_interventions) == 1
    completed = case.completed_interventions[0]
    assert completed.intervention.id == intervention.id
    assert completed.technician_confirmed is True
    assert case.assessment is not None
    assert case.assessment.intervention is None

    with sqlite3.connect(tmp_path / "fieldtech.db") as connection:
        payload = connection.execute(
            "SELECT payload_json FROM case_events "
            "WHERE case_id = ? AND event_type = 'intervention.completed'",
            (case.id,),
        ).fetchone()
    assert payload is not None
    assert json.loads(payload[0])["technician_confirmed"] is True

    with pytest.raises(InvalidCaseAction, match="no longer"):
        service.complete_intervention(
            case.id,
            intervention.id,
            "Duplicate submission",
            confirmed=True,
        )


def test_intervention_result_rejects_recovery_key(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    case = service.create_case("Authorized BitLocker recovery")
    intervention = case.assessment.intervention
    assert intervention is not None

    with pytest.raises(InvalidCaseAction, match="Do not enter"):
        service.complete_intervention(
            case.id,
            intervention.id,
            "111111-222222-333333-444444-555555-666666-777777-888888",
            confirmed=True,
        )

    reloaded = service.get_case(case.id)
    assert reloaded.completed_interventions == []
    assert reloaded.assessment is not None
    assert reloaded.assessment.intervention is not None


def test_intervention_completion_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "fieldtech.api.app.build_provider",
        lambda settings: InterventionThenDoneModel(),
    )
    app = create_app(Settings(data_dir=tmp_path, model_provider="mock"))
    client = TestClient(app, base_url="http://localhost")
    page = client.get("/")
    token = re.search(r'name="fieldtech-token" content="([^"]+)"', page.text).group(1)
    headers = {"X-Fieldtech-Token": token}
    case = client.post(
        "/api/cases",
        headers=headers,
        json={"complaint": "Authorized BitLocker recovery"},
    ).json()
    intervention_id = case["assessment"]["intervention"]["id"]

    unconfirmed = client.post(
        f"/api/cases/{case['id']}/interventions/{intervention_id}/complete",
        headers=headers,
        json={"result": "Completed", "outcome": "pass", "confirmed": False},
    )
    assert unconfirmed.status_code == 409

    response = client.post(
        f"/api/cases/{case['id']}/interventions/{intervention_id}/complete",
        headers=headers,
        json={"result": "Completed", "outcome": "pass", "confirmed": True},
    )
    assert response.status_code == 200
    assert response.json()["completed_interventions"][0]["technician_confirmed"] is True


def test_intervention_ui_has_completion_and_privacy_controls() -> None:
    app_js = Path("src/fieldtech/api/static/app.js").read_text(encoding="utf-8")

    assert "intervention-result-form" in app_js
    assert "intervention-confirmed" in app_js
    assert "/interventions/${intervention.id}/complete" in app_js
    assert "Do not record passwords or recovery keys" in app_js


def test_legacy_intervention_without_id_gets_a_stable_identifier() -> None:
    payload = {
        "title": "Apply the approved repair",
        "rationale": "The fault is isolated.",
        "steps": ["Apply the approved repair."],
        "verification": ["Verify the original symptom."],
        "risk": "safe",
    }

    first = Intervention.model_validate(payload)
    second = Intervention.model_validate(payload)

    assert first.id == second.id
    assert first.id.startswith("intervention_legacy_")
