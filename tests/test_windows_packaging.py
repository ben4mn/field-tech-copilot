from pathlib import Path

from fieldtech.desktop import KNOWLEDGE_PACK_VERSION

REPO_ROOT = Path(__file__).parents[1]
PREPARE_BUNDLE = REPO_ROOT / "packaging" / "windows" / "prepare-bundle.ps1"
JOSH_KNOWLEDGE = REPO_ROOT / "knowledge" / "josh-and-sons-fieldtech-knowledge-v1"


def test_windows_bundle_includes_josh_knowledge_pack() -> None:
    script = PREPARE_BUNDLE.read_text(encoding="utf-8")

    assert JOSH_KNOWLEDGE.is_dir()
    assert '"knowledge/josh-and-sons-fieldtech-knowledge-v1"' in script
    assert '(Join-Path $KnowledgePath "josh-and-sons-fieldtech-knowledge-v1")' in script
    assert f"knowledgePackVersion = {KNOWLEDGE_PACK_VERSION}" in script
