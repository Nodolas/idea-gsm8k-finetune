"""The course routes of the run service (contract C9, US12.3): ``/api/v1/course``.

The course is the guided path through the project: 24 steps whose texts, questions and run specs live in
``gsm8k.course.steps``. This module answers the overview and one step, queues a ``gpu`` step's runs (all or
none, results to ``outputs/course/runs.csv``), launches the CPU model-design inspection, checks quizzes and
keeps ``outputs/course/progress.json`` (``gsm8k.course.progress``). Course runs are learning runs: their rows
are read from ``outputs/course/runs.csv`` only, never from ``results/runs.csv``, and this module never
writes the run log.

Seam, read at call time (tests replace it): ``launch(argv, log_path, env) -> pid`` starts the inspection.
Error codes (C9): ``course_busy``, ``queue_full``, ``use_lab``, ``nothing_to_run``, ``invalid_answers``,
``invalid_text`` and ``progress_unreadable`` (plus the C6 ``not_found``). Course data modules are imported
at call time; nothing here imports torch (ADR-006).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI

from gsm8k._env import ROOT
from gsm8k.course import progress as course_progress
from gsm8k.run_control import queue as run_queue
from gsm8k.run_records import lock as run_lock
from gsm8k.run_records import log as run_log
from gsm8k.run_records import paths
from gsm8k.service.lab_routes import LabRoutes

Z_95 = 1.96
PROBLEMS = 100  # every course run scores the first 100 dev problems
CARD_GB = 6.5  # the 8 GB card less 1.5 GB for the desktop and activations (AC12.3.6)
GB = 1e9
LORA_RANK = 16
MIN_KEPT = 50
WITHIN_NOISE = "within noise"
REFERENCE_RUN = ("c01", "base-06")
REFERENCE_MODEL = "Qwen/Qwen3-0.6B-Base"
RUN_STATES = ("not-run", "queued", "running", "finished", "failed", "stopped")

MEMORY_NOTE = (
    "These figures leave out activations, which grow with batch size and sequence length, so a run needs "
    "some room beyond them."
)
COMPARISON_NOTE = (
    "100 problems give intervals about ±10 points wide, so a gain inside the noise is not a result. "
    "The reference runs in results/runs.csv (500 problems) are the ones to trust."
)

_ATTEMPT = re.compile(r"^course-(c[0-9]{2})-([a-z0-9-]+)-([0-9]+)$")
_processes: dict[int, subprocess.Popen] = {}


def launch(argv: list[str], log_path: Path, env: dict[str, str]) -> int:
    """Start the inspection in its own session from the project root; output is appended to the log.
    Returns the process id."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
    _processes[process.pid] = process
    return process.pid


def _alive(pid: int) -> bool:
    process = _processes.get(pid)
    if process is not None:
        if process.poll() is None:
            return True
        _processes.pop(pid, None)
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _interval(accuracy: float, n: int = PROBLEMS) -> tuple[float, float]:
    p = min(1.0, max(0.0, accuracy))
    half = Z_95 * math.sqrt(p * (1.0 - p) / n)
    return max(0.0, accuracy - half), min(1.0, accuracy + half)


def _read_json(path: Path) -> dict | None:
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class _Snapshot:
    """What one request knows about the course runs: the course rows, the run folders, the queue and the
    GPU lock, read once."""

    def __init__(self, outputs: Path, error: type[Exception]):
        self.outputs = outputs
        results = outputs / "course" / "runs.csv"
        try:
            self.rows, _ = run_log.read_rows(results)
        except OSError as exc:
            raise error(
                500, "run_log_unreadable", f"Run log could not be read: {results}", file=str(results)
            ) from exc
        self.row_by_attempt: dict[str, run_log.RunRow] = {}
        for row in self.rows:
            self.row_by_attempt[row.run_id] = row  # the last row of an attempt wins
        try:
            self.queued = [entry.attempt_id for entry in run_queue.list_queue(outputs)]
        except (OSError, ValueError):
            self.queued = []
        self.lock_id = self._lock_id()
        self.folders = self._folders()
        self.numbers: dict[tuple[str, str], set[int]] = {}
        for attempt_id in [
            *self.row_by_attempt,
            *self.queued,
            *self.folders,
            *([self.lock_id] if self.lock_id else []),
        ]:
            match = _ATTEMPT.match(attempt_id)
            if match:
                self.numbers.setdefault((match.group(1), match.group(2)), set()).add(int(match.group(3)))

    def _lock_id(self) -> str | None:
        path = self.outputs / "run.lock"
        if run_lock.is_free(path):
            return None
        content = run_lock.read_lock(path) or {}
        run_id = content.get("run_id")
        return run_id if isinstance(run_id, str) else None

    def _folders(self) -> set[str]:
        try:
            entries = list(self.outputs.iterdir())
        except OSError:
            return set()
        return {e.name for e in entries if e.name.startswith("course-") and e.is_dir()}

    # attempts

    def latest(self, step_id: str, run: str) -> str | None:
        numbers = self.numbers.get((step_id, run))
        return f"course-{step_id}-{run}-{max(numbers)}" if numbers else None

    def has_row(self, step_id: str, run: str) -> bool:
        return any(
            (m := _ATTEMPT.match(row.run_id)) is not None and (m.group(1), m.group(2)) == (step_id, run)
            for row in self.rows
        )

    def busy_attempt(self, step_id: str) -> str | None:
        """An attempt of the step that is queued or holds the GPU lock."""
        prefix = f"course-{step_id}-"
        for attempt_id in [*self.queued, *([self.lock_id] if self.lock_id else [])]:
            if attempt_id.startswith(prefix) and _ATTEMPT.match(attempt_id):
                return attempt_id
        return None

    def state(self, attempt_id: str) -> str:
        if attempt_id in self.queued:
            return "queued"
        if attempt_id == self.lock_id:
            return "running"
        if attempt_id in self.row_by_attempt:
            return "finished"
        status = (_read_json(self.outputs / attempt_id / "status.json") or {}).get("status")
        if status in ("failed", "stopped"):
            return status
        return "failed"  # a folder with no row, no final status and no lock: its process ended

    def row(self, attempt_id: str) -> run_log.RunRow | None:
        return self.row_by_attempt.get(attempt_id)


class CourseRoutes:
    def __init__(self, outputs_of: Callable[[], Path], error: type[Exception]):
        self._outputs_of = outputs_of
        self._error = error
        self._lab = LabRoutes(outputs_of, error)
        self._inspect_pid: int | None = None  # the inspection this service launched

    @property
    def outputs(self) -> Path:
        return Path(self._outputs_of())

    # reading

    def snapshot(self) -> _Snapshot:
        return _Snapshot(self.outputs, self._error)

    def progress(self) -> dict:
        try:
            return course_progress.read_progress(self.outputs)
        except course_progress.ProgressUnreadable as exc:
            raise self._progress_error(exc) from exc

    def _progress_error(self, exc: course_progress.ProgressUnreadable) -> Exception:
        return self._error(500, "progress_unreadable", str(exc), file=str(exc.path))

    def find(self, step_id: str) -> Any:
        from gsm8k.course.steps import get_step

        step = get_step(step_id) if isinstance(step_id, str) else None
        if step is None:
            raise self._error(404, "not_found", f"Step not found: {step_id}")
        return step

    def architectures(self) -> dict | None:
        return _read_json(self.outputs / "course" / "architectures.json")

    def lesson_state(self, step: Any) -> str:
        active, _ = self._lab.active()
        return self._lab.lesson_state(step.lesson, active)[1]

    # states

    def run_done(self, step: Any, snap: _Snapshot, architectures: dict | None) -> bool:
        if step.kind == "read":
            return True
        if step.kind == "inspect":
            return architectures is not None
        if step.kind == "lab":
            return self.lesson_state(step) == "finished"
        return all(snap.has_row(step.id, run) for run in step.runs)

    def run_started(self, step: Any, snap: _Snapshot, architectures: dict | None) -> bool:
        if step.kind == "gpu":
            return any(snap.latest(step.id, run) is not None for run in step.runs)
        if step.kind == "lab":
            return self.lesson_state(step) != "not-run"
        if step.kind == "inspect":
            return architectures is not None or (self.outputs / "course" / "inspect.log").exists()
        return False

    def summary(self, step: Any, snap: _Snapshot, progress: dict, architectures: dict | None) -> dict:
        mine = course_progress.step_state(progress, step.id)
        run_done = self.run_done(step, snap, architectures)
        quiz_passed = mine["passed_at"] is not None
        if run_done and quiz_passed:
            state = "done"
        elif (
            mine["opened_at"] is not None
            or mine["attempts"]
            or mine["own_words"] is not None
            or self.run_started(step, snap, architectures)
        ):
            state = "in-progress"
        else:
            state = "not-started"
        return {
            "id": step.id,
            "number": step.number,
            "part": step.part,
            "title": step.title,
            "kind": step.kind,
            "state": state,
            "run_done": run_done,
            "quiz_passed": quiz_passed,
        }

    # the overview

    def get_overview(self) -> dict:
        from gsm8k.course.steps import PARTS, STEPS

        progress = self.progress()
        snap = self.snapshot()
        architectures = self.architectures()
        summaries = [self.summary(step, snap, progress, architectures) for step in STEPS]
        parts = []
        for number, title in PARTS:
            mine = [s for s in summaries if s["part"] == number]
            parts.append(
                {
                    "number": number,
                    "title": title,
                    "done": sum(1 for s in mine if s["state"] == "done"),
                    "total": len(mine),
                    "steps": mine,
                }
            )
        done = sum(1 for s in summaries if s["state"] == "done")
        right, answered = course_progress.first_try(progress)
        next_step = next((s["id"] for s in summaries if s["state"] != "done"), None)
        return {
            "v": 1,
            "parts": parts,
            "progress": {
                "done": done,
                "total": len(STEPS),
                "percent": done * 100 // len(STEPS),
                "first_try_right": right,
                "questions_answered": answered,
            },
            "next_step": next_step,
        }

    # one step

    def run_info(self, spec: Any, snap: _Snapshot) -> dict:
        from gsm8k.course.configs import estimate_minutes

        minutes, measured = estimate_minutes(spec.step, spec.run, self.outputs)
        attempt_id = snap.latest(spec.step, spec.run)
        state = snap.state(attempt_id) if attempt_id is not None else "not-run"
        info: dict[str, Any] = {
            "run": spec.run,
            "command": spec.command,
            "model": spec.model,
            "changes": spec.changes_text,
            "estimate_minutes": minutes,
            "estimate_measured": measured,
            "attempt_id": attempt_id,
            "state": state,
            "accuracy": None,
            "interval_low": None,
            "interval_high": None,
            "minutes": None,
            "value": None,
            "metric": None,
        }
        row = snap.row(attempt_id) if attempt_id is not None and state == "finished" else None
        if row is not None:
            info.update(value=row.value, metric=row.metric, minutes=row.minutes)
            if row.metric == "accuracy":
                low, high = _interval(row.value)
                info.update(accuracy=row.value, interval_low=round(low, 4), interval_high=round(high, 4))
        return info

    def memory_table(self, architectures: dict | None) -> list[dict]:
        from gsm8k.course.steps import COURSE_MODELS

        designs: dict[str, dict] = {}
        if architectures is not None:
            for model in architectures.get("models") or []:
                if isinstance(model, dict) and isinstance(model.get("id"), str):
                    designs[model["id"]] = model
        table = []
        for course_model in COURSE_MODELS:
            row: dict[str, Any] = {
                "model": course_model.id,
                "full_gb": None,
                "lora_gb": None,
                "qlora_gb": None,
                "full_fits": None,
                "lora_fits": None,
                "qlora_fits": None,
            }
            need = self._memory_bytes(designs.get(course_model.id))
            if need is not None:
                for key, value in zip(("full", "lora", "qlora"), need, strict=True):
                    row[f"{key}_gb"] = round(value / GB, 2)
                    row[f"{key}_fits"] = value / GB <= CARD_GB
            table.append(row)
        return table

    @staticmethod
    def _memory_bytes(design: dict | None) -> tuple[float, float, float] | None:
        """(full, LoRA, QLoRA) training bytes of one design, or None when its figures are not all there."""
        if design is None:
            return None
        try:
            total = design["weights_total"]
            width, layers = design["width"], design["layers"]
            q_out = design["heads"] * design["head_size"]
            kv_out = design["kv_heads"] * design["head_size"]
            per_layer = (
                (width + q_out)  # q
                + 2 * (width + kv_out)  # k and v
                + (q_out + width)  # o
                + design["mlp_matrices"] * (width + design["mlp_width"])  # gate/up/down or up/down
            )
        except (KeyError, TypeError):
            return None
        adapter = LORA_RANK * per_layer * layers
        return total * 16.0, total * 2.0 + adapter * 16.0, total * 0.55 + adapter * 16.0

    def comparison(self, snap: _Snapshot) -> list[dict]:
        from gsm8k.course.steps import COURSE_RUNS

        listed = []
        for spec in COURSE_RUNS:
            numbers = [
                n
                for n in snap.numbers.get((spec.step, spec.run), ())
                if (row := snap.row(f"course-{spec.step}-{spec.run}-{n}")) is not None
                and row.metric == "accuracy"
                and row.data == "gsm8k-dev"
            ]
            if numbers:
                attempt_id = f"course-{spec.step}-{spec.run}-{max(numbers)}"
                listed.append((spec, attempt_id, snap.row(attempt_id)))
        reference = next((row for spec, _, row in listed if (spec.step, spec.run) == REFERENCE_RUN), None)
        ref_interval = _interval(reference.value) if reference is not None else None
        items = []
        for spec, attempt_id, row in listed:
            low, high = _interval(row.value)
            gain = noise = None
            if (
                reference is not None
                and ref_interval is not None
                and row.model == REFERENCE_MODEL
                and (spec.step, spec.run) != REFERENCE_RUN
            ):
                gain = round((row.value - reference.value) * 100, 1)
                overlap = low <= ref_interval[1] and ref_interval[0] <= high
                noise = WITHIN_NOISE if overlap else None
            items.append(
                {
                    "step": spec.step,
                    "run": spec.run,
                    "attempt_id": attempt_id,
                    "model": row.model,
                    "method": row.method,
                    "accuracy": row.value,
                    "interval_low": round(low, 4),
                    "interval_high": round(high, 4),
                    "gain_pts": gain,
                    "noise": noise,
                    "minutes": row.minutes,
                }
            )
        return items

    def notice(self, step: Any, snap: _Snapshot) -> str | None:
        if step.id == "c22":
            attempt_id = snap.latest("c22", "cotgen")
            row = snap.row(attempt_id) if attempt_id is not None else None
            if row is not None and row.metric == "kept_fraction":
                kept = round(row.value * 100)
                if kept < MIN_KEPT:
                    return f"Too few solutions were kept ({kept}); run the step again."
        if step.id == "c23":
            from gsm8k.course.configs import CourseRunRefused, course_config, next_attempt_id

            try:
                attempt_id = next_attempt_id("c23", "grpo", self.outputs)
                course_config("c23", "grpo", attempt_id, self.outputs, checkpoints=paths.checkpoints_root())
            except CourseRunRefused as exc:
                return str(exc)
        return None

    def get_step(self, step_id: str) -> dict:
        from gsm8k.course.steps import COURSE_RUNS
        from gsm8k.lab.lessons import LESSONS

        step = self.find(step_id)
        progress = self.progress()
        snap = self.snapshot()
        architectures = self.architectures()
        mine = course_progress.step_state(progress, step.id)
        answered = bool(mine["attempts"])
        questions = []
        for question in step.questions:
            questions.append(
                {
                    "prompt": question.prompt,
                    "options": list(question.options),
                    "answered": answered,
                    "right": question.right if answered else None,
                    "explanation": question.explanation if answered else None,
                }
            )
        lesson = None
        if step.kind == "lab":
            found = next((item for item in LESSONS if item.id == step.lesson), None)
            if found is not None:
                lesson = {
                    "id": found.id,
                    "number": found.number,
                    "title": found.title,
                    "question": found.question,
                    "state": self.lesson_state(step),
                }
        runs = []
        if step.kind == "gpu":
            runs = [self.run_info(spec, snap) for spec in COURSE_RUNS if spec.step == step.id]
        answer: dict[str, Any] = {
            "v": 1,
            "step": self.summary(step, snap, progress, architectures),
            "part_title": step.part_title,
            "why": step.why,
            "body": step.body,
            "questions": questions,
            "own_words_prompt": step.own_words_prompt,
            "own_words": mine["own_words"],
            "model_answer": step.model_answer if mine["own_words"] is not None else None,
            "runs": runs,
            "architectures": architectures if step.kind == "inspect" or step.id == "c19" else None,
            "lesson": lesson,
            "memory": self.memory_table(architectures) if step.id == "c19" else None,
            "comparison": self.comparison(snap) if step.id == "c24" else None,
            "notice": self.notice(step, snap),
        }
        if step.id == "c19":
            answer["memory_note"] = MEMORY_NOTE
        if step.id == "c24":
            answer["comparison_note"] = COMPARISON_NOTE
        return answer

    # running a step

    def run(self, step_id: str) -> dict:
        step = self.find(step_id)
        if step.kind == "lab":
            from gsm8k.lab.lessons import LESSONS

            found = next((item for item in LESSONS if item.id == step.lesson), None)
            title = f": {found.title}" if found is not None else ""
            raise self._error(
                422,
                "use_lab",
                f"This step runs in the Fine-Tuning Lab: start lesson {step.lesson}{title} on the Lab page.",
            )
        if step.kind == "read":
            raise self._error(
                422, "nothing_to_run", "This step has nothing to run; read it and take the quiz."
            )
        if step.kind == "inspect":
            return self.run_inspect(step)
        return self.run_gpu(step)

    def run_inspect(self, step: Any) -> dict:
        if self._inspect_pid is not None and _alive(self._inspect_pid):
            raise self._error(409, "course_busy", "The model-design inspection is already running.")
        argv = [sys.executable, "-m", "gsm8k", "course", "inspect"]
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "GSM8K_OUTPUTS_DIR": str(self.outputs)}
        pid = launch(argv, self.outputs / "course" / "inspect.log", env)
        self._inspect_pid = pid
        return {"step": step.id, "attempt_ids": []}

    def run_gpu(self, step: Any) -> dict:
        from gsm8k import run_config
        from gsm8k.course.configs import CourseRunRefused, course_config, next_attempt_id
        from gsm8k.course.steps import COURSE_RESULTS, COURSE_RUNS

        busy = self.snapshot().busy_attempt(step.id)
        if busy is not None:
            raise self._error(409, "course_busy", f"A run of this step is already queued or running: {busy}")
        specs = [spec for spec in COURSE_RUNS if spec.step == step.id]
        ids = {spec.run: next_attempt_id(step.id, spec.run, self.outputs) for spec in specs}
        entries = []
        try:
            for spec in specs:
                attempt_id = ids[spec.run]
                extra: dict[str, Any] = {}
                after = None
                if spec.run == "selfcot" and "cotgen" in ids:
                    extra["cot_data_run"] = ids["cotgen"]
                    after = ids["cotgen"]
                cfg = course_config(
                    step.id,
                    spec.run,
                    attempt_id,
                    self.outputs,
                    checkpoints=paths.checkpoints_root(),
                    **extra,
                )
                entries.append(
                    {
                        "attempt_id": attempt_id,
                        "config": run_config.to_dict(cfg),
                        "kind": spec.command,
                        "results": COURSE_RESULTS,
                        "after": after,
                    }
                )
        except CourseRunRefused as exc:
            raise self._error(422, "nothing_to_run", str(exc)) from exc
        try:
            run_queue.add_all(entries, outputs=self.outputs)
        except run_queue.QueueFull as exc:
            raise self._error(409, "queue_full", str(exc)) from exc
        return {"step": step.id, "attempt_ids": [entry["attempt_id"] for entry in entries]}

    # quiz, own words, opening

    def quiz(self, step_id: str, body: Any) -> dict:
        step = self.find(step_id)
        answers = body.get("answers") if isinstance(body, dict) else None
        try:
            return course_progress.check_quiz(step, answers, self.outputs)
        except course_progress.InvalidAnswers as exc:
            raise self._error(422, "invalid_answers", str(exc)) from exc
        except course_progress.ProgressUnreadable as exc:
            raise self._progress_error(exc) from exc

    def own_words(self, step_id: str, body: Any) -> dict:
        step = self.find(step_id)
        text = body.get("text") if isinstance(body, dict) else None
        try:
            return course_progress.save_own_words(step, text, self.outputs)
        except course_progress.InvalidText as exc:
            raise self._error(422, "invalid_text", str(exc)) from exc
        except course_progress.ProgressUnreadable as exc:
            raise self._progress_error(exc) from exc

    def open(self, step_id: str) -> dict:
        step = self.find(step_id)
        try:
            return {"opened_at": course_progress.record_open(step.id, self.outputs)}
        except course_progress.ProgressUnreadable as exc:
            raise self._progress_error(exc) from exc


def register(app: FastAPI, prefix: str, outputs_of: Callable[[], Path], error: type[Exception]) -> None:
    routes = CourseRoutes(outputs_of, error)

    @app.get(f"{prefix}/course")
    def get_course() -> dict:
        return routes.get_overview()

    @app.get(f"{prefix}/course/{{step_id}}")
    def get_course_step(step_id: str) -> dict:
        return routes.get_step(step_id)

    @app.post(f"{prefix}/course/{{step_id}}/run", status_code=202)
    def run_course_step(step_id: str) -> dict:
        return routes.run(step_id)

    @app.post(f"{prefix}/course/{{step_id}}/quiz")
    def post_course_quiz(step_id: str, body: Annotated[Any, Body()] = None) -> dict:
        return routes.quiz(step_id, body)

    @app.put(f"{prefix}/course/{{step_id}}/own-words")
    def put_course_own_words(step_id: str, body: Annotated[Any, Body()] = None) -> dict:
        return routes.own_words(step_id, body)

    @app.post(f"{prefix}/course/{{step_id}}/open")
    def open_course_step(step_id: str) -> dict:
        return routes.open(step_id)
