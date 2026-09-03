from pathlib import Path


PROMPT_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "fieldtech"
    / "providers"
    / "prompt.py"
)


def test_bitlocker_access_prompt_requires_caution_and_confirmation() -> None:
    prompt_source = PROMPT_PATH.read_text(encoding="utf-8")

    assert 'to "caution"' in prompt_source
    assert "set requires_confirmation to true" in prompt_source
    assert 'Do not call unlocking "decryption"' in prompt_source
    assert "the recovery-key ID as prerequisites" in prompt_source
    assert "relocking or safe disconnection as rollback" in prompt_source
