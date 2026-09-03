from fieldtech.providers.prompt import SYSTEM_PROMPT


def test_prompt_limits_technician_message_to_structured_action() -> None:
    normalized_prompt = " ".join(SYSTEM_PROMPT.split())

    assert (
        "technician_message must describe only the same single action "
        "represented by next_test or intervention"
        in normalized_prompt
    )
    assert (
        "Do not introduce or recommend any additional diagnostic test, "
        "command, intervention, restart, reset, power cycle, or "
        "configuration change there"
        in normalized_prompt
    )
    assert "If both next_test and intervention are null" in normalized_prompt
    assert (
        "must not instruct the technician to take an additional action"
        in normalized_prompt
    )
