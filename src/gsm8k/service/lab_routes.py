"""The lab routes of the run service (contract C8, US11.3): ``/api/v1/lab``.

The lab is CPU only: a lesson is started as its own ``gsm8k lab run`` process, with no GPU lock and no
queue. A lab run is going while the flock on ``outputs/lab/lab.lock`` is held, or while the process this
service launched has not ended. Lessons and configuration come from ``gsm8k.lab`` at call time; nothing
here imports torch.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from gsm8k._env import ROOT

STALE_RUNNING_MESSAGE = "The lab run ended without a status."
LAB_MODEL = {"name": "EleutherAI/pythia-31m", "weights": 30494720, "layers": 6, "device": "cpu"}


def launch(argv: list[str], log_path: Path) -> subprocess.Popen:
    """Start the lab command in its own session, from the project root, on the CPU; output is appended."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        return subprocess.Popen(
            argv,
            cwd=ROOT,
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
        )


def send_signal(pid: int, sig: int) -> None:
    os.kill(pid, sig)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _lock_holder(lab_dir: Path) -> dict | None:
    """The lock's content while its flock is held by another open file, else None."""
    path = lab_dir / "lab.lock"
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _read_json(path) or {}
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    finally:
        os.close(fd)


def _complete_lines(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = []
    for raw in text.split("\n")[:-1]:  # the last piece has no newline yet: not a line
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if isinstance(line, dict):
            lines.append(line)
    return lines


class LabRoutes:
    def __init__(self, outputs_of: Callable[[], Path], error: type[Exception]):
        self._outputs_of = outputs_of
        self._error = error
        self._launched: tuple[str, Any] | None = None  # (lesson, process)

    @property
    def lab_dir(self) -> Path:
        return Path(self._outputs_of()) / "lab"

    # the one place that says which lesson runs and what its state is

    def active(self) -> tuple[str | None, int | None]:
        """(lesson, pid) of the lab run going, or (None, None)."""
        holder = _lock_holder(self.lab_dir)
        if holder is not None:
            lesson = holder.get("lesson")
            pid = holder.get("pid")
            return (lesson if isinstance(lesson, str) else None), (pid if isinstance(pid, int) else None)
        if self._launched is not None:
            lesson, process = self._launched
            if process.poll() is None:
                return lesson, process.pid
            self._launched = None
        return None, None

    def lesson_state(self, lesson_id: str, active: str | None) -> tuple[dict, str]:
        """(status object, state) of a lesson; the shared source of the list and the lesson answer."""
        status: dict = {
            "state": "not-run",
            "variant": None,
            "done": [],
            "started_at": None,
            "ended_at": None,
            "message": None,
        }
        raw = _read_json(self.lab_dir / lesson_id / "status.json")
        if raw is not None:
            status["state"] = raw.get("state") if raw.get("state") else "not-run"
            for key in ("variant", "started_at", "ended_at", "message"):
                status[key] = raw.get(key)
            done = raw.get("done")
            status["done"] = list(done) if isinstance(done, list) else []
        if active == lesson_id:
            status["state"] = "running"
        elif status["state"] == "running":
            status["state"] = "failed"
            status["message"] = STALE_RUNNING_MESSAGE
        return status, status["state"]

    def info(self, lesson: Any, state: str) -> dict:
        from gsm8k.lab.config import changes_text, estimate_minutes

        return {
            "id": lesson.id,
            "number": lesson.number,
            "title": lesson.title,
            "question": lesson.question,
            "watch": lesson.watch,
            "guess_prompt": lesson.guess_prompt,
            "guess_options": list(lesson.guess_options),
            "variants": [
                {"name": v.name, "label": v.label, "changes": changes_text(v)} for v in lesson.variants
            ],
            "why": lesson.why,
            "big_run": lesson.big_run,
            "check": lesson.check,
            "estimate_minutes": estimate_minutes(lesson),
            "state": state,
        }

    def find(self, lesson_id: str) -> Any:
        from gsm8k.lab.lessons import LESSONS

        for lesson in LESSONS:
            if lesson.id == lesson_id:
                return lesson
        raise self._error(404, "not_found", f"Lesson not found: {lesson_id}")

    # handlers

    def get_list(self) -> dict:
        from gsm8k.lab.lessons import LESSONS

        active, _ = self.active()
        return {
            "model": dict(LAB_MODEL),
            "lessons": [self.info(lesson, self.lesson_state(lesson.id, active)[1]) for lesson in LESSONS],
            "active": active,
        }

    def get_lesson(self, lesson_id: str) -> dict:
        lesson = self.find(lesson_id)
        active, _ = self.active()
        status, state = self.lesson_state(lesson.id, active)
        results = []
        for variant in lesson.variants:
            folder = self.lab_dir / lesson.id / variant.name
            results.append(
                {
                    "name": variant.name,
                    "label": variant.label,
                    "lines": _complete_lines(folder / "metrics.jsonl"),
                    "summary": _read_json(folder / "summary.json"),
                }
            )
        return {"lesson": self.info(lesson, state), "status": status, "results": results}

    def run(self, lesson_id: str) -> dict:
        lesson = self.find(lesson_id)
        active, _ = self.active()
        if active is not None:
            raise self._error(409, "lab_busy", f"A lab run is already active: {active}")
        argv = [sys.executable, "-m", "gsm8k", "lab", "run", lesson.id]
        process = launch(argv, self.lab_dir / f"{lesson.id}.log")
        self._launched = (lesson.id, process)
        return {"lesson": lesson.id, "state": "running"}

    def stop(self) -> dict:
        active, pid = self.active()
        if active is None or pid is None:
            raise self._error(409, "no_lab_run", "No lab run is going.")
        send_signal(pid, signal.SIGTERM)
        return {"lesson": active}


def register(app: FastAPI, prefix: str, outputs_of: Callable[[], Path], error: type[Exception]) -> None:
    routes = LabRoutes(outputs_of, error)

    @app.get(f"{prefix}/lab")
    def get_lab() -> dict:
        return routes.get_list()

    @app.post(f"{prefix}/lab/stop")
    def stop_lab() -> dict:
        return routes.stop()

    @app.get(f"{prefix}/lab/{{lesson_id}}")
    def get_lab_lesson(lesson_id: str) -> dict:
        return routes.get_lesson(lesson_id)

    @app.post(f"{prefix}/lab/{{lesson_id}}/run", status_code=202)
    def run_lab_lesson(lesson_id: str) -> dict:
        return routes.run(lesson_id)
