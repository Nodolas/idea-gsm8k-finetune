"""u4-run-service evaluation progress in the status (batch-10 part P): AC3.1.6 and AC3.1.7.

A RUNNING run's status carries ``evaluation: {split, scored, total}``: ``scored`` is the number of complete
lines (ending in a newline) of ``outputs/<run_id>/predictions.jsonl``, ``total`` the split's size from
``gsm8k.run_control.launch.SPLIT_SIZES`` or the run's ``limit`` when that is smaller (contract C6
``Status.evaluation``). The status is stubbed through ``gsm8k.run_control.status.current_status`` and every
file lives in the temp outputs folder of ``tmp_project_dirs``; nothing touches the real outputs/ or
results/runs.csv. The service modules are imported inside each test, so a missing module fails each test
alone. CPU only, no model loads.
"""

import asyncio
import json
import time
from pathlib import Path

from gsm8k.run_config import RunConfig, to_dict

API = "/api/v1"
EVAL_RUN = "q06-base-dev-1"
STATUS_KEYS = {"status", "run_id", "reason", "log_tail", "started_at", "last_run"}


# --- helpers ---------------------------------------------------------------------------------------


def _run_folder(outputs: Path, run_id: str = EVAL_RUN, *, split: str = "dev", limit=None, method="base"):
    """A run folder with its C2 config.json, as the launcher writes it."""
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    cfg = RunConfig(run_id=run_id, method=method, split=split, limit=limit)
    (folder / "config.json").write_text(json.dumps(to_dict(cfg), indent=2) + "\n", encoding="utf-8")
    return folder


def _prediction(i: int) -> str:
    line = {"problem_id": f"dev-{i}", "output": "x #### 1", "predicted": "1", "gold": "1", "correct": True}
    return json.dumps(line) + "\n"


def _write_predictions(folder: Path, complete: int, partial: str = "") -> Path:
    path = folder / "predictions.jsonl"
    path.write_text("".join(_prediction(i) for i in range(complete)) + partial, encoding="utf-8")
    return path


def _append_predictions(path: Path, start: int, count: int) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write("".join(_prediction(i) for i in range(start, start + count)))


def _running(monkeypatch, run_id: str | None = EVAL_RUN) -> None:
    """Make every status read report ``run_id`` as RUNNING (the lock holder)."""
    from gsm8k.run_control import status

    monkeypatch.setattr(
        status, "current_status", lambda outputs=None: status.RunStatus(state=status.RUNNING, run_id=run_id)
    )


def _idle_with_last_run(monkeypatch, run_id: str = EVAL_RUN) -> None:
    """IDLE, with ``run_id`` as the last run (FAILED: ended without finishing)."""
    from gsm8k.run_control import status

    last = status.RunStatus(state=status.FAILED, run_id=run_id, reason=status.ENDED_WITHOUT_FINISHING)
    monkeypatch.setattr(
        status,
        "current_status",
        lambda outputs=None: status.RunStatus(state=status.IDLE, run_id=None, last_run=last),
    )


def _client(dirs):
    from fastapi.testclient import TestClient

    from gsm8k.service.app import create_app

    app = create_app(
        results=dirs.results, finalists=dirs.results.parent / "finalists.json", outputs=dirs.outputs
    )
    return TestClient(app)


def _get_status(dirs) -> dict:
    with _client(dirs) as client:
        response = client.get(f"{API}/status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert STATUS_KEYS <= set(body), body
    assert "evaluation" in body, body
    return body


def _parse_sse(chunk: str) -> list[dict]:
    """The SSE events in one yielded chunk, each a dict of field -> value (``data`` parsed as JSON)."""
    events = []
    for block in chunk.split("\n\n"):
        fields: dict = {}
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            name, _, value = line.partition(":")
            fields[name] = value[1:] if value.startswith(" ") else value
        if "data" in fields:
            fields["data"] = json.loads(fields["data"])
            events.append(fields)
    return events


async def _next_status(gen, deadline: float) -> dict:
    """The data of the next ``status`` event the stream yields before ``deadline`` (monotonic)."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("No status event arrived in time")
        try:
            chunk = await asyncio.wait_for(gen.__anext__(), timeout=remaining)
        except TimeoutError as exc:
            raise AssertionError("No status event arrived in time") from exc
        statuses = [e["data"] for e in _parse_sse(chunk) if e.get("event") == "status"]
        if statuses:
            return statuses[-1]


def _stream(dirs):
    from gsm8k.service import app as app_module

    svc = app_module._Service(dirs.results, dirs.results.parent / "finalists.json", dirs.outputs)
    return app_module._events(svc, None)


# --- AC3.1.6: evaluation progress in the status ------------------------------------------------------


def test_AC3_1_6_progress_counts_complete_lines_only(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 7, partial='{"problem_id": "dev-7", "outp')
    assert evaluation_progress(tmp_project_dirs.outputs, EVAL_RUN) == {
        "split": "dev",
        "scored": 7,
        "total": 500,
    }


def test_AC3_1_6_progress_counts_lines_without_parsing_them(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    folder = _run_folder(tmp_project_dirs.outputs)
    path = _write_predictions(folder, 3)
    with path.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
    assert evaluation_progress(tmp_project_dirs.outputs, EVAL_RUN) == {
        "split": "dev",
        "scored": 4,
        "total": 500,
    }


def test_AC3_1_6_progress_empty_predictions_scores_zero(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 0)
    assert evaluation_progress(tmp_project_dirs.outputs, EVAL_RUN) == {
        "split": "dev",
        "scored": 0,
        "total": 500,
    }


def test_AC3_1_6_progress_total_is_each_split_size(tmp_project_dirs):
    from gsm8k.run_control.launch import SPLIT_SIZES
    from gsm8k.service.progress import evaluation_progress

    assert SPLIT_SIZES["dev"] == 500 and SPLIT_SIZES["test"] == 1319
    for i, (split, size) in enumerate(SPLIT_SIZES.items(), start=1):
        run_id = f"q06-base-x-{i}"
        folder = _run_folder(tmp_project_dirs.outputs, run_id, split=split)
        _write_predictions(folder, 2)
        assert evaluation_progress(tmp_project_dirs.outputs, run_id) == {
            "split": split,
            "scored": 2,
            "total": size,
        }


def test_AC3_1_6_progress_total_is_limit_when_smaller(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    small = _run_folder(tmp_project_dirs.outputs, "q06-base-dev-2", limit=20)
    _write_predictions(small, 5)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-2") == {
        "split": "dev",
        "scored": 5,
        "total": 20,
    }
    large = _run_folder(tmp_project_dirs.outputs, "q06-base-dev-3", limit=800)
    _write_predictions(large, 5)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-3") == {
        "split": "dev",
        "scored": 5,
        "total": 500,
    }


def test_AC3_1_6_progress_scored_never_above_total(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    limited = _run_folder(tmp_project_dirs.outputs, "q06-base-dev-2", limit=10)
    _write_predictions(limited, 12)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-2") == {
        "split": "dev",
        "scored": 10,
        "total": 10,
    }
    whole = _run_folder(tmp_project_dirs.outputs, "q06-base-dev-3")
    _write_predictions(whole, 503)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-3") == {
        "split": "dev",
        "scored": 500,
        "total": 500,
    }


def test_AC3_1_6_progress_none_without_predictions_file(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    _run_folder(tmp_project_dirs.outputs)
    assert evaluation_progress(tmp_project_dirs.outputs, EVAL_RUN) is None
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-9") is None  # no run folder at all


def test_AC3_1_6_progress_none_when_config_missing_or_unreadable(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    outputs = tmp_project_dirs.outputs
    cases = {
        "q06-base-dev-2": None,  # no config.json
        "q06-base-dev-3": "{not json",
        "q06-base-dev-4": "[1, 2, 3]\n",  # valid JSON, not an object
        "q06-base-dev-5": "",  # empty file
        "q06-base-dev-6": b"\xff\xfe\x00garbage",  # not UTF-8
    }
    for run_id, content in cases.items():
        folder = outputs / run_id
        folder.mkdir()
        _write_predictions(folder, 3)
        if isinstance(content, bytes):
            (folder / "config.json").write_bytes(content)
        elif content is not None:
            (folder / "config.json").write_text(content, encoding="utf-8")
        assert evaluation_progress(outputs, run_id) is None, run_id
    unreadable = outputs / "q06-base-dev-7"
    (unreadable / "config.json").mkdir(parents=True)  # reading a folder raises an OSError
    _write_predictions(unreadable, 3)
    assert evaluation_progress(outputs, "q06-base-dev-7") is None


def test_AC3_1_6_progress_none_when_predictions_unreadable(tmp_project_dirs):
    from gsm8k.service.progress import evaluation_progress

    folder = _run_folder(tmp_project_dirs.outputs)
    (folder / "predictions.jsonl").mkdir()  # reading a folder raises an OSError
    assert evaluation_progress(tmp_project_dirs.outputs, EVAL_RUN) is None


def test_AC3_1_6_progress_none_for_split_without_size(tmp_project_dirs):
    from gsm8k.run_control.launch import SPLIT_SIZES
    from gsm8k.service.progress import evaluation_progress

    assert "train" not in SPLIT_SIZES
    folder = _run_folder(tmp_project_dirs.outputs, "q06-cotgen-train-1", split="train", method="cotgen")
    _write_predictions(folder, 3)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-cotgen-train-1") is None
    odd = tmp_project_dirs.outputs / "q06-base-dev-2"
    odd.mkdir()
    (odd / "config.json").write_text(json.dumps({"split": "nosuchsplit"}), encoding="utf-8")
    _write_predictions(odd, 3)
    assert evaluation_progress(tmp_project_dirs.outputs, "q06-base-dev-2") is None


def test_AC3_1_6_status_carries_evaluation_for_running_run(tmp_project_dirs, monkeypatch):
    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 42, partial='{"problem_id": "dev-42"')
    _running(monkeypatch)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN
    assert body["evaluation"] == {"split": "dev", "scored": 42, "total": 500}


def test_AC3_1_6_status_evaluation_uses_limit_and_caps_scored(tmp_project_dirs, monkeypatch):
    folder = _run_folder(tmp_project_dirs.outputs, limit=8)
    _write_predictions(folder, 9)
    _running(monkeypatch)
    assert _get_status(tmp_project_dirs)["evaluation"] == {"split": "dev", "scored": 8, "total": 8}


def test_AC3_1_6_status_evaluation_null_without_predictions(tmp_project_dirs, monkeypatch):
    _run_folder(tmp_project_dirs.outputs)
    _running(monkeypatch)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN
    assert body["evaluation"] is None


def test_AC3_1_6_status_evaluation_null_when_config_bad(tmp_project_dirs, monkeypatch):
    _running(monkeypatch)
    folder = tmp_project_dirs.outputs / EVAL_RUN
    folder.mkdir()
    _write_predictions(folder, 3)
    body = _get_status(tmp_project_dirs)  # no config.json
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN and body["evaluation"] is None
    (folder / "config.json").write_text("{not json", encoding="utf-8")
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN and body["evaluation"] is None
    (folder / "config.json").unlink()
    (folder / "config.json").mkdir()  # unreadable
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN and body["evaluation"] is None


def test_AC3_1_6_status_evaluation_null_for_split_without_size(tmp_project_dirs, monkeypatch):
    run_id = "q06-cotgen-train-1"
    folder = _run_folder(tmp_project_dirs.outputs, run_id, split="train", method="cotgen")
    _write_predictions(folder, 3)
    _running(monkeypatch, run_id)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == run_id and body["evaluation"] is None


def test_AC3_1_6_status_evaluation_null_when_not_running(tmp_project_dirs, monkeypatch):
    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 42)
    _idle_with_last_run(monkeypatch)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "IDLE" and body["evaluation"] is None
    last = body["last_run"]
    assert last is not None and last["run_id"] == EVAL_RUN and last["status"] == "FAILED"
    assert "evaluation" in last and last["evaluation"] is None


def test_AC3_1_6_status_evaluation_null_when_running_without_run_id(tmp_project_dirs, monkeypatch):
    _running(monkeypatch, None)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["evaluation"] is None


def test_AC3_1_6_status_evaluation_null_when_idle_without_runs(tmp_project_dirs):
    body = _get_status(tmp_project_dirs)  # the real current_status on an empty temp outputs folder
    assert body["status"] == "IDLE" and body["evaluation"] is None and body["last_run"] is None


def test_AC3_1_6_status_answers_with_unreadable_run_files(tmp_project_dirs, monkeypatch):
    """Folders where config.json and predictions.jsonl belong: reading them fails, the status still
    answers 200 with the rest unchanged and evaluation null."""
    folder = tmp_project_dirs.outputs / EVAL_RUN
    (folder / "config.json").mkdir(parents=True)
    (folder / "predictions.jsonl").mkdir()
    _running(monkeypatch)
    body = _get_status(tmp_project_dirs)
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN and body["evaluation"] is None


def test_AC3_1_6_stream_status_event_carries_evaluation(tmp_project_dirs, monkeypatch):
    from gsm8k.service import app as app_module

    monkeypatch.setattr(app_module, "STREAM_POLL_SECONDS", 0.02)
    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 11)
    _running(monkeypatch)

    async def scenario() -> dict:
        gen = _stream(tmp_project_dirs)
        try:
            return await _next_status(gen, time.monotonic() + 3.0)
        finally:
            await gen.aclose()

    payload = asyncio.run(scenario())
    assert payload["status"] == "RUNNING" and payload["run_id"] == EVAL_RUN
    assert payload["evaluation"] == {"split": "dev", "scored": 11, "total": 500}


# --- AC3.1.7: the stream sends new evaluation progress ------------------------------------------------


def test_AC3_1_7_stream_sends_new_scored_when_predictions_grow(tmp_project_dirs, monkeypatch):
    from gsm8k.service import app as app_module

    monkeypatch.setattr(app_module, "STREAM_POLL_SECONDS", 0.02)
    folder = _run_folder(tmp_project_dirs.outputs)
    path = _write_predictions(folder, 3)
    _running(monkeypatch)

    async def scenario() -> tuple[dict, dict, float]:
        gen = _stream(tmp_project_dirs)
        try:
            first = await _next_status(gen, time.monotonic() + 3.0)
            _append_predictions(path, 3, 4)
            appended = time.monotonic()
            second = await _next_status(gen, appended + 5.0)  # NFR10: within 5 seconds
            return first, second, time.monotonic() - appended
        finally:
            await gen.aclose()

    first, second, waited = asyncio.run(scenario())
    assert first["evaluation"] == {"split": "dev", "scored": 3, "total": 500}
    assert second["status"] == "RUNNING" and second["run_id"] == EVAL_RUN
    assert second["evaluation"] == {"split": "dev", "scored": 7, "total": 500}
    assert second["evaluation"]["scored"] > first["evaluation"]["scored"]
    assert waited < 5.0


# --- AC3.1.6 with the app built the way `gsm8k serve` builds it (no `outputs` argument) ---------------


def _default_client(dirs):
    """The app as the real service builds it: no `outputs`, so the outputs root comes from
    `gsm8k.run_records.paths.outputs_root()`, which `tmp_project_dirs` points at the temp folder
    through GSM8K_OUTPUTS_DIR."""
    from fastapi.testclient import TestClient

    from gsm8k.run_records import paths
    from gsm8k.service.app import create_app

    assert paths.outputs_root() == dirs.outputs
    return TestClient(create_app(results=dirs.results, finalists=dirs.results.parent / "finalists.json"))


def test_AC3_1_6_status_carries_evaluation_with_default_outputs(tmp_project_dirs, monkeypatch):
    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 42, partial='{"problem_id": "dev-42"')
    _running(monkeypatch)
    with _default_client(tmp_project_dirs) as client:
        response = client.get(f"{API}/status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "RUNNING" and body["run_id"] == EVAL_RUN
    assert body["evaluation"] == {"split": "dev", "scored": 42, "total": 500}


def test_AC3_1_6_status_evaluation_uses_limit_with_default_outputs(tmp_project_dirs, monkeypatch):
    folder = _run_folder(tmp_project_dirs.outputs, limit=8)
    _write_predictions(folder, 9)
    _running(monkeypatch)
    with _default_client(tmp_project_dirs) as client:
        body = client.get(f"{API}/status").json()
    assert body["evaluation"] == {"split": "dev", "scored": 8, "total": 8}


def test_AC3_1_6_stream_status_event_carries_evaluation_with_default_outputs(tmp_project_dirs, monkeypatch):
    from gsm8k.service import app as app_module

    monkeypatch.setattr(app_module, "STREAM_POLL_SECONDS", 0.02)
    folder = _run_folder(tmp_project_dirs.outputs)
    _write_predictions(folder, 11)
    _running(monkeypatch)

    async def scenario() -> dict:
        svc = app_module._Service(
            tmp_project_dirs.results, tmp_project_dirs.results.parent / "finalists.json", None
        )
        gen = app_module._events(svc, None)
        try:
            return await _next_status(gen, time.monotonic() + 3.0)
        finally:
            await gen.aclose()

    payload = asyncio.run(scenario())
    assert payload["status"] == "RUNNING" and payload["run_id"] == EVAL_RUN
    assert payload["evaluation"] == {"split": "dev", "scored": 11, "total": 500}
