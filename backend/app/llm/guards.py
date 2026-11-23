"""Output guards: the LLM may explain numbers, never invent them (architecture §6).

`unsupported_numbers` lists every number in the model's text that does not appear in the
prompt it was given (allowing for normal rounding). Any such number means the text
cannot be trusted and is replaced by the deterministic template.
"""

import re

# 1,356.30  -12.5  56  2026-11-23 (-> 2026, 11, 23)  14-day (-> 14)
_NUMBER = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|(?<![\w.])-?\d+(?:\.\d+)?")
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove Qwen3 <think>...</think> blocks (defence in depth; thinking is also disabled)."""
    text = _THINK_BLOCK.sub("", text)
    if "<think>" in text.lower():  # an unclosed block: drop everything after it
        text = text[: text.lower().index("<think>")]
    return text.strip()


def extract_numbers(text: str) -> list[float]:
    numbers = []
    for match in _NUMBER.findall(text):
        try:
            numbers.append(float(match.replace(",", "")))
        except ValueError:
            continue
    return numbers


def _is_supported(value: float, allowed: list[float]) -> bool:
    for ref in allowed:
        if ref == value:
            return True
        # Accept rounding of a known value (56.24 -> 56.2 or 56) and sign-free mentions
        # ("fell 2.3%" when the fact is -2.3).
        for candidate in (ref, -ref):
            if abs(candidate - value) <= max(0.5, abs(candidate) * 0.005) and _rounding_of(candidate, value):
                return True
    return False


def _rounding_of(ref: float, value: float) -> bool:
    return any(round(ref, digits) == round(value, digits) for digits in (0, 1, 2))


def unsupported_numbers(output_text: str, prompt_text: str) -> list[float]:
    """Numbers in `output_text` that are not present (up to rounding) in `prompt_text`."""
    allowed = extract_numbers(prompt_text)
    return [n for n in extract_numbers(output_text) if not _is_supported(n, allowed)]
