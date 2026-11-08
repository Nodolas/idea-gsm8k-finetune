"""GRPO reward functions (AC7.1.1): correctness 1.0 or 0.0, a small format reward, and their sum.

Pure functions on top of ``gsm8k.scoring``; no torch, trl or transformers import. The ``*_rewards``
functions have the shape trl's ``GRPOTrainer`` calls: ``(completions, gold, **kwargs) -> list[float]``,
where a completion is a string or a list of message dicts (the text is the last message's content).
"""

import re
from collections.abc import Sequence
from typing import Any

from gsm8k.scoring import score

FORMAT_BONUS = 0.1
_HASH_LINE_RE = re.compile(r"####[ \t]*\$?-?\$?\d")


def correctness_reward(completion: str, gold: str) -> float:
    """1.0 when the completion's answer matches ``gold`` under the scoring rules, else 0.0."""
    return 1.0 if score(completion, str(gold))[1] else 0.0


def format_reward(completion: str) -> float:
    """0.1 when the completion has a ``#### <number>`` line, else 0.0 (right or wrong answer)."""
    return FORMAT_BONUS if _HASH_LINE_RE.search(completion) else 0.0


def total_reward(completion: str, gold: str) -> float:
    """Correctness plus format reward."""
    return correctness_reward(completion, gold) + format_reward(completion)


def completion_text(completion: Any) -> str:
    """The text of a completion given as a string or as a list of message dicts."""
    if isinstance(completion, str):
        return completion
    if isinstance(completion, Sequence) and completion:
        last = completion[-1]
        if isinstance(last, dict):
            return str(last.get("content") or "")
        return str(last)
    return ""


def correctness_rewards(completions: Sequence[Any], gold: Sequence[str], **kwargs: Any) -> list[float]:
    """trl-shaped correctness rewards, one float per completion."""
    return [correctness_reward(completion_text(c), g) for c, g in zip(completions, gold, strict=True)]


def format_rewards(
    completions: Sequence[Any], gold: Sequence[str] | None = None, **kwargs: Any
) -> list[float]:
    """trl-shaped format rewards, one float per completion."""
    return [format_reward(completion_text(c)) for c in completions]


def total_rewards(completions: Sequence[Any], gold: Sequence[str], **kwargs: Any) -> list[float]:
    """trl-shaped total rewards, one float per completion."""
    return [total_reward(completion_text(c), g) for c, g in zip(completions, gold, strict=True)]
