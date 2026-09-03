from fieldtech.providers.prompt import SYSTEM_PROMPT


def test_prompt_prioritizes_dhcp_before_dns_for_apipa() -> None:
    normalized_prompt = " ".join(SYSTEM_PROMPT.split())

    assert "complaint reports 169.254.x.x or APIPA" in normalized_prompt
    assert (
        "prioritize failure to obtain a DHCP lease over DNS failure"
        in normalized_prompt
    )
    assert (
        "Do not propose DNS, name-resolution, or public-internet tests"
        in normalized_prompt
    )
