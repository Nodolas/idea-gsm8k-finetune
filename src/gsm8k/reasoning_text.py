"""Reasoning lines and words of a model answer or worked solution (C2 rule, added 2026-11-08).

A text's reasoning lines are its stripped non-empty lines before the first line that starts with
``####`` (all non-empty lines when there is none); its words are the whitespace-separated words of
those lines. Self-taught generation (``gsm8k.cot``) and the reasoning comparison
(``gsm8k.reasoning_report``) both count with these, so the page and ``cot_stats.json`` agree.
"""


def reasoning_lines(text: str) -> list[str]:
    """The stripped non-empty lines before the first ``####`` line."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("####"):
            break
        if line:
            lines.append(line)
    return lines


def reasoning_words(text: str) -> int:
    """The number of whitespace-separated words in the reasoning lines."""
    return sum(len(line.split()) for line in reasoning_lines(text))
