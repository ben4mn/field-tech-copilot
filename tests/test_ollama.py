import json

import httpx

from fieldtech.core.models import DiagnosticCase
from fieldtech.providers.mock import MockDiagnosticModel
from fieldtech.providers.ollama import OllamaDiagnosticModel


def test_ollama_captures_runtime_durations_and_counts(monkeypatch) -> None:
    case = DiagnosticCase(title="Synthetic", complaint="Synthetic complaint")
    expected = MockDiagnosticModel().assess(case, [])

    def fake_post(*args, **kwargs) -> httpx.Response:
        assert kwargs["timeout"] == 4
        return httpx.Response(
            200,
            request=httpx.Request("POST", args[0]),
            json={
                "message": {"content": expected.model_dump_json()},
                "total_duration": 2_500_000_000,
                "load_duration": 500_000_000,
                "prompt_eval_duration": 750_000_000,
                "eval_duration": 1_250_000_000,
                "prompt_eval_count": 100,
                "eval_count": 20,
                "done_reason": "stop",
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    model = OllamaDiagnosticModel(
        base_url="http://127.0.0.1:11434",
        model="qwen",
        timeout_seconds=30,
    )

    result = model.assess(case, [], timeout_seconds=4)

    assert result.summary == expected.summary
    metrics = {**model.last_metrics}
    assert metrics.pop("client_request_seconds") >= 0
    assert metrics == {
        "durations_ns": {
            "total_duration": 2_500_000_000,
            "load_duration": 500_000_000,
            "prompt_eval_duration": 750_000_000,
            "eval_duration": 1_250_000_000,
        },
        "durations_seconds": {
            "total_seconds": 2.5,
            "load_seconds": 0.5,
            "prompt_eval_seconds": 0.75,
            "eval_seconds": 1.25,
        },
        "token_counts": {"prompt_eval_count": 100, "eval_count": 20},
        "done_reason": "stop",
    }
    assert model.metrics_history == [model.last_metrics]


def test_ollama_ignores_boolean_and_unknown_metrics() -> None:
    metrics = OllamaDiagnosticModel._response_metrics(
        {"total_duration": True, "eval_count": False, "unknown": json.dumps({})}
    )

    assert metrics == {}
