"""Assertions for the LLM evals, as pure functions so they can be tested without an LLM (#9).

An assertion that has never failed has not been shown to work: tests/test_eval_assertions.py
runs the three wrong answers the review found through these checks and expects them to be refused.
"""

import json
import re

_PATTERN_LOOKAHEAD = 40  # max. characters between a year and its value in the answer
_YEARS = {str(y) for y in range(1990, 2040)}
# Duizendtallen met punt of (harde/smalle) spatie, zoals gpt-oss schrijft: 91.500, 91 500.
_ANSWER_NUMBER = re.compile(r"\d{1,3}(?:[.\s]\d{3})+|\d{4,}")


def unpaired_years(answer: str, truth: dict[int, int]) -> list[str]:
    """Years whose value does not stand next to that year in the answer (Dutch thousands separators allowed)."""
    problems = []
    for year, expected in truth.items():
        # The separator swap must only touch the value: a blanket replace also rewrote the comma
        # in the {0,40} quantifier, so the old pattern never matched a correct answer.
        value = f"{expected:,}".replace(",", r"[.\s]?")
        pattern = rf"{year}[^\d]{{0,{_PATTERN_LOOKAHEAD}}}{value}"
        if not re.search(pattern, answer):
            problems.append(f"Jaar {year} niet gekoppeld aan {expected:,} in antwoord")
    return problems


def ungrounded_numbers(answer: str, tool_payloads: list) -> set[str]:
    """Numbers of four or more digits in the answer that appear in no tool payload of the same run."""
    tool_numbers: set[str] = set()
    for payload in tool_payloads:
        tool_numbers |= set(re.findall(r"\d{4,}", json.dumps(payload)))
    answer_numbers = {re.sub(r"[.\s]", "", n) for n in _ANSWER_NUMBER.findall(answer)}
    return answer_numbers - tool_numbers - _YEARS
