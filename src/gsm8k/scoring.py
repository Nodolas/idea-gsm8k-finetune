"""AnswerScoring: cut a model output, extract its answer and compare it with the gold answer.

Rules BR3.1-BR3.5 (u1 rules.md). Pure functions: no model, no files.
"""

import re
from decimal import Decimal, InvalidOperation

# A number as a model writes it: optional '$' and minus sign, digits with optional thousands commas,
# an optional decimal part and an optional '%'. A trailing comma or full stop is never part of it.
_NUMBER = r"\$?-?\$?\d(?:[\d,]*\d)?(?:\.\d+)?%?"
_NUMBER_RE = re.compile(_NUMBER)
_HASH_NUMBER_RE = re.compile(r"####[ \t]*(" + _NUMBER + ")")
_NEW_QUESTION = "Question:"
_TOLERANCE = Decimal("1e-6")


def cut_output(text: str) -> str:
    """Keep only the text up to the stop point (BR3.5).

    The stop point is the end of the first line holding ``#### <number>`` or the start of a new
    ``Question:``, whichever comes first. Without a stop point the text is kept as it is.
    """
    stops = []
    match = _HASH_NUMBER_RE.search(text)
    if match:
        line_end = text.find("\n", match.end())
        stops.append(len(text) if line_end == -1 else line_end)
    question = text.find(_NEW_QUESTION)
    if question != -1:
        stops.append(question)
    return text[: min(stops)] if stops else text


def _normalise(number: str) -> str:
    return number.replace(",", "").replace("$", "").replace("%", "").strip()


def extract_answer(text: str) -> str | None:
    """The predicted answer with commas, '$' and '%' removed, or None when the text has no number.

    The number after the first ``####`` wins (BR3.1); otherwise the last number in the text (BR3.2);
    no number at all gives None (BR3.3).
    """
    match = _HASH_NUMBER_RE.search(text)
    if match:
        return _normalise(match.group(1))
    numbers = _NUMBER_RE.findall(text)
    if not numbers:
        return None
    return _normalise(numbers[-1])


def _to_decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(_normalise(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def is_correct(predicted: str | None, gold: str) -> bool:
    """True when both read as numbers and differ by less than 1e-6 (BR3.4); None is wrong (BR3.3)."""
    if predicted is None:
        return False
    left = _to_decimal(predicted)
    right = _to_decimal(gold)
    if left is None or right is None:
        return False
    return abs(left - right) < _TOLERANCE


def score(output: str, gold: str) -> tuple[str | None, bool]:
    """Cut the output at its stop point, extract the answer and compare it with the gold answer."""
    predicted = extract_answer(cut_output(output))
    return predicted, is_correct(predicted, gold)
