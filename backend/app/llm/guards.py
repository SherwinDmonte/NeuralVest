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


_MARKUP = re.compile(r"</?\s*(article|think|system|user|assistant)\b|```", re.IGNORECASE)
MIN_TEXT_CHARS = 20


def suspicious_text(text: str) -> str | None:
    """Reason why a free-text answer is unusable, or None. Catches a model echoing our
    prompt markup (seen in Phase 7: a digest that was just "<article>") or saying nothing."""
    stripped = text.strip()
    if _MARKUP.search(stripped):
        return "output contains prompt markup"
    if len(stripped) < MIN_TEXT_CHARS:
        return "output too short"
    return None


def unsupported_numbers(output_text: str, prompt_text: str) -> list[float]:
    """Numbers in `output_text` that are not present (up to rounding) in `prompt_text`."""
    allowed = extract_numbers(prompt_text)
    return [n for n in extract_numbers(output_text) if not _is_supported(n, allowed)]


# ---------------------------------------------------------------- contradictions (Phase 10)
# Pairs of opposite phrases used by the rule-based readings. If a reading states one side and
# the model's text states the other, the text contradicts a computed fact and is rejected
# (retry with a repair hint -> fallback model -> template, like an invented number).
OPPOSITES = [
    ("above its signal line", "below its signal line"),
    ("momentum strengthening", "momentum weakening"),
    ("above its 200-day average", "below its 200-day average"),
    ("overbought", "oversold"),
    ("(defensive)", "(aggressive)"),
    ("returns exceeded the risk-free rate", "did not exceed the risk-free rate"),
    ("and it later recovered", "has not yet recovered"),
    ("did better than", "did worse than"),
]
# Performance against the NIFTY 50 needs the SUBJECT: "the stock underperformed" and "the
# NIFTY 50 outperformed" say the same thing; "the benchmark underperformed the NIFTY 50" is
# nonsense (the benchmark IS the NIFTY 50) - the Phase 9 review case.
_PERF_VERB = re.compile(r"\b(out|under)perform(?:ed|s|ing)?\b(\s+(?:the\s+)?(?:nifty\s*50|benchmark|index|market))?",
                        re.IGNORECASE)
# the index is the SUBJECT only when it directly precedes the verb in the same clause (no comma)
_INDEX_SUBJECT = re.compile(r"\b(benchmark|nifty\s*50|index|market)(?:\s+\w+){0,2}\s*$", re.IGNORECASE)
_PERF_READING = re.compile(r"\b(out|under)performed the nifty 50", re.IGNORECASE)


def _performance_contradiction(text: str, readings: list[str]) -> str | None:
    """Who out/underperformed whom. "X underperformed the NIFTY 50" says X is the stock unless
    X is the benchmark itself; "the NIFTY 50 outperformed (the stock)" means the stock
    underperformed."""
    truth = next((m.group(1).lower() for r in readings if (m := _PERF_READING.search(r))), None)
    if truth is None:
        return None
    for m in _PERF_VERB.finditer(text):
        direction, index_object = m.group(1).lower(), bool(m.group(2))
        sentence_start = max(text.rfind(".", 0, m.start()), text.rfind(";", 0, m.start())) + 1
        before = text[sentence_start:m.start()]
        index_subject = _INDEX_SUBJECT.search(before)
        if index_subject and index_object:
            return "says the benchmark out/underperformed the NIFTY 50 (the comparison is the stock against it)"
        if index_subject:
            direction = "under" if direction == "out" else "out"  # the NIFTY 50 outperformed = stock underperformed
        elif not index_object:
            continue  # neither side is the index: not a benchmark statement
        if direction != truth:
            return f"says the stock {direction}performed the NIFTY 50, but it {truth}performed"
    return None


def contradicted_reading(text: str, readings: list[str] | tuple[str, ...]) -> str | None:
    """Reason why `text` contradicts one of the rule-based `readings`, or None."""
    if not readings:
        return None
    readings = [r for r in readings if r]
    low_text, low_readings = text.lower(), " | ".join(readings).lower()
    for a, b in OPPOSITES:
        for said, opposite in ((a, b), (b, a)):
            if said in low_readings and opposite not in low_readings and opposite in low_text:
                return f"says '{opposite}' but the computed reading is '{said}'"
    return _performance_contradiction(text, readings)
