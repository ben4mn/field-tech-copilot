import re
from pathlib import Path

from fastapi.testclient import TestClient

from fieldtech.api.app import create_app
from fieldtech.config import Settings


def test_local_api_requires_session_token_and_creates_case(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, model_provider="mock"))
    client = TestClient(app, base_url="http://localhost")

    assert client.get("/api/cases").status_code == 401
    page = client.get("/")
    token = re.search(r'name="fieldtech-token" content="([^"]+)"', page.text).group(1)
    headers = {"X-Fieldtech-Token": token}

    response = client.post(
        "/api/cases",
        headers=headers,
        json={"complaint": "Ethernet works but Wi-Fi disconnects"},
    )

    assert response.status_code == 201
    case = response.json()
    assert case["assessment"]["next_test"]["key"] == "scope-the-reported-failure"
    assert client.get("/api/cases", headers=headers).json()[0]["id"] == case["id"]

    health = client.get("/api/health", headers=headers).json()
    assert health["reasoning_mode"] == "demo_fixture"
    assert health["diagnostic_capable"] is False
    assert health["can_quit"] is False


def test_desktop_shutdown_route_is_only_enabled_with_callback(tmp_path: Path) -> None:
    calls: list[str] = []
    app = create_app(
        Settings(data_dir=tmp_path, model_provider="mock"),
        shutdown_callback=lambda: calls.append("stopped"),
    )
    client = TestClient(app, base_url="http://localhost")
    page = client.get("/")
    token = re.search(r'name="fieldtech-token" content="([^"]+)"', page.text).group(1)

    response = client.post(
        "/api/system/shutdown", headers={"X-Fieldtech-Token": token}
    )

    assert response.json() == {"status": "stopping"}
    assert calls == ["stopped"]
