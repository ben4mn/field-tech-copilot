import json

import httpx
import pytest
from pydantic import ValidationError

from fieldtech.core.models import DiagnosticCase
from fieldtech.providers.llama_cpp import (
    LlamaCppDiagnosticModel,
    assessment_generation_schema,
)
from fieldtech.providers.mock import MockDiagnosticModel


def _assert_required_properties_exist(value: object) -> None:
    if isinstance(value, dict):
        properties = value.get("properties")
        required = value.get("required")
        if isinstance(properties, dict) and isinstance(required, list):
            assert set(required) <= set(properties)
        for item in value.values():
            _assert_required_properties_exist(item)
    elif isinstance(value, list):
        for item in value:
            _assert_required_properties_exist(item)


def test_generation_schema_preserves_real_title_properties() -> None:
    schema = assessment_generation_schema()

    definitions = schema["$defs"]
    assert "title" in definitions["TestProposal"]["properties"]
    assert "title" in definitions["Intervention"]["properties"]
    assert "title" not in definitions["TestProposal"]
    assert "id" not in definitions["TestProposal"]["properties"]
    assert "id" not in definitions["Intervention"]["properties"]
    assert "id" not in definitions["Hypothesis"]["properties"]
    assert "Citation" not in definitions
    assert "citations" not in schema["properties"]
    assert "generated_at" not in schema["properties"]
    _assert_required_properties_exist(schema)


def test_llama_cpp_health_and_structured_assessment() -> None:
    case = DiagnosticCase(title="Synthetic case", complaint="Wi-Fi disconnects")
    expected = MockDiagnosticModel().assess(case, [])
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer session-secret"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "fieldtech-lite"}]})
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        generation_schema = payload["response_format"]["json_schema"]["schema"]
        assert "maxLength" not in json.dumps(generation_schema)
        assert generation_schema["required"] == ["summary", "technician_message"]
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert payload["reasoning_effort"] == "medium"
        assert payload["temperature"] == 0.7
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": expected.model_dump_json()}}],
                "usage": {"prompt_tokens": 321, "completion_tokens": 45},
                "timings": {"predicted_ms": 1250.5},
                "stats": {"time_to_first_token_seconds": 0.75},
            },
        )

    model = LlamaCppDiagnosticModel(
        base_url="http://127.0.0.1:12345/v1",
        model="fieldtech-lite",
        timeout_seconds=30,
        api_key="session-secret",
        transport=httpx.MockTransport(handler),
    )

    assert model.health() == (True, "Bundled local model 'fieldtech-lite' is ready")
    result = model.assess(case, [])
    assert result.summary == expected.summary
    metrics = {**model.last_metrics}
    assert metrics.pop("client_request_seconds") >= 0
    assert metrics == {
        "usage": {"prompt_tokens": 321, "completion_tokens": 45},
        "timings": {"predicted_ms": 1250.5},
        "stats": {"time_to_first_token_seconds": 0.75},
    }
    assert model.metrics_history == [model.last_metrics]
    assert len(requests) == 2


def test_llama_cpp_ignores_missing_or_unexpected_telemetry() -> None:
    assert LlamaCppDiagnosticModel._response_metrics({"usage": None}) == {}
    assert LlamaCppDiagnosticModel._response_metrics(
        {"usage": {"total_tokens": 4}, "stats": "not-an-object"}
    ) == {"usage": {"total_tokens": 4}}


def test_llama_cpp_rejects_dual_actions_instead_of_silently_choosing() -> None:
    case = DiagnosticCase(title="Synthetic case", complaint="Printer is offline")
    payload = {
        "summary": "Two conflicting actions were returned.",
        "technician_message": "Do both actions.",
        "next_test": {
            "key": "inspect-printer",
            "title": "Inspect printer status",
            "rationale": "Collect evidence.",
            "instructions": ["Open Windows printer settings."],
        },
        "intervention": {
            "title": "Restart print spooler",
            "rationale": "Attempt repair.",
            "steps": ["Restart the spooler service."],
            "verification": ["Print a test page."],
            "risk": "safe",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    model = LlamaCppDiagnosticModel(
        base_url="http://127.0.0.1:12345/v1",
        model="fieldtech-lite",
        timeout_seconds=30,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValidationError, match="return a next test or an intervention"):
        model.assess(case, [])
