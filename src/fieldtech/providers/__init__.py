"""Local model provider adapters."""

from fieldtech.config import Settings
from fieldtech.providers.base import DiagnosticModel
from fieldtech.providers.llama_cpp import LlamaCppDiagnosticModel
from fieldtech.providers.mock import MockDiagnosticModel
from fieldtech.providers.ollama import OllamaDiagnosticModel


def build_provider(settings: Settings) -> DiagnosticModel:
    if settings.model_provider == "llama_cpp":
        return LlamaCppDiagnosticModel(
            base_url=settings.model_base_url,
            model=settings.model_name,
            timeout_seconds=settings.model_timeout_seconds,
            reasoning_effort=settings.model_reasoning_effort,
            api_key=settings.model_api_key,
        )
    if settings.model_provider == "mock":
        return MockDiagnosticModel()
    if settings.model_provider == "ollama":
        return OllamaDiagnosticModel(
            base_url=settings.model_base_url,
            model=settings.model_name,
            timeout_seconds=settings.model_timeout_seconds,
            reasoning_effort=settings.model_reasoning_effort,
        )
    raise ValueError(f"Unsupported model provider: {settings.model_provider}")


__all__ = ["DiagnosticModel", "build_provider"]
