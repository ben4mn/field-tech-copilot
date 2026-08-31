from __future__ import annotations

import httpx

from fieldtech.core.models import Assessment, DiagnosticCase
from fieldtech.knowledge.store import KnowledgeSnippet
from fieldtech.providers.prompt import SYSTEM_PROMPT, build_context

GENERATION_ONLY_SCHEMA_KEYS = {
    "default",
    "description",
    "examples",
    "format",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "pattern",
    "title",
}


def llama_generation_schema(value: object, *, _property_map: bool = False) -> object:
    """Remove grammar-expensive bounds; Pydantic validates the full schema afterward."""
    if isinstance(value, dict):
        return {
            key: llama_generation_schema(item, _property_map=key == "properties")
            for key, item in value.items()
            if _property_map or key not in GENERATION_ONLY_SCHEMA_KEYS
        }
    if isinstance(value, list):
        return [llama_generation_schema(item) for item in value]
    return value


def assessment_generation_schema() -> dict[str, object]:
    """Expose reasoning fields only; the application owns IDs, citations, and time."""
    schema = llama_generation_schema(Assessment.model_json_schema())
    if not isinstance(schema, dict):
        raise TypeError("Assessment JSON schema must be an object")
    properties = schema.get("properties")
    definitions = schema.get("$defs")
    if not isinstance(properties, dict) or not isinstance(definitions, dict):
        raise TypeError("Assessment JSON schema is missing properties or definitions")
    properties.pop("generated_at", None)
    properties.pop("citations", None)
    definitions.pop("Citation", None)
    for definition_name in ("Hypothesis", "TestProposal"):
        definition = definitions.get(definition_name)
        if isinstance(definition, dict) and isinstance(
            definition_properties := definition.get("properties"), dict
        ):
            definition_properties.pop("id", None)
    return schema


class LlamaCppDiagnosticModel:
    """Adapter for llama.cpp's loopback-only OpenAI-compatible server."""

    name = "llama_cpp"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str = "medium",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.api_key = api_key
        self.transport = transport

    def _client(self, timeout: float) -> httpx.Client:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        return httpx.Client(timeout=timeout, transport=self.transport, headers=headers)

    def health(self) -> tuple[bool, str]:
        try:
            with self._client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/models")
                response.raise_for_status()
            model_ids = {
                item.get("id") for item in response.json().get("data", []) if item.get("id")
            }
            if self.model not in model_ids:
                return False, f"Local runtime is reachable, but model '{self.model}' is not loaded"
            return True, f"Bundled local model '{self.model}' is ready"
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            return False, f"Bundled local model is unavailable: {exc}"

    def assess(self, case: DiagnosticCase, knowledge: list[KnowledgeSnippet]) -> Assessment:
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0,
            "presence_penalty": 1.5,
            "seed": 42,
            "max_tokens": 2_048,
            "reasoning_effort": "none",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "diagnostic_assessment",
                    "strict": True,
                    "schema": assessment_generation_schema(),
                },
            },
            "chat_template_kwargs": {"enable_thinking": False},
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
        with self._client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return Assessment.model_validate_json(content)
