"""The course service routes of u12-learning-course, part S (US12.3; contract C9; NFR6, NFR8).

Every test drives `gsm8k.service.app.create_app(results=..., finalists=..., outputs=...)` through FastAPI's
`TestClient` on temp folders (`tmp_project_dirs`). The course files under `outputs/course/` (`runs.csv` in
the C1 format, `architectures.json`, `progress.json`) and the lab files under `outputs/lab/` are written by
the test in their C9 and C8 shapes. The queue is the real `gsm8k.run_control.queue` on the temp outputs
folder (entries are read back from disk); the GPU lock is simulated by the test holding an exclusive `flock`
on `outputs/run.lock` through its own file descriptor. Steps, run specs and configurations come from part D
(`gsm8k.course.steps`, `gsm8k.course.configs`), read inside each test so a missing module fails that test.

Seam in `gsm8k.service.course_routes`, read at call time:
- `launch(argv, log_path, env) -> pid` starts the model-design inspection (an `inspect` step's run); the
  stub here records the call and returns a fake pid above Linux's PID_MAX_LIMIT, so no process starts.

Nothing here touches the project's outputs/, checkpoints/ or results/runs.csv.
"""

import fcntl
import json
import math
import os
import sys
from pathlib import Path

import pytest

API = "/api/v1"
FAKE_PID = 4194304 + 2000  # above PID_MAX_LIMIT: never a real process
COURSE_RESULTS = "outputs/course/runs.csv"
BASE_06 = "Qwen/Qwen3-0.6B-Base"
GB_UNITS = (1e9, 2**30)  # the unit of "GB" is not fixed by the spec: both readings are accepted
CARD_GB = 6.5

# Fixture model designs (C9 fields used by the memory table); weights are the Course Models table's.
DESIGNS = {
    "EleutherAI/pythia-31m": dict(
        family="gpt_neox",
        layers=6,
        width=256,
        heads=8,
        kv_heads=8,
        head_size=32,
        mlp_width=1024,
        mlp_matrices=2,
        vocab=50304,
        context=2048,
        tied=False,
        position="rotary",
        total=30_494_720,
    ),
    "HuggingFaceTB/SmolLM2-360M": dict(
        family="llama",
        layers=32,
        width=960,
        heads=15,
        kv_heads=5,
        head_size=64,
        mlp_width=2560,
        mlp_matrices=3,
        vocab=49152,
        context=8192,
        tied=True,
        position="rotary",
        total=361_821_120,
    ),
    "Qwen/Qwen2.5-0.5B": dict(
        family="qwen2",
        layers=24,
        width=896,
        heads=14,
        kv_heads=2,
        head_size=64,
        mlp_width=4864,
        mlp_matrices=3,
        vocab=151936,
        context=32768,
        tied=True,
        position="rotary",
        total=494_032_768,
    ),
    "Qwen/Qwen3-0.6B-Base": dict(
        family="qwen3",
        layers=28,
        width=1024,
        heads=16,
        kv_heads=8,
        head_size=128,
        mlp_width=3072,
        mlp_matrices=3,
        vocab=151936,
        context=32768,
        tied=True,
        position="rotary",
        total=596_049_920,
    ),
    "Qwen/Qwen3-1.7B-Base": dict(
        family="qwen3",
        layers=28,
        width=2048,
        heads=16,
        kv_heads=8,
        head_size=128,
        mlp_width=6144,
        mlp_matrices=3,
        vocab=151936,
        context=32768,
        tied=True,
        position="rotary",
        total=1_720_574_976,
    ),
}


# --- helpers ---------------------------------------------------------------------------------------


class CourseEnv:
    """The service under test on temp folders, with the stubbed inspection launcher."""

    def __init__(self, dirs, monkeypatch):
        from fastapi.testclient import TestClient

        from gsm8k.service import course_routes  # the module under test (part S)
        from gsm8k.service.app import create_app

        self.dirs = dirs
        self.outputs: Path = dirs.outputs
        self.checkpoints: Path = dirs.checkpoints
        self.course: Path = dirs.outputs / "course"
        self.course.mkdir(parents=True, exist_ok=True)
        self.launches: list[tuple[list, Path, dict]] = []
        self.lock_fds: list[int] = []
        monkeypatch.setattr(course_routes, "launch", self._launch)
        app = create_app(
            results=dirs.results, finalists=dirs.results.parent / "finalists.json", outputs=dirs.outputs
        )
        self.client = TestClient(app)

    def _launch(self, argv, log_path, env):
        self.launches.append((list(argv), Path(log_path), dict(env)))
        return FAKE_PID

    def close(self) -> None:
        for fd in self.lock_fds:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass
        self.client.close()

    # requests

    def get(self, path: str):
        return self.client.get(f"{API}{path}")

    def post(self, path: str, body=None):
        return (
            self.client.post(f"{API}{path}", json=body)
            if body is not None
            else self.client.post(f"{API}{path}")
        )

    def overview(self) -> dict:
        response = self.get("/course")
        assert response.status_code == 200, response.text
        return response.json()

    def step(self, step_id: str) -> dict:
        response = self.get(f"/course/{step_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def queue_ids(self) -> list[str]:
        from gsm8k.run_control import queue

        return [entry.attempt_id for entry in queue.list_queue(self.outputs)]

    # course files

    def write_row(
        self,
        attempt_id: str,
        model: str,
        method: str,
        value: float,
        minutes: float = 3.0,
        *,
        data: str = "gsm8k-dev",
        metric: str = "accuracy",
    ) -> None:
        from gsm8k.run_records.log import RunRow, append_row

        append_row(
            self.course / "runs.csv",
            RunRow("2026-11-09T10:00:00Z", attempt_id, model, method, data, metric, value, minutes, "0" * 64),
        )

    def write_run_folder(self, attempt_id: str, status: str | None) -> Path:
        folder = self.outputs / attempt_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "config.json").write_text(json.dumps({"v": 1, "run_id": attempt_id}), encoding="utf-8")
        if status is not None:
            (folder / "status.json").write_text(
                json.dumps(
                    {
                        "v": 1,
                        "run_id": attempt_id,
                        "status": status,
                        "exit_code": 0 if status == "finished" else 1,
                        "reason": None,
                        "ended_at": "2026-11-09T10:05:00Z",
                    }
                ),
                encoding="utf-8",
            )
        return folder

    def hold_gpu_lock(self, run_id: str) -> None:
        fd = os.open(self.outputs / "run.lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        content = {"v": 1, "run_id": run_id, "pid": FAKE_PID, "started_at": "2026-11-09T10:00:00Z"}
        os.ftruncate(fd, 0)
        os.pwrite(fd, (json.dumps(content) + "\n").encode("utf-8"), 0)
        self.lock_fds.append(fd)

    def write_lab_status(self, lesson: str, state: str) -> None:
        folder = self.outputs / "lab" / lesson
        folder.mkdir(parents=True, exist_ok=True)
        status = {
            "v": 1,
            "lesson": lesson,
            "state": state,
            "variant": None,
            "variants": [],
            "done": [],
            "pid": FAKE_PID,
            "started_at": "2026-11-08T10:00:00Z",
            "ended_at": "2026-11-08T10:05:00Z",
            "message": None,
        }
        (folder / "status.json").write_text(json.dumps(status), encoding="utf-8")

    def write_architectures(self) -> dict:
        data = architectures_fixture()
        (self.course / "architectures.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    @property
    def progress_path(self) -> Path:
        return self.course / "progress.json"

    def write_progress(self, steps: dict) -> None:
        self.progress_path.write_text(json.dumps({"v": 1, "steps": steps}), encoding="utf-8")

    def progress(self) -> dict:
        return json.loads(self.progress_path.read_text(encoding="utf-8"))


@pytest.fixture
def course_env(tmp_project_dirs, monkeypatch):
    """A factory: call it inside the test, so a missing module fails the test (not the fixture)."""
    made: list[CourseEnv] = []

    def make() -> CourseEnv:
        env = CourseEnv(tmp_project_dirs, monkeypatch)
        made.append(env)
        return env

    yield make
    for env in made:
        env.close()


def architectures_fixture() -> dict:
    from gsm8k.course.steps import COURSE_MODELS

    models = []
    for model in COURSE_MODELS:
        d = DESIGNS[model.id]
        total = d["total"]
        embeddings = d["vocab"] * d["width"]
        norms = d["layers"] * 2 * d["width"] + d["width"]
        attention = (
            d["layers"] * d["width"] * (2 * d["heads"] * d["head_size"] + 2 * d["kv_heads"] * d["head_size"])
        )
        head = 0 if d["tied"] else d["vocab"] * d["width"]
        mlp = total - embeddings - norms - attention - head
        models.append(
            {
                "id": model.id,
                "revision": model.revision,
                "licence": "Apache-2.0",
                "family": d["family"],
                "layers": d["layers"],
                "width": d["width"],
                "heads": d["heads"],
                "kv_heads": d["kv_heads"],
                "attention": "multi-head" if d["heads"] == d["kv_heads"] else "grouped-query",
                "head_size": d["head_size"],
                "mlp_width": d["mlp_width"],
                "mlp_matrices": d["mlp_matrices"],
                "vocab": d["vocab"],
                "context": d["context"],
                "tied_embeddings": d["tied"],
                "position_encoding": d["position"],
                "activation": "silu",
                "weights_total": total,
                "weights_by_part": {
                    "embeddings": embeddings,
                    "attention": attention,
                    "mlp": mlp,
                    "norms": norms,
                    "head": head,
                },
                "bf16_gb": round(total * 2 / 1e9, 2),
                "int4_gb": round(total * 0.5 / 1e9, 2),
                "problem_tokens": 60,
                "prompt_tokens": 900,
                "first_tokens": [f"t{i}" for i in range(20)],
            }
        )
    return {"v": 1, "generated_at": "2026-11-09T09:00:00Z", "sample_problem_id": "dev-0001", "models": models}


def adapter_weights(design: dict) -> int:
    """LoRA adapter weights at rank 16 on every linear layer of the decoder blocks: q, k, v, o and the
    MLP matrices, each rank x (in + out)."""
    rank = 16
    width = design["width"]
    q_out = design["heads"] * design["head_size"]
    kv_out = design["kv_heads"] * design["head_size"]
    per_layer = (
        (width + q_out)  # q
        + 2 * (width + kv_out)  # k, v
        + (q_out + width)  # o
        + design["mlp_matrices"] * (width + design["mlp_width"])  # gate/up/down or up/down
    )
    return rank * per_layer * design["layers"]


def expected_bytes(design: dict) -> dict[str, float]:
    total = design["total"]
    adapter = adapter_weights(design)
    return {
        "full": total * 16.0,
        "lora": total * 2.0 + adapter * 16.0,
        "qlora": total * 0.55 + adapter * 16.0,
    }


def gb_matches(actual, bytes_: float) -> bool:
    return actual is not None and any(
        actual == pytest.approx(bytes_ / unit, rel=0.02, abs=0.011) for unit in GB_UNITS
    )


def wrong_answers(step) -> list[int]:
    return [(q.right + 1) % len(q.options) for q in step.questions]


def right_answers(step) -> list[int]:
    return [q.right for q in step.questions]


def interval(p: float, n: int = 100) -> tuple[float, float]:
    half = 1.96 * math.sqrt(p * (1 - p) / n)
    return max(0.0, p - half), min(1.0, p + half)


def attempt(step, answers: list[int]) -> dict:
    return {
        "answers": answers,
        "right": [a == q.right for a, q in zip(answers, step.questions, strict=True)],
        "at": "2026-11-09T09:30:00Z",
    }


def quiz_state(step, attempts: list[list[int]], passed: bool) -> dict:
    return {
        "opened_at": "2026-11-09T09:00:00Z",
        "quiz": {
            "attempts": [attempt(step, answers) for answers in attempts],
            "passed_at": "2026-11-09T09:31:00Z" if passed else None,
        },
        "own_words": None,
    }


def passed_quiz(step_id: str) -> dict:
    from gsm8k.course.steps import get_step

    step = get_step(step_id)
    return quiz_state(step, [right_answers(step)], True)


def summaries(overview: dict) -> dict[str, dict]:
    return {s["id"]: s for part in overview["parts"] for s in part["steps"]}


# --- AC12.3.1: the overview ----------------------------------------------------------------------------


def test_AC12_3_1_overview_lists_the_parts_and_24_steps_in_order(course_env):
    from gsm8k.course.steps import PARTS, STEPS

    env = course_env()
    overview = env.overview()

    assert overview["v"] == 1
    assert [(p["number"], p["title"]) for p in overview["parts"]] == [tuple(p) for p in PARTS]
    listed = [s for part in overview["parts"] for s in part["steps"]]
    assert [s["id"] for s in listed] == [step.id for step in STEPS] == [f"c{n:02d}" for n in range(1, 25)]
    for item, step in zip(listed, STEPS, strict=True):
        assert (item["number"], item["part"], item["title"], item["kind"]) == (
            step.number,
            step.part,
            step.title,
            step.kind,
        )
    for part in overview["parts"]:
        assert part["total"] == len(part["steps"])
    assert sum(part["total"] for part in overview["parts"]) == 24


def test_AC12_3_1_fresh_course_has_no_progress_and_the_first_step_is_next(course_env):
    env = course_env()
    overview = env.overview()

    assert overview["progress"] == {
        "done": 0,
        "total": 24,
        "percent": 0,
        "first_try_right": 0,
        "questions_answered": 0,
    }
    assert overview["next_step"] == "c01"
    by_id = summaries(overview)
    for step_id, item in by_id.items():
        if item["kind"] != "read":
            assert item["state"] == "not-started", step_id
            assert item["run_done"] is False, step_id
        else:
            assert item["run_done"] is True, step_id  # a read step's run part is always done
        assert item["quiz_passed"] is False, step_id
    assert not env.progress_path.exists()  # reading creates nothing


def test_AC12_3_1_step_states_follow_the_run_part_the_quiz_and_opening(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.5)  # run part done, quiz not passed
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.02)  # 1 of 4 runs
    env.write_architectures()  # c02, c03, c04 run parts done
    env.write_lab_status("l01", "finished")  # c07
    env.write_progress(
        {
            "c02": {
                "opened_at": "2026-11-09T09:00:00Z",
                "quiz": {"attempts": [], "passed_at": None},
                "own_words": None,
            },
            "c06": passed_quiz("c06"),
            "c04": quiz_state(get_step("c04"), [right_answers(get_step("c04"))], True),
            "c08": {
                "opened_at": "2026-11-09T09:00:00Z",
                "quiz": {"attempts": [], "passed_at": None},
                "own_words": None,
            },
        }
    )

    by_id = summaries(env.overview())

    assert (by_id["c01"]["run_done"], by_id["c01"]["quiz_passed"], by_id["c01"]["state"]) == (
        True,
        False,
        "in-progress",
    )
    assert (by_id["c05"]["run_done"], by_id["c05"]["state"]) == (
        False,
        "in-progress",
    )  # its run part has started
    assert (by_id["c02"]["run_done"], by_id["c02"]["state"]) == (True, "in-progress")  # opened, not passed
    assert (by_id["c03"]["run_done"], by_id["c03"]["state"]) == (True, "in-progress")  # file exists
    assert (by_id["c04"]["run_done"], by_id["c04"]["quiz_passed"], by_id["c04"]["state"]) == (
        True,
        True,
        "done",
    )
    assert (by_id["c06"]["run_done"], by_id["c06"]["quiz_passed"], by_id["c06"]["state"]) == (
        True,
        True,
        "done",
    )
    assert (by_id["c07"]["run_done"], by_id["c07"]["state"]) == (True, "in-progress")  # lesson finished
    assert (by_id["c08"]["run_done"], by_id["c08"]["state"]) == (False, "in-progress")  # opened only
    assert by_id["c09"]["state"] == "not-started"
    assert by_id["c20"]["state"] == "not-started"


def test_AC12_3_1_progress_counts_done_steps_with_percent_rounded_down_and_the_next_step(course_env):
    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.5)
    env.write_lab_status("l01", "finished")
    env.write_progress({sid: passed_quiz(sid) for sid in ("c01", "c06", "c07", "c19", "c24")})

    overview = env.overview()

    progress = overview["progress"]
    assert (progress["done"], progress["total"]) == (5, 24)
    assert progress["percent"] == 20  # 5 / 24 = 20.8 %, rounded down
    assert overview["next_step"] == "c02"  # the first step that is not done
    done_by_part = {p["number"]: (p["done"], p["total"]) for p in overview["parts"]}
    assert done_by_part == {1: (1, 1), 2: (1, 5), 3: (1, 12), 4: (1, 2), 5: (1, 4)}


def test_AC12_3_1_first_try_counts_use_only_each_questions_first_attempt(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    c01, c06, c19 = get_step("c01"), get_step("c06"), get_step("c19")
    wrong_one = right_answers(c06)
    wrong_one[0] = (wrong_one[0] + 1) % len(c06.questions[0].options)
    env.write_progress(
        {
            "c01": quiz_state(c01, [right_answers(c01)], True),
            "c06": quiz_state(c06, [wrong_one, right_answers(c06)], True),  # second attempt all right
            "c19": quiz_state(c19, [wrong_answers(c19), wrong_answers(c19)], False),
        }
    )

    progress = env.overview()["progress"]

    assert progress["first_try_right"] == len(c01.questions) + (len(c06.questions) - 1)
    assert progress["questions_answered"] == len(c01.questions) + len(c06.questions) + len(c19.questions)


def test_AC12_3_1_finished_course_has_all_steps_done_and_no_next_step(course_env):
    from gsm8k.course.steps import COURSE_RUNS, STEPS

    env = course_env()
    env.write_architectures()
    steps = {}
    for step in STEPS:
        steps[step.id] = passed_quiz(step.id)
        if step.kind == "lab":
            env.write_lab_status(step.lesson, "finished")
    for spec in COURSE_RUNS:
        attempt_id = f"course-{spec.step}-{spec.run}-1"
        if spec.run == "cotgen":
            env.write_row(attempt_id, spec.model, "cotgen", 0.7, data="gsm8k-train", metric="kept_fraction")
        else:
            env.write_row(attempt_id, spec.model, spec.changes.get("method", "base"), 0.5)
    env.write_progress(steps)

    overview = env.overview()

    assert overview["progress"]["done"] == 24
    assert overview["progress"]["percent"] == 100
    assert overview["next_step"] is None
    assert all(item["state"] == "done" for item in summaries(overview).values())


# --- AC12.3.2: one step ----------------------------------------------------------------------------------


def test_AC12_3_2_step_answer_carries_the_content_and_hides_what_is_not_earned_yet(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")

    answer = env.step("c01")

    assert answer["v"] == 1
    assert answer["step"]["id"] == "c01" and answer["step"]["kind"] == "gpu"
    assert answer["part_title"] == step.part_title
    assert (answer["why"], answer["body"], answer["own_words_prompt"]) == (
        step.why,
        step.body,
        step.own_words_prompt,
    )
    assert len(answer["questions"]) == len(step.questions)
    for shown, question in zip(answer["questions"], step.questions, strict=True):
        assert shown["prompt"] == question.prompt
        assert shown["options"] == list(question.options)
        assert shown["answered"] is False
        assert shown["right"] is None
        assert shown["explanation"] is None
    assert answer["own_words"] is None
    assert answer["model_answer"] is None
    assert answer.get("notice") is None
    for question in step.questions:  # nothing leaks through another field
        assert question.explanation not in env.client.get(f"{API}/course/c01").text
    assert step.model_answer not in env.client.get(f"{API}/course/c01").text


def test_AC12_3_2_right_option_and_explanation_appear_once_the_question_is_answered(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")
    response = env.post("/course/c01/quiz", {"answers": wrong_answers(step)})
    assert response.status_code == 200, response.text

    answer = env.step("c01")

    for shown, question in zip(answer["questions"], step.questions, strict=True):
        assert shown["answered"] is True
        assert shown["right"] == question.right
        assert shown["explanation"] == question.explanation


def test_AC12_3_2_model_answer_appears_only_once_own_words_are_saved(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c06")
    assert env.step("c06")["model_answer"] is None

    saved = env.client.put(
        f"{API}/course/c06/own-words", json={"text": "Because it fits and has room to improve."}
    )
    assert saved.status_code == 200, saved.text
    answer = env.step("c06")

    assert answer["own_words"] == "Because it fits and has room to improve."
    assert answer["model_answer"] == step.model_answer


def test_AC12_3_2_gpu_step_lists_each_run_with_its_spec_estimate_and_not_run_state(course_env):
    from gsm8k.course.configs import estimate_minutes
    from gsm8k.course.steps import COURSE_RUNS

    env = course_env()

    answer = env.step("c05")

    specs = [spec for spec in COURSE_RUNS if spec.step == "c05"]
    assert (
        [run["run"] for run in answer["runs"]]
        == [spec.run for spec in specs]
        == [
            "pythia",
            "smollm2",
            "qwen25",
            "qwen3-17",
        ]
    )
    for run, spec in zip(answer["runs"], specs, strict=True):
        minutes, measured = estimate_minutes("c05", spec.run, env.outputs)
        assert (run["command"], run["model"], run["changes"]) == (spec.command, spec.model, spec.changes_text)
        assert (run["estimate_minutes"], run["estimate_measured"]) == (minutes, measured)
        assert run["state"] == "not-run"
        assert run["attempt_id"] is None
        assert run["accuracy"] is None and run["minutes"] is None and run["value"] is None


def test_AC12_3_2_run_states_come_from_the_queue_the_run_folder_the_lock_and_the_rows(course_env):
    from gsm8k.run_control import queue

    env = course_env()
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.03, 1.5)  # finished: a row
    env.write_run_folder("course-c05-smollm2-1", "failed")
    env.write_run_folder("course-c05-qwen25-1", "stopped")
    queue.add("q06-sft-dev-1", {"v": 1, "run_id": "q06-sft-dev-1"}, outputs=env.outputs)  # unrelated entry

    runs = {run["run"]: run for run in env.step("c05")["runs"]}

    assert runs["pythia"]["state"] == "finished"
    assert runs["pythia"]["attempt_id"] == "course-c05-pythia-1"
    assert runs["pythia"]["accuracy"] == pytest.approx(0.03)
    assert runs["pythia"]["value"] == pytest.approx(0.03)
    assert runs["pythia"]["metric"] == "accuracy"
    assert runs["pythia"]["minutes"] == pytest.approx(1.5)
    low, high = interval(0.03)
    assert runs["pythia"]["interval_low"] == pytest.approx(low, abs=1e-3)
    assert runs["pythia"]["interval_high"] == pytest.approx(high, abs=1e-3)
    assert (runs["smollm2"]["state"], runs["smollm2"]["attempt_id"]) == ("failed", "course-c05-smollm2-1")
    assert (runs["qwen25"]["state"], runs["qwen25"]["attempt_id"]) == ("stopped", "course-c05-qwen25-1")
    assert runs["smollm2"]["accuracy"] is None and runs["qwen25"]["accuracy"] is None
    assert (runs["qwen3-17"]["state"], runs["qwen3-17"]["attempt_id"]) == ("not-run", None)


def test_AC12_3_2_a_queued_run_reads_queued_and_the_run_holding_the_gpu_reads_running(course_env):
    env = course_env()
    queued = env.post("/course/c01/run")
    assert queued.status_code == 202, queued.text

    run = env.step("c01")["runs"][0]
    assert (run["state"], run["attempt_id"]) == ("queued", "course-c01-base-06-1")

    from gsm8k.run_control import queue

    queue.remove("course-c01-base-06-1", outputs=env.outputs)  # the worker launched it: the lock names it now
    env.write_run_folder("course-c01-base-06-1", None)
    env.hold_gpu_lock("course-c01-base-06-1")
    run = env.step("c01")["runs"][0]
    assert (run["state"], run["attempt_id"]) == ("running", "course-c01-base-06-1")


def test_AC12_3_2_the_latest_attempt_is_the_one_shown(course_env):
    env = course_env()
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.03)
    env.write_run_folder("course-c05-pythia-2", "failed")

    run = {r["run"]: r for r in env.step("c05")["runs"]}["pythia"]

    assert (run["attempt_id"], run["state"]) == ("course-c05-pythia-2", "failed")


def test_AC12_3_2_inspect_step_carries_the_architectures_file_once_it_exists(course_env):
    env = course_env()
    for step_id in ("c02", "c03", "c04"):
        answer = env.step(step_id)
        assert answer["architectures"] is None
        assert answer["runs"] == []

    data = env.write_architectures()

    for step_id in ("c02", "c03", "c04"):
        answer = env.step(step_id)
        assert answer["architectures"]["models"] == data["models"]
        assert answer["architectures"]["sample_problem_id"] == data["sample_problem_id"]


def test_AC12_3_2_lab_step_carries_its_lesson_and_the_lessons_state(course_env):
    from gsm8k.course.steps import get_step
    from gsm8k.lab.lessons import LESSONS

    env = course_env()
    step = get_step("c07")
    lesson = next(lesson for lesson in LESSONS if lesson.id == step.lesson)

    answer = env.step("c07")
    assert answer["lesson"] == {
        "id": lesson.id,
        "number": lesson.number,
        "title": lesson.title,
        "question": lesson.question,
        "state": "not-run",
    }
    assert answer["runs"] == []

    env.write_lab_status(lesson.id, "finished")
    answer = env.step("c07")
    assert answer["lesson"]["state"] == "finished"
    assert answer["step"]["run_done"] is True


def test_AC12_3_2_unknown_step_answers_404_not_found_on_every_route(course_env):
    env = course_env()

    responses = [
        env.get("/course/c99"),
        env.post("/course/c99/run"),
        env.post("/course/c99/quiz", {"answers": [0]}),
        env.client.put(f"{API}/course/c99/own-words", json={"text": "x"}),
        env.post("/course/c99/open"),
    ]

    for response in responses:
        assert response.status_code == 404, response.text
        assert response.json()["error"] == "not_found"


# --- AC12.3.3: running a step ------------------------------------------------------------------------------


def test_AC12_3_3_run_queues_the_runs_in_table_order_with_results_and_answers_202(course_env):
    from gsm8k import run_config
    from gsm8k.course.steps import COURSE_RUNS
    from gsm8k.run_control import queue

    env = course_env()

    response = env.post("/course/c05/run")

    assert response.status_code == 202, response.text
    specs = [spec for spec in COURSE_RUNS if spec.step == "c05"]
    expected_ids = [f"course-c05-{spec.run}-1" for spec in specs]
    assert response.json() == {"step": "c05", "attempt_ids": expected_ids}
    entries = queue.list_queue(env.outputs)
    assert [entry.attempt_id for entry in entries] == expected_ids
    for entry, spec in zip(entries, specs, strict=True):
        assert entry.results == COURSE_RESULTS
        assert entry.after is None
        assert entry.config["run_id"] == entry.attempt_id
        assert entry.config["model"] == spec.model
        assert entry.config["method"] == "base"
        assert entry.config["limit"] == 100 and entry.config["split"] == "dev" and entry.config["seed"] == 42
        run_config.validate(run_config.from_dict(entry.config))  # C2-valid
    assert not env.dirs.results.exists()  # results/runs.csv is never touched


def test_AC12_3_3_attempt_ids_count_up_from_the_rows_folders_and_queue(course_env):
    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.5)
    env.write_run_folder("course-c01-base-06-2", "failed")

    response = env.post("/course/c01/run")

    assert response.status_code == 202, response.text
    assert response.json()["attempt_ids"] == ["course-c01-base-06-3"]


def test_AC12_3_3_c22_queues_cotgen_then_selfcot_waiting_for_it(course_env):
    from gsm8k import run_config
    from gsm8k.run_control import queue

    env = course_env()

    response = env.post("/course/c22/run")

    assert response.status_code == 202, response.text
    assert response.json()["attempt_ids"] == ["course-c22-cotgen-1", "course-c22-selfcot-1"]
    cotgen, selfcot = queue.list_queue(env.outputs)
    assert (cotgen.attempt_id, selfcot.attempt_id) == ("course-c22-cotgen-1", "course-c22-selfcot-1")
    assert cotgen.results == selfcot.results == COURSE_RESULTS
    assert cotgen.after is None
    assert selfcot.after == "course-c22-cotgen-1"
    assert cotgen.config["method"] == "cotgen" and cotgen.config["split"] == "train"
    assert cotgen.config["cot_problems"] == 100 and cotgen.config["cot_samples"] == 4
    assert cotgen.config["limit"] is None
    assert selfcot.config["method"] == "selfcot"
    assert selfcot.config["train_examples"] == 100
    assert selfcot.config["cot_data_run"] == "course-c22-cotgen-1"
    for entry in (cotgen, selfcot):
        run_config.validate(run_config.from_dict(entry.config))


def test_AC12_3_3_queue_full_adds_none_of_the_runs(course_env):
    from gsm8k.run_control import queue

    env = course_env()
    for n in range(1, 10):  # 9 waiting: one place left, c05 needs four
        queue.add(f"q06-sft-dev-{n}", {"v": 1, "run_id": f"q06-sft-dev-{n}"}, outputs=env.outputs)
    before = env.queue_ids()
    assert len(before) == 9

    response = env.post("/course/c05/run")

    assert response.status_code == 409, response.text
    assert response.json()["error"] == "queue_full"
    assert response.json()["message"] == queue.QUEUE_FULL_MESSAGE
    assert env.queue_ids() == before  # all or none


def test_AC12_3_3_the_runs_fit_exactly_when_ten_places_are_taken(course_env):
    from gsm8k.run_control import queue

    env = course_env()
    for n in range(1, 7):  # 6 waiting + 4 runs = 10
        queue.add(f"q06-sft-dev-{n}", {"v": 1, "run_id": f"q06-sft-dev-{n}"}, outputs=env.outputs)

    response = env.post("/course/c05/run")

    assert response.status_code == 202, response.text
    assert len(env.queue_ids()) == 10


def test_AC12_3_3_a_step_with_a_run_queued_or_running_answers_409_course_busy(course_env):
    env = course_env()
    assert env.post("/course/c01/run").status_code == 202

    again = env.post("/course/c01/run")

    assert again.status_code == 409, again.text
    assert again.json()["error"] == "course_busy"
    assert again.json()["message"] == "A run of this step is already queued or running: course-c01-base-06-1"
    assert env.queue_ids() == ["course-c01-base-06-1"]
    other = env.post("/course/c05/run")  # another step is not busy
    assert other.status_code == 202, other.text


def test_AC12_3_3_one_queued_run_of_a_step_makes_the_whole_step_busy(course_env):
    from gsm8k.run_control import queue

    env = course_env()
    queue.add(
        "course-c05-qwen25-1",
        {"v": 1, "run_id": "course-c05-qwen25-1"},
        outputs=env.outputs,
        results=COURSE_RESULTS,
    )

    response = env.post("/course/c05/run")

    assert response.status_code == 409, response.text
    assert response.json()["error"] == "course_busy"
    assert "course-c05-qwen25-1" in response.json()["message"]
    assert env.queue_ids() == ["course-c05-qwen25-1"]


def test_AC12_3_3_a_run_holding_the_gpu_makes_its_step_busy(course_env):
    env = course_env()
    env.write_run_folder("course-c01-base-06-1", None)
    env.hold_gpu_lock("course-c01-base-06-1")

    response = env.post("/course/c01/run")

    assert response.status_code == 409, response.text
    assert response.json()["error"] == "course_busy"
    assert (
        response.json()["message"] == "A run of this step is already queued or running: course-c01-base-06-1"
    )


@pytest.mark.parametrize("step_id", ["c02", "c03", "c04"])
def test_AC12_3_3_inspect_step_launches_the_inspection_as_an_argument_list_on_the_cpu(course_env, step_id):
    env = course_env()

    response = env.post(f"/course/{step_id}/run")

    assert response.status_code == 202, response.text
    assert len(env.launches) == 1
    argv, log_path, child_env = env.launches[0]
    assert argv == [sys.executable, "-m", "gsm8k", "course", "inspect"]
    assert log_path == env.outputs / "course" / "inspect.log"
    assert child_env["CUDA_VISIBLE_DEVICES"] == ""
    assert env.queue_ids() == []  # no queue entry: the CPU inspection runs outside the GPU queue


def test_AC12_3_3_lab_step_answers_422_use_lab_naming_the_lesson(course_env):
    from gsm8k.course.steps import get_step
    from gsm8k.lab.lessons import LESSONS

    env = course_env()
    step = get_step("c07")
    lesson = next(lesson for lesson in LESSONS if lesson.id == step.lesson)

    response = env.post("/course/c07/run")

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "use_lab"
    message = response.json()["message"].lower()
    assert lesson.id in message or lesson.title.lower() in message or f"lesson {lesson.number}" in message
    assert env.queue_ids() == [] and env.launches == []


@pytest.mark.parametrize("step_id", ["c06", "c19", "c24"])
def test_AC12_3_3_read_step_answers_422_nothing_to_run(course_env, step_id):
    env = course_env()

    response = env.post(f"/course/{step_id}/run")

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "nothing_to_run"
    assert env.queue_ids() == [] and env.launches == []


def test_AC12_3_3_c22_shows_a_notice_when_too_few_solutions_were_kept(course_env):
    env = course_env()
    env.write_row(
        "course-c22-cotgen-1", BASE_06, "cotgen", 0.3, data="gsm8k-train", metric="kept_fraction"
    )  # 30 of 100 problems kept

    answer = env.step("c22")

    assert "Too few solutions were kept (30); run the step again" in (answer.get("notice") or "")

    env.write_row("course-c22-cotgen-2", BASE_06, "cotgen", 0.6, data="gsm8k-train", metric="kept_fraction")
    assert env.step("c22").get("notice") is None  # the latest cotgen kept 60


# --- AC12.3.4: the quiz ---------------------------------------------------------------------------------


def test_AC12_3_4_all_right_passes_and_the_attempt_is_stored(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")

    response = env.post("/course/c01/quiz", {"answers": right_answers(step)})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["passed"] is True
    assert body["attempts"] == 1
    assert len(body["results"]) == len(step.questions)
    for result, question in zip(body["results"], step.questions, strict=True):
        assert result == {"right": True, "right_option": question.right, "explanation": question.explanation}
    stored = env.progress()["steps"]["c01"]["quiz"]
    assert len(stored["attempts"]) == 1
    assert stored["attempts"][0]["answers"] == right_answers(step)
    assert stored["attempts"][0]["right"] == [True] * len(step.questions)
    assert isinstance(stored["attempts"][0]["at"], str)
    assert isinstance(stored["passed_at"], str)
    summary = summaries(env.overview())["c01"]
    assert summary["quiz_passed"] is True


def test_AC12_3_4_a_wrong_answer_fails_the_quiz_and_a_later_attempt_is_allowed_and_counted(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")
    answers = right_answers(step)
    answers[0] = (answers[0] + 1) % len(step.questions[0].options)

    first = env.post("/course/c01/quiz", {"answers": answers}).json()

    assert first["passed"] is False
    assert first["attempts"] == 1
    assert [r["right"] for r in first["results"]] == [False] + [True] * (len(step.questions) - 1)
    assert first["results"][0]["right_option"] == step.questions[0].right
    assert first["results"][0]["explanation"] == step.questions[0].explanation
    assert env.progress()["steps"]["c01"]["quiz"]["passed_at"] is None

    second = env.post("/course/c01/quiz", {"answers": right_answers(step)}).json()

    assert second["passed"] is True
    assert second["attempts"] == 2
    stored = env.progress()["steps"]["c01"]["quiz"]
    assert len(stored["attempts"]) == 2
    assert stored["attempts"][0]["right"][0] is False
    assert isinstance(stored["passed_at"], str)
    progress = env.overview()["progress"]
    assert progress["first_try_right"] == len(step.questions) - 1  # only the first attempt counts
    assert progress["questions_answered"] == len(step.questions)


@pytest.mark.parametrize(
    "case", ["too_few", "too_many", "empty", "out_of_range_high", "out_of_range_negative"]
)
def test_AC12_3_4_invalid_answers_answer_422_and_store_nothing(course_env, case):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")
    answers = right_answers(step)
    if case == "too_few":
        answers = answers[:-1]
    elif case == "too_many":
        answers = [*answers, 0]
    elif case == "empty":
        answers = []
    elif case == "out_of_range_high":
        answers[0] = len(step.questions[0].options)
    else:
        answers[0] = -1

    response = env.post("/course/c01/quiz", {"answers": answers})

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "invalid_answers"
    assert not env.progress_path.exists() or not env.progress()["steps"].get("c01", {}).get("quiz", {}).get(
        "attempts"
    )


# --- AC12.3.5: own words, opening, progress.json -----------------------------------------------------------


def test_AC12_3_5_own_words_are_stored_with_their_time_and_answer_with_the_model_answer(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")

    response = env.client.put(
        f"{API}/course/c01/own-words", json={"text": "A base model is scored on 100 problems."}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model_answer"] == step.model_answer
    assert isinstance(body["saved_at"], str)
    stored = env.progress()["steps"]["c01"]["own_words"]
    assert stored["text"] == "A base model is scored on 100 problems."
    assert stored["saved_at"] == body["saved_at"]

    again = env.client.put(f"{API}/course/c01/own-words", json={"text": "Changed my mind."})  # can be changed
    assert again.status_code == 200, again.text
    assert env.progress()["steps"]["c01"]["own_words"]["text"] == "Changed my mind."
    assert env.step("c01")["own_words"] == "Changed my mind."


@pytest.mark.parametrize("length", [1, 4000])
def test_AC12_3_5_own_words_of_1_to_4000_characters_are_accepted(course_env, length):
    env = course_env()

    response = env.client.put(f"{API}/course/c01/own-words", json={"text": "x" * length})

    assert response.status_code == 200, response.text
    assert len(env.progress()["steps"]["c01"]["own_words"]["text"]) == length


@pytest.mark.parametrize("length", [0, 4001])
def test_AC12_3_5_empty_or_too_long_own_words_answer_422_invalid_text(course_env, length):
    env = course_env()

    response = env.client.put(f"{API}/course/c01/own-words", json={"text": "x" * length})

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "invalid_text"
    assert not env.progress_path.exists() or env.progress()["steps"].get("c01", {}).get("own_words") is None


def test_AC12_3_5_open_records_the_first_time_and_later_calls_keep_it(course_env):
    env = course_env()

    first = env.post("/course/c08/open")
    assert first.status_code == 200, first.text
    opened_at = first.json()["opened_at"]
    assert isinstance(opened_at, str)
    assert env.progress()["steps"]["c08"]["opened_at"] == opened_at
    assert summaries(env.overview())["c08"]["state"] == "in-progress"

    import time

    time.sleep(1.1)  # times are ISO seconds: a changed value would differ
    second = env.post("/course/c08/open")

    assert second.status_code == 200, second.text
    assert second.json()["opened_at"] == opened_at
    assert env.progress()["steps"]["c08"]["opened_at"] == opened_at


def test_AC12_3_5_progress_json_is_written_atomically_by_a_temporary_file_and_a_rename(
    course_env, monkeypatch
):
    env = course_env()
    renames: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def spy(src, dst, *args, **kwargs):
        renames.append((Path(src), Path(dst)))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", spy)

    assert env.post("/course/c01/open").status_code == 200

    target = env.progress_path
    assert any(dst == target and src != target and src.parent == target.parent for src, dst in renames)
    assert [p.name for p in env.course.iterdir() if p.name.startswith("progress.json") and p != target] == []
    assert env.progress()["v"] == 1


def test_AC12_3_5_a_missing_progress_file_reads_as_no_progress(course_env):
    env = course_env()
    assert not env.progress_path.exists()

    overview = env.overview()
    step = env.step("c01")

    assert overview["progress"]["done"] == 0
    assert all(not q["answered"] for q in step["questions"])
    assert step["own_words"] is None
    assert not env.progress_path.exists()


@pytest.mark.parametrize("garbage", ["{not json", "[1, 2]"])
def test_AC12_3_5_an_unreadable_progress_file_answers_500_naming_it_and_is_never_overwritten(
    course_env, garbage
):
    from gsm8k.course.steps import get_step

    env = course_env()
    env.progress_path.write_text(garbage, encoding="utf-8")
    step = get_step("c01")

    responses = [
        env.get("/course"),
        env.post("/course/c01/quiz", {"answers": right_answers(step)}),
        env.client.put(f"{API}/course/c01/own-words", json={"text": "my words"}),
        env.post("/course/c01/open"),
    ]

    for response in responses:
        assert response.status_code == 500, response.text
        assert response.json()["error"] == "progress_unreadable"
        assert (
            str(env.progress_path) in response.json()["message"]
            or "progress.json" in response.json()["message"]
        )
    assert env.progress_path.read_text(encoding="utf-8") == garbage


def test_AC12_3_5_step_ids_the_course_does_not_know_are_kept_when_the_file_is_written(course_env):
    env = course_env()
    env.write_progress({"c99": {"opened_at": "2026-11-01T00:00:00Z", "quiz": None, "own_words": None}})

    assert env.post("/course/c01/open").status_code == 200

    steps = env.progress()["steps"]
    assert steps["c99"] == {"opened_at": "2026-11-01T00:00:00Z", "quiz": None, "own_words": None}
    assert "c01" in steps
    assert "c99" not in summaries(env.overview())


# --- AC12.3.6: c19 memory table ---------------------------------------------------------------------------


def test_AC12_3_6_memory_table_has_null_figures_until_architectures_exist(course_env):
    from gsm8k.course.steps import COURSE_MODELS

    env = course_env()

    memory = env.step("c19")["memory"]

    assert [row["model"] for row in memory] == [model.id for model in COURSE_MODELS]
    for row in memory:
        for key in ("full_gb", "lora_gb", "qlora_gb", "full_fits", "lora_fits", "qlora_fits"):
            assert row[key] is None, (row["model"], key)
    assert env.step("c06")["memory"] is None  # c19 only


def test_AC12_3_6_memory_table_figures_follow_the_bytes_per_weight_and_the_adapter_size(course_env):
    from gsm8k.course.steps import COURSE_MODELS

    env = course_env()
    env.write_architectures()

    memory = env.step("c19")["memory"]

    assert [row["model"] for row in memory] == [model.id for model in COURSE_MODELS]
    for row in memory:
        design = DESIGNS[row["model"]]
        want = expected_bytes(design)
        assert gb_matches(row["full_gb"], want["full"]), (row["model"], "full", row["full_gb"])
        assert gb_matches(row["lora_gb"], want["lora"]), (row["model"], "lora", row["lora_gb"])
        assert gb_matches(row["qlora_gb"], want["qlora"]), (row["model"], "qlora", row["qlora_gb"])
        for approach, flag in (("full", "full_fits"), ("lora", "lora_fits"), ("qlora", "qlora_fits")):
            verdicts = {want[approach] / unit <= CARD_GB for unit in GB_UNITS}
            assert len(verdicts) == 1, "fixture sits on the 6.5 GB boundary under one reading"
            assert row[flag] is verdicts.pop(), (row["model"], approach)
    by_model = {row["model"]: row for row in memory}
    assert by_model["Qwen/Qwen3-1.7B-Base"]["full_fits"] is False
    assert by_model["Qwen/Qwen3-1.7B-Base"]["lora_fits"] is True
    assert by_model["Qwen/Qwen3-1.7B-Base"]["qlora_fits"] is True
    assert by_model["HuggingFaceTB/SmolLM2-360M"]["full_fits"] is True


def test_AC12_3_6_c19_says_the_figures_leave_out_activations(course_env):
    env = course_env()
    env.write_architectures()

    text = json.dumps(env.step("c19"), ensure_ascii=False).lower()

    assert "activations" in text


# --- AC12.3.7: c24 comparison ------------------------------------------------------------------------------


def _comparison(env: CourseEnv) -> list[dict]:
    comparison = env.step("c24")["comparison"]
    assert isinstance(comparison, list)
    return comparison


def test_AC12_3_7_comparison_is_empty_before_any_course_run_finished(course_env):
    env = course_env()

    assert _comparison(env) == []
    assert env.step("c06")["comparison"] is None  # c24 only


def test_AC12_3_7_comparison_lists_accuracy_interval_gain_and_the_noise_label(course_env):
    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.50, 2.0)
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.02, 1.0)
    env.write_row("course-c05-qwen3-17-1", "Qwen/Qwen3-1.7B-Base", "base", 0.80, 4.0)
    env.write_row("course-c20-lora-1", BASE_06, "sft", 0.58, 6.0)
    env.write_row("course-c21-sft-1", BASE_06, "sft", 0.75, 7.0)
    env.write_row(
        "course-c22-cotgen-1", BASE_06, "cotgen", 0.70, 5.0, data="gsm8k-train", metric="kept_fraction"
    )
    env.write_run_folder("course-c20-qlora-1", "failed")  # no row: not listed

    rows = {item["attempt_id"]: item for item in _comparison(env)}

    assert set(rows) == {
        "course-c01-base-06-1",
        "course-c05-pythia-1",
        "course-c05-qwen3-17-1",
        "course-c20-lora-1",
        "course-c21-sft-1",
    }  # cotgen is a keep rate, not an accuracy; the failed run has no row
    base = rows["course-c01-base-06-1"]
    assert (base["step"], base["run"], base["model"], base["method"]) == ("c01", "base-06", BASE_06, "base")
    assert base["accuracy"] == pytest.approx(0.50)
    assert base["minutes"] == pytest.approx(2.0)
    low, high = interval(0.50)
    assert base["interval_low"] == pytest.approx(low, abs=1e-3)
    assert base["interval_high"] == pytest.approx(high, abs=1e-3)
    assert base["gain_pts"] is None and base["noise"] is None  # the reference itself

    lora = rows["course-c20-lora-1"]
    assert (lora["step"], lora["run"], lora["method"]) == ("c20", "lora", "sft")
    assert lora["gain_pts"] == pytest.approx(8.0, abs=0.1)
    assert lora["noise"] == "within noise"  # [0.483, 0.677] overlaps [0.402, 0.598]

    sft = rows["course-c21-sft-1"]
    assert sft["gain_pts"] == pytest.approx(25.0, abs=0.1)
    assert sft["noise"] is None  # [0.665, 0.835] does not overlap
    low, high = interval(0.75)
    assert (sft["interval_low"], sft["interval_high"]) == (
        pytest.approx(low, abs=1e-3),
        pytest.approx(high, abs=1e-3),
    )

    for attempt_id in ("course-c05-pythia-1", "course-c05-qwen3-17-1"):  # gain only for Qwen3-0.6B runs
        assert rows[attempt_id]["gain_pts"] is None and rows[attempt_id]["noise"] is None


def test_AC12_3_7_intervals_are_clipped_to_0_and_1(course_env):
    env = course_env()
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.0)
    env.write_row("course-c05-qwen3-17-1", "Qwen/Qwen3-1.7B-Base", "base", 1.0)

    rows = {item["attempt_id"]: item for item in _comparison(env)}

    assert rows["course-c05-pythia-1"]["interval_low"] == 0.0
    assert rows["course-c05-pythia-1"]["interval_high"] == pytest.approx(0.0, abs=1e-3)
    assert rows["course-c05-qwen3-17-1"]["interval_high"] == 1.0


def test_AC12_3_7_only_the_latest_attempt_of_a_run_is_listed(course_env):
    env = course_env()
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.02)
    env.write_row("course-c05-pythia-2", "EleutherAI/pythia-31m", "base", 0.04)

    rows = _comparison(env)

    assert [item["attempt_id"] for item in rows] == ["course-c05-pythia-2"]
    assert rows[0]["accuracy"] == pytest.approx(0.04)


def test_AC12_3_7_c24_says_100_problems_give_wide_intervals_and_points_to_the_reference_runs(course_env):
    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.50)

    text = json.dumps(env.step("c24"), ensure_ascii=False)

    assert "±10 points" in text
    assert "500 problems" in text


# --- AC12.3.8: course runs are not results -----------------------------------------------------------------


def test_AC12_3_8_course_rows_never_appear_with_accuracy_in_the_run_list(course_env):
    from gsm8k.run_records.log import RunRow, append_row

    env = course_env()
    append_row(
        env.dirs.results,
        RunRow(
            "2026-11-05T10:00:00Z",
            "q06-base-dev-1",
            BASE_06,
            "base",
            "gsm8k-dev",
            "accuracy",
            0.4,
            9.0,
            "1" * 64,
        ),
    )
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.9, 2.0)
    env.write_row("course-c05-pythia-1", "EleutherAI/pythia-31m", "base", 0.91, 1.0)
    env.write_run_folder("course-c01-base-06-1", "finished")
    (env.outputs / "course-c01-base-06-1" / "config.json").write_text(
        json.dumps({"v": 1, "run_id": "course-c01-base-06-1", "model": BASE_06, "method": "base"}),
        encoding="utf-8",
    )

    response = env.get("/runs")

    assert response.status_code == 200, response.text
    runs = {run["run_id"]: run for run in response.json()["runs"]}
    assert set(runs) == {"q06-base-dev-1", "course-c01-base-06-1"}  # the pythia row has no folder: not listed
    assert runs["q06-base-dev-1"]["dev_accuracy"] == pytest.approx(0.4)
    course = runs["course-c01-base-06-1"]
    assert course["status"] == "finished"
    assert course["dev_accuracy"] is None
    assert course["test_accuracy"] is None
    assert course["minutes"] is None
    assert course["gain"] is None
    assert "0.9" not in json.dumps(response.json()["runs"])
    assert env.dirs.results.read_text(encoding="utf-8").count("course-") == 0  # the run log is untouched


def test_AC12_3_8_course_rows_alone_give_an_empty_run_list(course_env):
    env = course_env()
    env.write_row("course-c01-base-06-1", BASE_06, "base", 0.9)

    response = env.get("/runs")

    assert response.status_code == 200, response.text
    assert response.json()["runs"] == []


def test_AC12_3_8_course_routes_never_write_the_run_log(course_env):
    from gsm8k.course.steps import get_step

    env = course_env()
    step = get_step("c01")

    assert env.post("/course/c01/run").status_code == 202
    assert env.post("/course/c01/quiz", {"answers": right_answers(step)}).status_code == 200
    assert env.post("/course/c02/run").status_code == 202
    env.step("c24")
    env.step("c19")

    assert not env.dirs.results.exists()


# --- AC12.4.6: c23 and a missing c21 adapter ----------------------------------------------------------------


def test_AC12_4_6_c23_with_a_missing_c21_adapter_is_not_queued_and_says_so(course_env):
    env = course_env()
    env.write_row(
        "course-c21-sft-1", BASE_06, "sft", 0.5, 3.0
    )  # finished, but checkpoints/course-c21-sft-1 is gone
    message = "Run step c21 again: its adapter is missing"

    response = env.post("/course/c23/run")

    assert response.status_code == 422, response.text
    assert response.json()["error"] == "nothing_to_run"
    assert message in response.json()["message"]
    assert env.queue_ids() == []
    answer = env.step("c23")
    assert message in (answer.get("notice") or "")


def test_AC12_4_6_c23_runs_grpo_from_the_latest_finished_c21_adapter(course_env):
    from gsm8k import run_config
    from gsm8k.run_control import queue

    env = course_env()
    env.write_row("course-c21-sft-1", BASE_06, "sft", 0.5)
    env.write_row("course-c21-sft-2", BASE_06, "sft", 0.55)
    (env.checkpoints / "course-c21-sft-1").mkdir()
    (env.checkpoints / "course-c21-sft-2").mkdir()

    response = env.post("/course/c23/run")

    assert response.status_code == 202, response.text
    assert response.json()["attempt_ids"] == ["course-c23-grpo-1"]
    (entry,) = queue.list_queue(env.outputs)
    assert entry.results == COURSE_RESULTS
    config = entry.config
    assert config["method"] == "grpo" and config["grpo_steps"] == 20 and config["grpo_generations"] == 4
    assert config["limit"] == 100
    assert Path(config["adapter_path"]).resolve() == (env.checkpoints / "course-c21-sft-2").resolve()
    run_config.validate(run_config.from_dict(config))
    assert env.step("c23").get("notice") is None


def test_AC12_4_6_c23_without_any_c21_run_starts_from_the_base_model(course_env):
    from gsm8k.run_control import queue

    env = course_env()

    response = env.post("/course/c23/run")

    assert response.status_code == 202, response.text
    (entry,) = queue.list_queue(env.outputs)
    assert entry.config["adapter_path"] is None
    assert env.step("c23").get("notice") is None
