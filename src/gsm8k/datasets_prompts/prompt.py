"""The four exemplars, the problems to score and the fixed 4-shot prompt (BR2.1-BR2.3)."""

import random
import re

from gsm8k.datasets_prompts.hub import Problem
from gsm8k.datasets_prompts.split import SPLIT_SEED, Split, index_of, sort_by_index

N_EXEMPLARS = 4
PROMPT_VERSION = "v1"

_CALCULATOR_NOTE = re.compile(r"<<.*?>>")


def choose_exemplars(dev_ids: list[str], split_seed: int = SPLIT_SEED) -> list[str]:
    """BR2.1: ``random.Random(split_seed).sample`` of the index-sorted dev ids, sampled order kept."""
    return random.Random(split_seed).sample(sort_by_index(list(dev_ids)), N_EXEMPLARS)


def strip_calculator_notes(text: str) -> str:
    """Remove every ``<<...>>`` calculator note from a worked answer."""
    return _CALCULATOR_NOTE.sub("", text)


def build_prompt(exemplars: list[Problem], question: str) -> str:
    """BR2.3: 'Question: <q>' newline 'Answer: <answer without notes>' per exemplar, blank lines
    between examples, then 'Question: <target>' newline 'Answer:'."""
    blocks = [f"Question: {p.question}\nAnswer: {strip_calculator_notes(p.answer)}" for p in exemplars]
    blocks.append(f"Question: {question}\nAnswer:")
    return "\n\n".join(blocks)


def problems_to_score(
    split_name: str,
    split: Split,
    problems: dict[str, list[Problem]],
    exemplar_ids: list[str],
    limit: int | None = None,
) -> list[Problem]:
    """BR2.2: dev = dev ids minus the exemplars (496); test = all test problems; both sorted by
    numeric index, and a limit takes the first N."""
    if limit is not None and limit < 0:
        raise ValueError(f"limit must be 0 or more: {limit}")
    if split_name == "dev":
        by_id = {p.id: p for p in problems["train"]}
        excluded = set(exemplar_ids)
        ids = sort_by_index([i for i in split.dev_ids if i not in excluded])
        chosen = [by_id[i] for i in ids]
    elif split_name == "test":
        chosen = sorted(problems["test"], key=lambda p: index_of(p.id))
    else:
        raise ValueError(f"split must be 'dev' or 'test': {split_name!r}")
    return chosen if limit is None else chosen[:limit]
