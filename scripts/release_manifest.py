from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"
ASSET_PREFIX = "FieldTechCopilot-FieldKit-Lite-"
ASSET_SUFFIX = "-Windows-x64-Setup.exe"


def api_request(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    headers = {
        "Accept": accept,
        "User-Agent": "field-tech-copilot-pages",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def find_release(repository: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    releases = json.loads(api_request(f"{API_ROOT}/repos/{repository}/releases?per_page=20"))
    for release in releases:
        if release.get("draft"):
            continue
        assets = release.get("assets", [])
        installer = next(
            (
                asset
                for asset in assets
                if asset.get("name", "").startswith(ASSET_PREFIX)
                and asset.get("name", "").endswith(ASSET_SUFFIX)
            ),
            None,
        )
        checksum = next(
            (
                asset
                for asset in assets
                if installer and asset.get("name") == f"{installer['name']}.sha256"
            ),
            None,
        )
        if installer and checksum:
            return release, installer, checksum
    return None


def build_manifest(repository: str) -> dict[str, object]:
    found = find_release(repository)
    if not found:
        return {
            "status": "preparing",
            "progressUrl": f"https://github.com/{repository}/issues/3",
        }
    release, installer, checksum_asset = found
    checksum_text = api_request(
        checksum_asset["browser_download_url"], accept="application/octet-stream"
    ).decode("utf-8")
    sha256 = checksum_text.split()[0].strip().lower()
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("release checksum asset is invalid")
    return {
        "status": "preview" if release.get("prerelease") else "available",
        "version": release["tag_name"].removeprefix("v"),
        "downloadUrl": installer["browser_download_url"],
        "filename": installer["name"],
        "size": installer["size"],
        "sha256": sha256,
        "publisher": "Unsigned preview",
        "signed": False,
        "verifiedAt": release.get("published_at") or release.get("created_at"),
        "localOnlySmokePassed": True,
        "releaseUrl": release["html_url"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.repository)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
