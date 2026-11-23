import pytest

from app.llm.guards import extract_numbers, strip_thinking, unsupported_numbers


def test_strip_thinking_removes_closed_and_unclosed_blocks():
    assert strip_thinking("<think>reasoning</think>\n{\"a\": 1}") == '{"a": 1}'
    assert strip_thinking('{"a": 1}<think>never closed') == '{"a": 1}'


def test_extract_numbers_handles_commas_decimals_signs_and_dates():
    # Date parts are read as positive numbers (the hyphen follows a digit, so it is not a sign).
    assert extract_numbers("Close 1,356.30, RSI 56.2, change -2.5% on 2026-11-23 (14-day)") == [
        1356.30, 56.2, -2.5, 2026, 11, 23, 14,
    ]


@pytest.mark.parametrize(
    "output, prompt, expected",
    [
        ("RSI is 56.2", '{"rsi_14": 56.24}', []),  # rounding allowed
        ("RSI is about 56", '{"rsi_14": 56.24}', []),
        ("The stock fell 2.3%", '{"change_pct": -2.31}', []),  # sign-free mention
        ("Close was 1,356.30", '{"close": 1356.3}', []),
        ("RSI is 70", '{"rsi_14": 56.24}', [70.0]),  # invented
        ("Target price 1500", '{"close": 1356.3}', [1500.0]),
        ("No numbers at all", "{}", []),
    ],
)
def test_unsupported_numbers(output, prompt, expected):
    assert unsupported_numbers(output, prompt) == expected


@pytest.mark.parametrize(
    "text, problem",
    [("<article>", "output contains prompt markup"), ("Summary </article> injected", "output contains prompt markup"),
     ("<think>hmm</think> fine text here", "output contains prompt markup"), ("Too short.", "output too short"),
     ("A normal, complete sentence about results.", None)],
)
def test_suspicious_text(text, problem):
    from app.llm.guards import suspicious_text
    assert suspicious_text(text) == problem


def test_rupee_amounts_in_prompt_are_supported():
    """Regression (Phase 10 live run): json.dumps escaped the rupee sign (\u20b999,294), so the
    guard could not read 99,294 in the prompt and rejected a correct answer."""
    from app.llm import prompts as p
    spec = p.portfolio_explanation_prompt({"cash_reading": "57 whole shares cost ₹99,294 and ₹706 is left as cash"})
    assert "₹99,294" in spec.user
    assert unsupported_numbers("The shares cost ₹99,294 and ₹706 stays as cash.", spec.system + spec.user) == []
