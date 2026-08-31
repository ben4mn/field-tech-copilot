from __future__ import annotations

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

    def assess(self, case: DiagnosticCase, knowledge: list[KnowledgeSnippet]) -> Assessment:
        payload = {
            "model": self.model,
            "stream": False,
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
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return Assessment.model_validate_json(content)

