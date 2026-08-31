import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "release_manifest.py"
SPEC = importlib.util.spec_from_file_location("release_manifest", MODULE_PATH)
assert SPEC and SPEC.loader
release_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manifest)


def test_release_manifest_finds_preview_asset(monkeypatch) -> None:
    releases = [
        {
            "draft": False,
            "prerelease": True,
            "tag_name": "v0.2.0-preview.1",
            "published_at": "2026-08-31T00:00:00Z",
            "html_url": "https://github.com/example/repo/releases/tag/v0.2.0-preview.1",
            "assets": [
                {
                    "name": "FieldTechCopilot-FieldKit-Lite-0.2.0-preview.1-Windows-x64-Setup.exe",
                    "size": 1_950_000_000,
                    "browser_download_url": "https://github.com/example/repo/releases/download/v0.2.0-preview.1/setup.exe",
                },
                {
                    "name": (
                        "FieldTechCopilot-FieldKit-Lite-0.2.0-preview.1-"
                        "Windows-x64-Setup.exe.sha256"
                    ),
                    "browser_download_url": (
                        "https://github.com/example/repo/releases/download/"
                        "v0.2.0-preview.1/setup.exe.sha256"
                    ),
                },
            ],
        }
    ]

    def fake_request(url: str, **kwargs) -> bytes:
        if url.endswith("releases?per_page=20"):
            return json.dumps(releases).encode()
        return (b"a" * 64) + b"  setup.exe\n"

    monkeypatch.setattr(release_manifest, "api_request", fake_request)

    manifest = release_manifest.build_manifest("example/repo")

    assert manifest["status"] == "preview"
    assert manifest["sha256"] == "a" * 64
    assert manifest["localOnlySmokePassed"] is True
