"""The course progress file ``outputs/course/progress.json`` (contract C9, US12.3).

``{"v": 1, "steps": {"<step>": {"opened_at", "quiz": {"attempts": [...], "passed_at"}, "own_words"}}}``.
A missing file reads as no progress; an unreadable one raises ``ProgressUnreadable`` and is never
overwritten. Writes are atomic (a temporary file in the same folder, then a rename), and a read-change-write
runs under one process-wide lock so two requests never lose each other's change. Step ids this version of
the course does not know stay in the file untouched.

This module imports nothing heavy and changes no environment variable (AC12.1.4, ADR-006).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PROGRESS_FILE = "progress.json"
OWN_WORDS_MAX = 4000

_write_lock = threading.RLock()


class ProgressUnreadable(Exception):
    """``progress.json`` exists but cannot be read; ``path`` names it."""

    def __init__(self, path: Path):
        self.path = Path(path)
        super().__init__(f"Course progress could not be read: {self.path}")


class InvalidAnswers(ValueError):
    """The quiz answers are not one chosen option per question."""


class InvalidText(ValueError):
    """The own-words text is empty or longer than 4000 characters."""


def progress_path(outputs: Path) -> Path:
    return Path(outputs) / "course" / PROGRESS_FILE


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_progress(outputs: Path) -> dict:
    """The progress file as a dict; a missing file is ``{"v": 1, "steps": {}}``; an unreadable one (not
    JSON, not an object, or ``steps`` not an object) raises ``ProgressUnreadable``."""
    path = progress_path(outputs)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"v": SCHEMA_VERSION, "steps": {}}
    except (OSError, UnicodeDecodeError) as exc:
        raise ProgressUnreadable(path) from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ProgressUnreadable(path) from exc
    if not isinstance(data, dict):
        raise ProgressUnreadable(path)
    steps = data.setdefault("steps", {})
    if not isinstance(steps, dict):
        raise ProgressUnreadable(path)
    data.setdefault("v", SCHEMA_VERSION)
    return data


def _write(outputs: Path, data: dict) -> None:
    """Write the whole file atomically."""
    path = progress_path(outputs)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{PROGRESS_FILE}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _entry(data: dict, step_id: str) -> dict:
    """The step's entry in ``data`` with every key present (created in place when missing)."""
    steps = data["steps"]
    entry = steps.get(step_id)
    if not isinstance(entry, dict):
        entry = {}
        steps[step_id] = entry
    entry.setdefault("opened_at", None)
    if not isinstance(entry.get("quiz"), dict):
        entry["quiz"] = {"attempts": [], "passed_at": None}
    quiz = entry["quiz"]
    if not isinstance(quiz.get("attempts"), list):
        quiz["attempts"] = []
    quiz.setdefault("passed_at", None)
    entry.setdefault("own_words", None)
    return entry


def step_state(progress: dict, step_id: str) -> dict:
    """A read-only view of one step's progress: ``opened_at``, ``attempts`` (list), ``passed_at`` and
    ``own_words`` (the text or None), tolerant of missing or malformed parts."""
    entry = progress.get("steps", {}).get(step_id)
    entry = entry if isinstance(entry, dict) else {}
    quiz = entry.get("quiz") if isinstance(entry.get("quiz"), dict) else {}
    attempts = quiz.get("attempts") if isinstance(quiz.get("attempts"), list) else []
    own = entry.get("own_words") if isinstance(entry.get("own_words"), dict) else None
    text = own.get("text") if own is not None and isinstance(own.get("text"), str) else None
    opened = entry.get("opened_at")
    passed = quiz.get("passed_at")
    return {
        "opened_at": opened if isinstance(opened, str) else None,
        "attempts": [a for a in attempts if isinstance(a, dict)],
        "passed_at": passed if isinstance(passed, str) else None,
        "own_words": text,
    }


def record_open(step_id: str, outputs: Path) -> str:
    """Record the first time a step was opened and return it; later calls keep (and return) it."""
    with _write_lock:
        data = read_progress(outputs)
        existing = step_state(data, step_id)["opened_at"]
        if existing is not None:
            return existing
        opened_at = _now()
        _entry(data, step_id)["opened_at"] = opened_at
        _write(outputs, data)
        return opened_at


def _checked_answers(step: Any, answers: Any) -> list[int]:
    count = len(step.questions)
    if not isinstance(answers, list) or len(answers) != count:
        raise InvalidAnswers(f"Give one answer for each of the {count} questions")
    for index, (answer, question) in enumerate(zip(answers, step.questions, strict=True), start=1):
        if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer < len(question.options):
            raise InvalidAnswers(
                f"Answer {index} must be a whole number from 0 to {len(question.options) - 1}"
            )
    return list(answers)


def check_quiz(step: Any, answers: Any, outputs: Path) -> dict:
    """Check one attempt, store it and answer the C9 QuizResult. Raises ``InvalidAnswers`` (nothing is
    stored) or ``ProgressUnreadable``. The quiz is passed once an attempt has every answer right."""
    chosen = _checked_answers(step, answers)
    right = [answer == question.right for answer, question in zip(chosen, step.questions, strict=True)]
    with _write_lock:
        data = read_progress(outputs)
        quiz = _entry(data, step.id)["quiz"]
        at = _now()
        quiz["attempts"].append({"answers": chosen, "right": right, "at": at})
        passed = all(right)
        if passed and not isinstance(quiz.get("passed_at"), str):
            quiz["passed_at"] = at
        attempts = len(quiz["attempts"])
        _write(outputs, data)
    return {
        "results": [
            {"right": ok, "right_option": question.right, "explanation": question.explanation}
            for ok, question in zip(right, step.questions, strict=True)
        ],
        "passed": passed,
        "attempts": attempts,
    }


def save_own_words(step: Any, text: Any, outputs: Path) -> dict:
    """Store the own-words answer (1 to 4000 characters; it can be changed) and answer ``saved_at`` and the
    step's model answer. Raises ``InvalidText`` (nothing is stored) or ``ProgressUnreadable``."""
    if not isinstance(text, str) or not 1 <= len(text) <= OWN_WORDS_MAX:
        raise InvalidText(f"Write between 1 and {OWN_WORDS_MAX} characters")
    with _write_lock:
        data = read_progress(outputs)
        saved_at = _now()
        _entry(data, step.id)["own_words"] = {"text": text, "saved_at": saved_at}
        _write(outputs, data)
    return {"saved_at": saved_at, "model_answer": step.model_answer}


def first_try(progress: dict) -> tuple[int, int]:
    """(questions answered right on the first try, questions answered) over the steps this course knows;
    only each step's first attempt counts."""
    from gsm8k.course.steps import STEPS

    right = answered = 0
    for step in STEPS:
        attempts = step_state(progress, step.id)["attempts"]
        if not attempts:
            continue
        flags = attempts[0].get("right")
        if not isinstance(flags, list):
            continue
        flags = flags[: len(step.questions)]
        answered += len(flags)
        right += sum(1 for flag in flags if flag is True)
    return right, answered
