from pathlib import Path

import pytest

from fieldtech.config import Settings


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELDTECH_DATA_DIR", "/tmp/fieldtech-test")
    monkeypatch.setenv("FIELDTECH_MODEL_PROVIDER", "mock")

    settings = Settings.from_env()

    assert settings.data_dir == Path("/tmp/fieldtech-test")
    assert settings.model_provider == "mock"
    assert settings.model_name == "qwen3:8b"


def test_llama_cpp_provider_is_allowed() -> None:
    Settings(model_provider="llama_cpp").validate()


def test_non_loopback_bind_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        Settings(host="0.0.0.0").validate()
