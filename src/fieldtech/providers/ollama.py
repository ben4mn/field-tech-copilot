from __future__ import annotations

import time

import httpx

from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.knowledge.store import KnowledgeSnippet
from fieldtech.providers.prompt import SYSTEM_PROMPT, build_context


class OllamaDiagnosticModel:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str = "medium",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.last_metrics: dict[str, object] = {}
        self.metrics_history: list[dict[str, object]] = []

    def health(self) -> tuple[bool, str]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            names = {item.get("name") for item in response.json().get("models", [])}
            if self.model not in names:
                return False, f"Ollama is reachable, but model '{self.model}' is not installed"
            return True, f"Ollama model '{self.model}' is ready"
        except (httpx.HTTPError, ValueError) as exc:
            return False, f"Ollama is unavailable: {exc}"

    def assess(
        self,
        case: DiagnosticCase,
        knowledge: list[KnowledgeSnippet],
        *,
        timeout_seconds: float | None = None,
    ) -> Assessment:
        self.last_metrics = {}
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": Assessment.model_json_schema(),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_context(
                        case=case,
                        knowledge=knowledge,
                        reasoning_effort=self.reasoning_effort,
                    ),
                },
            ],
        }
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=min(self.timeout_seconds, timeout_seconds)
                if timeout_seconds is not None
                else self.timeout_seconds,
            )
            response.raise_for_status()
        except Exception:
            self._record_metrics(
                {"client_request_seconds": round(time.perf_counter() - started, 6)}
            )
            raise
        response_payload = response.json()
        self._record_metrics(
            {
                "client_request_seconds": round(time.perf_counter() - started, 6),
                **self._response_metrics(response_payload),
            }
        )
        content = response_payload["message"]["content"]
        return Assessment.model_validate_json(content)

    def _record_metrics(self, metrics: dict[str, object]) -> None:
        self.last_metrics = metrics
        self.metrics_history.append(metrics)
        self.metrics_history = self.metrics_history[-8:]

    @staticmethod
    def _response_metrics(payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            return {}
        metrics: dict[str, object] = {}
        durations: dict[str, int | float] = {}
        duration_seconds: dict[str, float] = {}
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
        ):
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                durations[key] = value
                duration_seconds[key.removesuffix("_duration") + "_seconds"] = value / 1_000_000_000
        if durations:
            metrics["durations_ns"] = durations
            metrics["durations_seconds"] = duration_seconds
        counters = {
            key: payload[key]
            for key in ("prompt_eval_count", "eval_count")
            if isinstance(payload.get(key), int) and not isinstance(payload[key], bool)
        }
        if counters:
            metrics["token_counts"] = counters
        if isinstance(payload.get("done_reason"), str):
            metrics["done_reason"] = payload["done_reason"]
        return metrics
