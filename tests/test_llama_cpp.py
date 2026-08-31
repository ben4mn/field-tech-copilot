import json

import httpx

from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.providers.llama_cpp import LlamaCppDiagnosticModel, llama_generation_schema
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
    schema = llama_generation_schema(Assessment.model_json_schema())

    assert isinstance(schema, dict)
    definitions = schema["$defs"]
    assert "title" in definitions["TestProposal"]["properties"]
    assert "title" in definitions["Intervention"]["properties"]
    assert "title" not in definitions["TestProposal"]
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
        assert payload["reasoning_effort"] == "none"
        assert payload["temperature"] == 0.7
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": expected.model_dump_json()}}
                ]
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
    assert len(requests) == 2
