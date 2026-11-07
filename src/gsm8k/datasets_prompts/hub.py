"""The only Hugging Face Hub access (NFR6.1, NFR6.3, NFR6.4; BR1.2).

Everything loads anonymously (no token), at a pinned commit hash, from safetensors only and with
no remote code. The pins were resolved from the Hub once at Code Generation (2026-11-06); moving
one is a spec change (`inception/changes.md`) and changes later configuration hashes.

Heavy libraries (datasets, transformers) are imported inside the functions, so importing this
module stays light; the in-folder caches are already set by ``gsm8k/__init__.py``.
"""

import re
from dataclasses import dataclass

DATASET_ID = "openai/gsm8k"
DATASET_CONFIG = "main"
DATASET_REVISION = "740312add88f781978c0658806c59bc2815b9866"

# Generalisation sets, evaluation only (FR5.1; brief). Pinned to the Hub heads read on 2026-11-07.
GSMPLUS_ID = "qintongli/GSM-Plus"
GSMPLUS_SPLIT = "testmini"
GSMPLUS_REVISION = "3b708db57b96a16e8e3368ed2956990c0809440e"
GSMSYM_ID = "apple/GSM-Symbolic"
GSMSYM_CONFIG = "p1"
GSMSYM_SPLIT = "test"
GSMSYM_REVISION = "93b5b3758d9d9841ffe81d6cd2ae2b030685b078"
GENERALISATION_SPLITS = ("gsmplus-testmini", "gsmsym-p1")

MODEL_REVISIONS: dict[str, str] = {
    "Qwen/Qwen3-0.6B-Base": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
    "Qwen/Qwen3-1.7B-Base": "ea980cb0a6c2ae4b936e82123acc929f1cec04c1",
}

_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
# A plain decimal number: an optional minus sign, digits and an optional decimal part. GSM-Plus rows
# whose answer is anything else ("None", "1/4") cannot be compared under BR3.4 and are left out.
_PLAIN_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Problem:
    """One problem; ``gold`` is the final answer after ``####``, as written.

    GSM8K ids are ``gsm8k-<split>-<row>``; GSM-Plus ``gsmplus-testmini-<row>``; GSM-Symbolic
    ``gsmsym-p1-<row>``.
    """

    id: str
    question: str
    answer: str
    gold: str


def _check_revision(repo_id: str, revision: str) -> None:
    if not isinstance(revision, str) or not _REVISION_PATTERN.match(revision):
        raise ValueError(f"Revision for {repo_id} must be a 40-character commit hash: {revision!r}")


def _check_model(model_id: str, revision: str) -> None:
    if model_id not in MODEL_REVISIONS:
        allowed = ", ".join(sorted(MODEL_REVISIONS))
        raise ValueError(f"Unknown model: {model_id} (pinned models: {allowed})")
    _check_revision(model_id, revision)


def gold_of(answer: str) -> str:
    """The text after the last ``####`` of a worked answer, stripped."""
    if "####" not in answer:
        raise ValueError("GSM8K answer has no '####' line")
    return answer.split("####")[-1].strip()


def load_gsm8k(revision: str = DATASET_REVISION) -> dict[str, list[Problem]]:
    """Load ``openai/gsm8k`` config ``main`` anonymously into the project cache.

    Returns ``{"train": [...], "test": [...]}`` with ids ``gsm8k-<split>-<row index>``.
    A failed download raises ``RuntimeError`` naming the dataset.
    """
    _check_revision(DATASET_ID, revision)
    import datasets

    try:
        ds = datasets.load_dataset(DATASET_ID, DATASET_CONFIG, revision=revision, token=False)
    except Exception as exc:  # network, missing revision, damaged cache
        raise RuntimeError(
            f"Could not load dataset {DATASET_ID} ({DATASET_CONFIG}) at {revision}: {exc}"
        ) from exc
    out: dict[str, list[Problem]] = {}
    for name in ("train", "test"):
        rows = ds[name]
        out[name] = [
            Problem(
                id=f"gsm8k-{name}-{i}",
                question=row["question"],
                answer=row["answer"],
                gold=gold_of(row["answer"]),
            )
            for i, row in enumerate(rows)
        ]
    return out


def _load_hub_dataset(repo_id: str, config: str | None, revision: str):
    _check_revision(repo_id, revision)
    import datasets

    name = f"{repo_id} ({config})" if config else repo_id
    try:
        return datasets.load_dataset(repo_id, config, revision=revision, token=False)
    except Exception as exc:  # network, missing revision, damaged cache
        raise RuntimeError(f"Could not load dataset {name} at {revision}: {exc}") from exc


def _gsmplus_problems(rows) -> tuple[list[Problem], int]:
    problems: list[Problem] = []
    left_out = 0
    for i, row in enumerate(rows):
        gold = str(row["answer"]).strip()
        if not _PLAIN_NUMBER.match(gold):
            left_out += 1
            continue
        solution = (row.get("solution") or "").strip()
        problems.append(
            Problem(
                id=f"gsmplus-testmini-{i}",
                question=row["question"],
                answer=f"{solution}\n#### {gold}" if solution else f"#### {gold}",
                gold=gold,
            )
        )
    return problems, left_out


def _gsmsym_problems(rows) -> tuple[list[Problem], int]:
    return [
        Problem(
            id=f"gsmsym-p1-{i}",
            question=row["question"],
            answer=row["answer"],
            gold=gold_of(row["answer"]),
        )
        for i, row in enumerate(rows)
    ], 0


def load_generalisation(split: str) -> tuple[list[Problem], int]:
    """Load a generalisation set (evaluation only, FR5.1) anonymously at its pinned commit.

    ``split`` is ``gsmplus-testmini`` (GSM-Plus testmini) or ``gsmsym-p1`` (GSM-Symbolic p1).
    Returns the problems in row order and the count of rows left out: GSM-Plus rows whose answer is
    not a plain decimal number (the critical-thinking "None" rows and fractions) cannot be scored
    (BR3.4); GSM-Symbolic is loaded whole. A failed download raises ``RuntimeError``.
    """
    if split == "gsmplus-testmini":
        ds = _load_hub_dataset(GSMPLUS_ID, None, GSMPLUS_REVISION)
        return _gsmplus_problems(ds[GSMPLUS_SPLIT])
    if split == "gsmsym-p1":
        ds = _load_hub_dataset(GSMSYM_ID, GSMSYM_CONFIG, GSMSYM_REVISION)
        return _gsmsym_problems(ds[GSMSYM_SPLIT])
    allowed = ", ".join(GENERALISATION_SPLITS)
    raise ValueError(f"Unknown generalisation split: {split} (expected one of {allowed})")


def load_tokenizer(model_id: str, revision: str):
    """The tokenizer of a pinned model, loaded anonymously with no remote code."""
    _check_model(model_id, revision)
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False, token=False)


def load_causal_lm(model_id: str, revision: str, dtype):
    """A pinned causal language model: safetensors only, no remote code, no token."""
    _check_model(model_id, revision)
    from transformers import AutoModelForCausalLM

    return AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=revision,
        dtype=dtype,
        use_safetensors=True,
        trust_remote_code=False,
        token=False,
    )
