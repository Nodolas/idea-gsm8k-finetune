"""The lab service routes of u11-finetune-lab, part S (US11.3; contract C8; NFR6).

Every test drives `gsm8k.service.app.create_app(results=..., finalists=..., outputs=...)` through
FastAPI's `TestClient` on temp folders (`tmp_project_dirs`); the lab files under `outputs/lab/` are
written by the test in their C8 shapes. Lessons come from part L's `gsm8k.lab.lessons.LESSONS` and
`gsm8k.lab.config` (`estimate_minutes`, `changes_text`), read here at call time to build the expected
answers. Nothing touches the project's outputs/ or results/.

Seams in `gsm8k.service.lab_routes`, read at call time:
- `launch(argv, log_path)` starts the lab command and returns its process: the real one returns the
  `subprocess.Popen`; the stub here returns a fake process with `pid` and `poll()` (None while it runs),
  so no real lab run starts. The service reaps its launched process with `poll()` (AC11.3.1).
- `send_signal(pid, sig)` sends a signal to a process; the stub records it and ends the fake run (its
  fake process ends and a held lab lock is released), so nothing real is signalled.

A lab run held by another process is simulated by this test holding an exclusive `flock` on
`outputs/lab/lab.lock` through its own file descriptor (flock locks belong to the open file, so the
service's own non-blocking try conflicts). Fake pids are above Linux's PID_MAX_LIMIT (4194304), so
they can never name a real process. The one real child (AC11.3.3, the launch itself) is a harmless
`python -c` that prints its environment and exits. The service modules are imported inside each test,
so a missing module fails each test alone.
"""

import fcntl
import json
import os
import signal
import sys
from pathlib import Path

import pytest

API = "/api/v1"
LAB_MODEL = {"name": "EleutherAI/pythia-31m", "weights": 30494720, "layers": 6, "device": "cpu"}
LESSON_IDS = [f"l{n:02d}" for n in range(1, 13)]
STALE_RUNNING_MESSAGE = "The lab run ended without a status."
FAKE_PID_BASE = 4194304 + 1000  # above PID_MAX_LIMIT: never a real process


# --- helpers ---------------------------------------------------------------------------------------


class FakeProcess:
    """A launched lab run as the stubbed `launch` returns it: running until `end()`."""

    def __init__(self, pid: int):
        self.pid = pid
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def end(self, code: int = 0) -> None:
        if self.returncode is None:
            self.returncode = code


class LabEnv:
    """The service under test on temp folders, with the stubbed launcher and signal sender."""

    def __init__(self, dirs, monkeypatch):
        from fastapi.testclient import TestClient

        from gsm8k.service import lab_routes  # the module under test (part S)
        from gsm8k.service.app import create_app

        self.dirs = dirs
        self.outputs: Path = dirs.outputs
        self.lab: Path = dirs.outputs / "lab"
        self.lab.mkdir(parents=True, exist_ok=True)
        self.launches: list[tuple[list, Path]] = []
        self.processes: list[FakeProcess] = []
        self.signals: list[tuple[int, int]] = []
        self.held_locks: dict[int, int] = {}  # fd -> pid written in the lock
        self.real_launch = lab_routes.launch
        monkeypatch.setattr(lab_routes, "launch", self._launch)
        monkeypatch.setattr(lab_routes, "send_signal", self._send_signal)
        app = create_app(
            results=dirs.results, finalists=dirs.results.parent / "finalists.json", outputs=dirs.outputs
        )
        self.client = TestClient(app)

    # stubs

    def _launch(self, argv, log_path):
        self.launches.append((argv, Path(log_path)))
        process = FakeProcess(FAKE_PID_BASE + len(self.processes))
        self.processes.append(process)
        return process

    def _send_signal(self, pid, sig):
        self.signals.append((pid, sig))
        for process in self.processes:
            if process.pid == pid:
                process.end(-int(sig))
        for fd, held_pid in list(self.held_locks.items()):
            if held_pid == pid:
                self.release_lock(fd)

    # a lab run held by another process

    def hold_lock(self, lesson: str, pid: int) -> int:
        path = self.lab / "lab.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        content = {"v": 1, "pid": pid, "lesson": lesson, "started_at": "2026-11-08T10:00:00Z"}
        os.ftruncate(fd, 0)
        os.pwrite(fd, (json.dumps(content) + "\n").encode("utf-8"), 0)
        self.held_locks[fd] = pid
        return fd

    def release_lock(self, fd: int) -> None:
        if self.held_locks.pop(fd, None) is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def close(self) -> None:
        for process in self.processes:
            process.end()
        for fd in list(self.held_locks):
            self.release_lock(fd)
        self.client.close()

    # lab files in their C8 shapes

    def write_status(self, lesson: str, state: str, **fields) -> dict:
        status = {
            "v": 1,
            "lesson": lesson,
            "state": state,
            "variant": None,
            "variants": [],
            "done": [],
            "pid": FAKE_PID_BASE + 999,
            "started_at": "2026-11-08T10:00:00Z",
            "ended_at": None if state == "running" else "2026-11-08T10:05:00Z",
            "message": None,
        }
        status.update(fields)
        folder = self.lab / lesson
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "status.json").write_text(json.dumps(status), encoding="utf-8")
        return status

    def write_metrics(self, lesson: str, variant: str, lines: list[dict], partial: str = "") -> None:
        folder = self.lab / lesson / variant
        folder.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(line) + "\n" for line in lines) + partial
        (folder / "metrics.jsonl").write_text(text, encoding="utf-8")

    def write_summary(self, lesson: str, variant: str, summary: dict) -> None:
        folder = self.lab / lesson / variant
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


@pytest.fixture
def lab_env(tmp_project_dirs, monkeypatch):
    """A factory: call it inside the test, so a missing module fails the test (not the fixture)."""
    made: list[LabEnv] = []

    def make() -> LabEnv:
        env = LabEnv(tmp_project_dirs, monkeypatch)
        made.append(env)
        return env

    yield make
    for env in made:
        env.close()


def _lessons():
    from gsm8k.lab.lessons import LESSONS

    return LESSONS


def _lesson(lesson_id: str):
    return next(lesson for lesson in _lessons() if lesson.id == lesson_id)


def _multi_variant_lesson():
    return next(lesson for lesson in _lessons() if len(lesson.variants) >= 2)


def _expected_info(lesson, state: str) -> dict:
    from gsm8k.lab.config import changes_text, estimate_minutes

    return {
        "id": lesson.id,
        "number": lesson.number,
        "title": lesson.title,
        "question": lesson.question,
        "watch": lesson.watch,
        "guess_prompt": lesson.guess_prompt,
        "guess_options": list(lesson.guess_options),
        "variants": [{"name": v.name, "label": v.label, "changes": changes_text(v)} for v in lesson.variants],
        "why": lesson.why,
        "big_run": lesson.big_run,
        "check": lesson.check,
        "estimate_minutes": estimate_minutes(lesson),
        "state": state,
    }


def _info_part(info: dict, expected: dict) -> dict:
    return {key: info.get(key) for key in expected}


def _lab_list(env: LabEnv) -> dict:
    response = env.client.get(f"{API}/lab")
    assert response.status_code == 200, response.text
    return response.json()


def _lesson_answer(env: LabEnv, lesson_id: str) -> dict:
    response = env.client.get(f"{API}/lab/{lesson_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _states(listing: dict) -> dict[str, str]:
    return {info["id"]: info["state"] for info in listing["lessons"]}


def _step_line(step: int, total: int, loss: float) -> dict:
    return {
        "v": 1,
        "step": step,
        "total_steps": total,
        "loss": loss,
        "learning_rate": 1e-4,
        "grad_norm": 0.5,
        "elapsed_s": float(step),
        "dev_loss": None,
    }


def _dev_line(step: int, total: int, dev_loss: float) -> dict:
    return {
        "v": 1,
        "step": step,
        "total_steps": total,
        "loss": None,
        "learning_rate": None,
        "grad_norm": None,
        "elapsed_s": float(step),
        "dev_loss": dev_loss,
    }


def _summary(lesson_id: str, variant) -> dict:
    return {
        "v": 1,
        "lesson": lesson_id,
        "variant": variant.name,
        "label": variant.label,
        "config": {"model": "EleutherAI/pythia-31m", "learning_rate": 1e-4},
        "trainable_params": 98304,
        "total_params": 30494720,
        "steps": 2,
        "seconds": 3.5,
        "seconds_per_step": 1.75,
        "tokenize_seconds": 0.4,
        "retokenize_seconds_per_step": None,
        "padding_fraction": 0.31,
        "peak_memory_mb": 412.0,
        "train_loss_first": 2.5,
        "train_loss_last": 1.9,
        "dev_loss_before": 2.6,
        "dev_loss_after": 2.1,
        "dev_loss_best": 2.1,
        "dev_loss_best_step": 2,
        "accuracy_before": 0.0,
        "accuracy_after": 0.05,
        "format_rate_before": 0.1,
        "format_rate_after": 0.9,
        "samples": [{"question": "1 + 1?", "gold": "2", "before": "3", "after": "#### 2"}],
    }


def _expected_argv(lesson_id: str) -> list[str]:
    return [sys.executable, "-m", "gsm8k", "lab", "run", lesson_id]


# --- AC11.3.1: the lesson list ------------------------------------------------------------------------


def test_AC11_3_1_lists_every_lesson_in_order_with_the_model_and_its_state(lab_env):
    env = lab_env()
    lessons = _lessons()
    env.write_status(lessons[0].id, "finished", done=[v.name for v in lessons[0].variants])
    env.write_status(lessons[1].id, "failed", message="Dev loss is not finite")
    env.write_status(lessons[2].id, "stopped", message="Stopped by SIGTERM")
    states = {lessons[0].id: "finished", lessons[1].id: "failed", lessons[2].id: "stopped"}

    listing = _lab_list(env)

    assert listing["model"] == LAB_MODEL
    assert listing["active"] is None
    assert [info["id"] for info in listing["lessons"]] == [lesson.id for lesson in lessons] == LESSON_IDS
    for info, lesson in zip(listing["lessons"], lessons, strict=True):
        expected = _expected_info(lesson, states.get(lesson.id, "not-run"))
        assert _info_part(info, expected) == expected, lesson.id


def test_AC11_3_1_active_is_the_lesson_whose_lab_lock_is_held(lab_env):
    env = lab_env()
    lesson_id = _lessons()[3].id
    fd = env.hold_lock(lesson_id, FAKE_PID_BASE + 500)

    listing = _lab_list(env)
    assert listing["active"] == lesson_id
    states = _states(listing)
    assert states[lesson_id] == "running"
    assert all(state == "not-run" for lid, state in states.items() if lid != lesson_id)

    env.release_lock(fd)  # the run ended; the lock file stays with its content but nobody holds it
    assert (env.lab / "lab.lock").exists()
    listing = _lab_list(env)
    assert listing["active"] is None
    assert _states(listing)[lesson_id] == "not-run"


def test_AC11_3_1_active_is_the_launched_lesson_while_its_process_has_not_ended(lab_env):
    env = lab_env()
    lesson_id = _lessons()[4].id
    response = env.client.post(f"{API}/lab/{lesson_id}/run")
    assert response.status_code == 202, response.text

    listing = _lab_list(env)  # no lock and no status file yet: only the launched process says so
    assert listing["active"] == lesson_id
    assert _states(listing)[lesson_id] == "running"

    env.processes[0].end(0)
    assert _lab_list(env)["active"] is None


# --- AC11.3.2: one lesson -----------------------------------------------------------------------------


def test_AC11_3_2_answers_the_lesson_its_status_and_per_variant_lines_and_summaries(lab_env):
    env = lab_env()
    lesson = _multi_variant_lesson()
    first, second = lesson.variants[0], lesson.variants[1]
    status = env.write_status(
        lesson.id,
        "failed",
        variant=second.name,
        variants=[first.name, second.name],
        done=[first.name],
        started_at="2026-11-08T10:00:00Z",
        ended_at="2026-11-08T10:07:30Z",
        message="Training loss is not finite",
    )
    first_lines = [_dev_line(0, 2, 2.6), _step_line(1, 2, 2.5), _step_line(2, 2, 1.9), _dev_line(2, 2, 2.1)]
    env.write_metrics(lesson.id, first.name, first_lines)
    summary = _summary(lesson.id, first)
    env.write_summary(lesson.id, first.name, summary)
    second_lines = [_dev_line(0, 2, 2.6)]
    env.write_metrics(lesson.id, second.name, second_lines, partial='{"v": 1, "step": 1, "total_st')

    answer = _lesson_answer(env, lesson.id)

    expected = _expected_info(lesson, "failed")
    assert _info_part(answer["lesson"], expected) == expected
    assert answer["status"] == {
        "state": "failed",
        "variant": second.name,
        "done": [first.name],
        "started_at": status["started_at"],
        "ended_at": status["ended_at"],
        "message": "Training loss is not finite",
    }
    results = {result["name"]: result for result in answer["results"]}
    assert [result["name"] for result in answer["results"]] == [v.name for v in lesson.variants]
    assert results[first.name] == {
        "name": first.name,
        "label": first.label,
        "lines": first_lines,
        "summary": summary,
    }
    assert results[second.name] == {  # the partial last line is not a line yet; no summary until it ends
        "name": second.name,
        "label": second.label,
        "lines": second_lines,
        "summary": None,
    }
    for variant in lesson.variants[2:]:
        assert results[variant.name] == {
            "name": variant.name,
            "label": variant.label,
            "lines": [],
            "summary": None,
        }


def test_AC11_3_2_a_lesson_never_run_reads_not_run_with_empty_results(lab_env):
    env = lab_env()
    lesson = _lessons()[0]

    answer = _lesson_answer(env, lesson.id)

    expected = _expected_info(lesson, "not-run")
    assert _info_part(answer["lesson"], expected) == expected
    assert answer["status"] == {
        "state": "not-run",
        "variant": None,
        "done": [],
        "started_at": None,
        "ended_at": None,
        "message": None,
    }
    assert answer["results"] == [
        {"name": v.name, "label": v.label, "lines": [], "summary": None} for v in lesson.variants
    ]


def test_AC11_3_2_the_active_lesson_reads_running_whatever_its_status_file_says(lab_env):
    env = lab_env()
    lesson = _multi_variant_lesson()
    env.write_status(lesson.id, "finished", done=[v.name for v in lesson.variants])  # an earlier run
    env.hold_lock(lesson.id, FAKE_PID_BASE + 501)

    answer = _lesson_answer(env, lesson.id)
    assert answer["status"]["state"] == "running"
    assert answer["lesson"]["state"] == "running"

    (env.lab / lesson.id / "status.json").unlink()  # right after the launch it may not be written yet
    answer = _lesson_answer(env, lesson.id)
    assert answer["status"]["state"] == "running"
    assert answer["lesson"]["state"] == "running"


def test_AC11_3_2_a_running_status_with_no_lab_run_going_reads_failed(lab_env):
    env = lab_env()
    lesson = _multi_variant_lesson()
    env.write_status(
        lesson.id,
        "running",
        variant=lesson.variants[0].name,
        variants=[v.name for v in lesson.variants],
        done=[],
    )

    answer = _lesson_answer(env, lesson.id)

    assert answer["status"]["state"] == "failed"
    assert answer["status"]["message"] == STALE_RUNNING_MESSAGE
    assert answer["lesson"]["state"] == "failed"


def test_AC11_3_2_an_unknown_lesson_is_not_found(lab_env):
    env = lab_env()

    response = env.client.get(f"{API}/lab/l99")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


# --- AC11.3.3: start a lesson -------------------------------------------------------------------------


def test_AC11_3_3_run_launches_the_lab_command_and_answers_202(lab_env):
    from gsm8k.run_records.lock import GpuLock

    env = lab_env()
    lesson_id = _lessons()[1].id
    gpu = GpuLock()
    gpu.acquire("q17-sft-dev-1", started_by="worker")  # a GPU run going plays no part
    try:
        response = env.client.post(f"{API}/lab/{lesson_id}/run")
    finally:
        gpu.release()

    assert response.status_code == 202, response.text
    assert response.json() == {"lesson": lesson_id, "state": "running"}
    assert len(env.launches) == 1
    argv, log_path = env.launches[0]
    assert isinstance(argv, list)
    assert argv == _expected_argv(lesson_id)
    assert log_path == env.outputs / "lab" / f"{lesson_id}.log"
    assert not (env.outputs / "queue").exists()  # the queue plays no part


def test_AC11_3_3_launch_runs_from_the_project_root_in_its_own_session_without_the_gpu(lab_env, monkeypatch):
    from gsm8k._env import ROOT

    env = lab_env()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setenv("GSM8K_LAB_TEST_MARKER", "passed-through")
    script = (
        "import json, os, sys; "
        "print(json.dumps({'cuda': os.environ.get('CUDA_VISIBLE_DEVICES'), 'cwd': os.getcwd(), "
        "'own_session': os.getsid(0) == os.getpid(), 'marker': os.environ.get('GSM8K_LAB_TEST_MARKER')}), "
        "flush=True); "
        "print('to-stderr', file=sys.stderr, flush=True)"
    )
    log_path = env.lab / "l01.log"
    log_path.write_text("earlier line\n", encoding="utf-8")

    process = env.real_launch([sys.executable, "-c", script], log_path)
    assert process.wait(timeout=60) == 0

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "earlier line"  # appended, not overwritten
    child = json.loads(lines[1])
    assert child["cuda"] == ""
    assert os.path.realpath(child["cwd"]) == os.path.realpath(ROOT)
    assert child["own_session"] is True
    assert child["marker"] == "passed-through"
    assert "to-stderr" in lines[2:]  # stderr goes to the same log


def test_AC11_3_3_run_while_a_lab_run_is_going_answers_lab_busy(lab_env):
    env = lab_env()
    a, b, c = (lesson.id for lesson in _lessons()[:3])

    fd = env.hold_lock(a, FAKE_PID_BASE + 502)
    response = env.client.post(f"{API}/lab/{b}/run")
    assert response.status_code == 409
    assert response.json()["error"] == "lab_busy"
    assert response.json()["message"] == f"A lab run is already active: {a}"
    assert env.launches == []
    env.release_lock(fd)

    assert env.client.post(f"{API}/lab/{b}/run").status_code == 202
    response = env.client.post(f"{API}/lab/{c}/run")  # b's launched process is still going
    assert response.status_code == 409
    assert response.json()["error"] == "lab_busy"
    assert response.json()["message"] == f"A lab run is already active: {b}"
    assert len(env.launches) == 1


def test_AC11_3_3_run_of_an_unknown_lesson_is_not_found(lab_env):
    env = lab_env()

    response = env.client.post(f"{API}/lab/l99/run")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert env.launches == []


# --- AC11.3.4: stop the lab run -----------------------------------------------------------------------


def test_AC11_3_4_stop_sends_sigterm_to_the_lab_lock_holder(lab_env):
    env = lab_env()
    lesson_id = _lessons()[5].id
    pid = FAKE_PID_BASE + 503
    env.hold_lock(lesson_id, pid)

    response = env.client.post(f"{API}/lab/stop")

    assert response.status_code == 200, response.text
    assert response.json()["lesson"] == lesson_id
    assert env.signals == [(pid, signal.SIGTERM)]


def test_AC11_3_4_stop_sends_sigterm_to_the_launched_process(lab_env):
    env = lab_env()
    lesson_id = _lessons()[6].id
    assert env.client.post(f"{API}/lab/{lesson_id}/run").status_code == 202
    pid = env.processes[0].pid

    response = env.client.post(f"{API}/lab/stop")

    assert response.status_code == 200, response.text
    assert response.json()["lesson"] == lesson_id
    assert env.signals == [(pid, signal.SIGTERM)]


def test_AC11_3_4_stop_with_no_lab_run_going_answers_no_lab_run(lab_env):
    env = lab_env()

    response = env.client.post(f"{API}/lab/stop")

    assert response.status_code == 409
    assert response.json()["error"] == "no_lab_run"
    assert env.signals == []
