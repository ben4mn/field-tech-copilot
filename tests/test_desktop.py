import json
from pathlib import Path

import pytest

from fieldtech.core.database import Database
from fieldtech.desktop import (
    VC_RUNTIME_FILENAMES,
    bundle_paths,
    seed_knowledge,
    user_data_root,
    validate_bundle,
)

EXAMPLE_KNOWLEDGE = Path(__file__).parents[1] / "examples" / "knowledge"


def make_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "runtime").mkdir(parents=True)
    (root / "models").mkdir()
    (root / "knowledge").mkdir()
    (root / "runtime" / "llama-server.exe").write_bytes(b"runtime")
    for name in VC_RUNTIME_FILENAMES:
        (root / "runtime" / name).write_bytes(b"runtime")
    (root / "models" / "Qwen3-1.7B-Q8_0.gguf").write_bytes(b"model")
    source = EXAMPLE_KNOWLEDGE / "windows" / "connectivity-scope.md"
    destination = root / "knowledge" / "connectivity-scope.md"
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "bundle-manifest.json").write_text(
        json.dumps({"model": {"size": 5}, "knowledgePackVersion": 2}),
        encoding="utf-8",
    )
    return root


def test_bundle_validation_and_knowledge_seed_are_idempotent(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    paths = bundle_paths(root)

    assert validate_bundle(paths)["model"]["size"] == 5
    database = Database(tmp_path / "data" / "fieldtech.db")
    database.initialize()
    assert seed_knowledge(database, paths.knowledge) == 1
    assert seed_knowledge(database, paths.knowledge) == 0
    assert database.count_knowledge_cards() == 1


def test_bundle_validation_rejects_mismatched_knowledge_version(tmp_path: Path) -> None:
    root = make_bundle(tmp_path)
    manifest = root / "bundle-manifest.json"
    manifest.write_text(
        json.dumps({"model": {"size": 5}, "knowledgePackVersion": 1}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="knowledge-pack version"):
        validate_bundle(bundle_paths(root))


def test_windows_user_data_path_uses_local_app_data(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert user_data_root() == tmp_path / "FieldTechCopilot"
