from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = Path("data")
    model_provider: str = "mock"
    model_base_url: str = "http://127.0.0.1:11434"
    model_name: str = "qwen3:8b"
    model_api_key: str | None = None
    model_timeout_seconds: float = 120.0
    model_reasoning_effort: str = "medium"
    allow_remote: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        settings = cls(
            host=os.getenv("FIELDTECH_HOST", defaults.host),
            port=int(os.getenv("FIELDTECH_PORT", defaults.port)),
            data_dir=Path(os.getenv("FIELDTECH_DATA_DIR", str(defaults.data_dir))),
            model_provider=os.getenv("FIELDTECH_MODEL_PROVIDER", defaults.model_provider),
            model_base_url=os.getenv("FIELDTECH_MODEL_BASE_URL", defaults.model_base_url),
            model_name=os.getenv("FIELDTECH_MODEL_NAME", defaults.model_name),
            model_api_key=os.getenv("FIELDTECH_MODEL_API_KEY", defaults.model_api_key),
            model_timeout_seconds=float(
                os.getenv("FIELDTECH_MODEL_TIMEOUT_SECONDS", defaults.model_timeout_seconds)
            ),
            model_reasoning_effort=os.getenv(
                "FIELDTECH_MODEL_REASONING_EFFORT", defaults.model_reasoning_effort
            ),
            allow_remote=_env_bool("FIELDTECH_ALLOW_REMOTE"),
        )
        settings.validate()
        return settings

    @property
    def database_path(self) -> Path:
        return self.data_dir / "fieldtech.db"

    def with_overrides(self, **changes: object) -> Settings:
        provided = {key: value for key, value in changes.items() if value is not None}
        settings = replace(self, **provided)
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.model_provider not in {"llama_cpp", "mock", "ollama"}:
            raise ValueError(
                "FIELDTECH_MODEL_PROVIDER must be 'llama_cpp', 'mock', or 'ollama'"
            )
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        if not self.allow_remote and self.host not in loopback_hosts:
            raise ValueError(
                "Refusing a non-loopback host without FIELDTECH_ALLOW_REMOTE=true. "
                "The MVP is not hardened for network access."
            )
