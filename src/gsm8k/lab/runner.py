"""The lab run: the lab lock, the status file and the variants in order (US11.2, contract C8)."""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
import shutil
import signal
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gsm8k.lab import config as lab_config
from gsm8k.lab import trainer
from gsm8k.lab.lessons import Lesson

EXIT_FINISHED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3
EXIT_STOPPED = 130


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json_atomic(path: Path, data: Any) -> None:
    """Write to a temporary file in the same folder, then rename it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


class LabLockHeld(Exception):
    def __init__(self, lesson: str | None):
        self.lesson = lesson
        super().__init__(f"A lab run is already active: {lesson if lesson else 'unknown'}")


def read_lock(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class LabLock:
    """An exclusive non-blocking ``flock`` on ``<outputs>/lab/lab.lock``, held until ``release``."""

    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None

    def acquire(self, lesson: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            holder = read_lock(self.path)
            raise LabLockHeld(holder.get("lesson") if holder else None) from None
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        content = {"v": 1, "pid": os.getpid(), "lesson": lesson, "started_at": _now()}
        os.ftruncate(fd, 0)
        os.pwrite(fd, (json.dumps(content) + "\n").encode("utf-8"), 0)
        os.fsync(fd)

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            os.ftruncate(fd, 0)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def run_lesson(lesson: Lesson, variant_names: list[str], outputs: Path, threads: int | None = None) -> int:
    """Run the variants in order; returns the exit code (0 finished, 1 failed, 3 locked, 130 stopped).

    The caller has already checked the lesson and variants. Order: lock (3), then the lesson's earlier
    folder is removed, then the run starts.
    """
    import torch

    lab_dir = Path(outputs) / "lab"
    lock = LabLock(lab_dir / "lab.lock")
    try:
        lock.acquire(lesson.id)
    except LabLockHeld as exc:
        print(str(exc))
        return EXIT_LOCKED

    stop_flag = {"stop": False}
    previous = signal.signal(signal.SIGTERM, lambda signum, frame: stop_flag.update(stop=True))

    def stop_check() -> None:
        if stop_flag["stop"]:
            raise trainer.Stopped()

    lesson_dir = lab_dir / lesson.id
    status: dict[str, Any] = {}
    try:
        shutil.rmtree(lesson_dir, ignore_errors=True)
        lesson_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "v": 1,
            "lesson": lesson.id,
            "state": "running",
            "variant": None,
            "variants": list(variant_names),
            "done": [],
            "pid": os.getpid(),
            "started_at": _now(),
            "ended_at": None,
            "message": None,
        }
        status_path = lesson_dir / "status.json"
        write_json_atomic(status_path, status)
        try:
            by_name = {v.name: v for v in lesson.variants}
            configs = {}
            for name in variant_names:
                cfg = lab_config.config_for(lesson.id, name)
                configs[name] = dataclasses.replace(cfg, threads=threads) if threads else cfg
            for cfg in configs.values():
                cfg.validate()
            first = configs[variant_names[0]]
            torch.set_num_threads(first.threads)
            os.nice(10)
            for name in variant_names:
                status["variant"] = name
                write_json_atomic(status_path, status)
                summary = trainer.run_variant(
                    lesson.id, name, by_name[name].label, configs[name], lesson_dir / name, stop_check
                )
                write_json_atomic(lesson_dir / name / "summary.json", summary)
                status["done"].append(name)
                write_json_atomic(status_path, status)
            status.update(state="finished", variant=None, ended_at=_now())
            code = EXIT_FINISHED
        except trainer.Stopped:
            status.update(state="stopped", ended_at=_now())
            code = EXIT_STOPPED
        except Exception as exc:
            traceback.print_exc()
            status.update(state="failed", message=str(exc) or exc.__class__.__name__, ended_at=_now())
            code = EXIT_FAILED
        write_json_atomic(status_path, status)
        return code
    finally:
        signal.signal(signal.SIGTERM, previous)
        lock.release()
