"""Self-taught chain of thought: the training problems of a ``selfcot`` fine-tune (US10.2; FR10.2, NFR8; C2).

A generation run (method ``cotgen``) writes ``outputs/<run_id>/cot_data.jsonl``: one C2 line per kept
problem (``v``, ``problem_id``, ``question``, ``gold``, ``solution``, ``correct_samples``, ``samples``).
Each line becomes a ``Problem`` whose ``answer`` is the kept solution, so the supervised loop's
``step-by-step`` target keeps the model's own reasoning and ends with ``#### <gold>``.

The whole file is checked before anything is chosen: a missing or unreadable file, or any dev or test
problem in it (not only among the first N), raises ``CotDataError`` (a ValueError) naming the file or
the leaked ids.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from gsm8k.datasets_prompts.hub import Problem
from gsm8k.run_config import RunConfig
from gsm8k.run_records import paths

COT_DATA_FILE = "cot_data.jsonl"
MAX_LISTED = 3
_TEXT_FIELDS = ("problem_id", "question", "gold", "solution")


class CotDataError(ValueError):
    """The kept solutions of a generation run cannot be trained on (the message says why)."""


def cot_data_path(run_id: str) -> Path:
    """``outputs/<run_id>/cot_data.jsonl`` of a generation run. Raises CotDataError for an invalid id."""
    try:
        return paths.run_dir(run_id) / COT_DATA_FILE
    except ValueError as exc:
        raise CotDataError(f"cot_data_run is not a valid run id: {run_id!r}") from exc


def _read_lines(path: Path) -> list[dict]:
    """Every C2 line of the file; raises CotDataError naming the file when it cannot be used."""
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError as exc:
        raise CotDataError(f"Kept solutions not found: {path} (no {COT_DATA_FILE} in that run)") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise CotDataError(f"Kept solutions could not be read: {path} ({exc})") from exc
    records: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise CotDataError(f"Kept solutions could not be read: {path} (line {number}: {exc})") from exc
        if not isinstance(record, dict):
            raise CotDataError(f"Kept solutions could not be read: {path} (line {number} is not an object)")
        missing = [name for name in _TEXT_FIELDS if not isinstance(record.get(name), str) or not record[name]]
        if missing:
            raise CotDataError(
                f"Kept solutions could not be read: {path} (line {number} has no {', '.join(missing)})"
            )
        records.append(record)
    return records


def load_cot_problems(
    run_id: str,
    dev_ids: Iterable[str],
    test_ids: Iterable[str],
    train_examples: int | str,
) -> list[Problem]:
    """The first ``train_examples`` kept solutions of generation run ``run_id`` in problem index order
    (``all``, or more than were kept: every one), each as ``Problem(id, question, solution, gold)``.

    Raises CotDataError when the file is missing or unreadable, when it holds a dev or test problem (or
    any id outside the training part), naming up to three of them, or when it holds no solution.
    """
    from gsm8k.datasets_prompts import split

    path = cot_data_path(run_id)
    records = _read_lines(path)

    forbidden = set(dev_ids) | set(test_ids)
    leaked: list[str] = []
    for record in records:
        problem_id = record["problem_id"]
        if (problem_id in forbidden or not problem_id.startswith(split.TRAIN_PREFIX)) and (
            problem_id not in leaked
        ):
            leaked.append(problem_id)
    if leaked:
        listed = ", ".join(leaked[:MAX_LISTED])
        more = f" and {len(leaked) - MAX_LISTED} more" if len(leaked) > MAX_LISTED else ""
        raise CotDataError(
            f"Kept solutions hold dev or test problems, which are never trained on: {listed}{more} ({path})"
        )

    if not records:
        raise CotDataError(f"The generation run {run_id} kept no solutions: {path} is empty")

    by_id: dict[str, dict] = {}
    for record in records:
        problem_id = record["problem_id"]
        try:
            split.index_of(problem_id)
        except ValueError as exc:
            raise CotDataError(f"Kept solutions could not be read: {path} ({exc})") from exc
        if problem_id in by_id:
            raise CotDataError(f"Kept solutions could not be read: {path} ({problem_id} appears twice)")
        by_id[problem_id] = record

    ordered = split.sort_by_index(list(by_id))
    if train_examples != "all":
        ordered = ordered[: int(train_examples)]
    return [
        Problem(
            id=problem_id,
            question=by_id[problem_id]["question"],
            answer=by_id[problem_id]["solution"],
            gold=by_id[problem_id]["gold"],
        )
        for problem_id in ordered
    ]


def load_for_config(cfg: RunConfig) -> list[Problem]:
    """The self-taught training problems of a ``selfcot`` configuration: its ``cot_data_run``'s kept
    solutions, checked against the fixed split's dev ids and the GSM8K test ids. Raises CotDataError."""
    from gsm8k.datasets_prompts import hub, split

    if not cfg.cot_data_run:
        raise CotDataError("method selfcot needs cot_data_run (--cot-data-run <generation run id>)")
    problems = hub.load_gsm8k(cfg.dataset_revision)
    data_split = split.load_or_build_split([p.id for p in problems["train"]], split_seed=cfg.split_seed)
    return load_cot_problems(
        cfg.cot_data_run,
        data_split.dev_ids,
        [p.id for p in problems["test"]],
        cfg.train_examples,
    )
