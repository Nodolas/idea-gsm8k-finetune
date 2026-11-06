"""The HTTP service of u4-run-service, part H3 (US3.1, US3.3; contracts C6, C7; NFR6; ADR-006).

Every test drives `gsm8k.service.app.create_app(results=..., finalists=..., outputs=...)` through
FastAPI's `TestClient` on temp folders (`tmp_project_dirs`); no real port is bound and no model loads.
Nothing touches the project's outputs/, checkpoints/, results/runs.csv or results/finalists.json.
A running run is either the GPU lock held by this test process (`GpuLock`, its own file descriptor,
so the service sees it as held) or a tiny stub script that holds the lock like a real run. Before a
confirm, H2's `gsm8k.run_control.launch.build_argv` is pointed at a harmless command, so nothing real
starts. The service modules are imported inside each test, so a missing module fails each test alone.

Shapes C6 leaves open, chosen here: `GET /queue` returns `{"entries": [...]}` (the C7 queue payload),
each entry with `attempt_id` and `position`; `GET /finalists` returns `{"finalists": [...]}` whose
items are run ids or C4 entries with `run_id`; marking a run that is not in the run log is 404
`not_found`. `POST /runs/check` takes C2 config fields only; the kind (train or evaluate) follows
from the method (`run_config.TRAINING_METHODS`).
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from gsm8k.run_config import RunConfig, to_dict
from gsm8k.run_records.folder import write_status
from gsm8k.run_records.lock import GpuLock, lock_path
from gsm8k.run_records.log import RunRow, append_row

API = "/api/v1"
Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
ACTIVE_RUN = "q06-sft-dev-1"
STATUS_KEYS = {"status", "run_id", "reason", "log_tail"}
CHECKED_RUN_KEYS = {
    "check_id",
    "attempt_id",
    "model",
    "method",
    "changes",
    "estimate_s",
    "over_cap",
    "command",
    "queue_position",
    "needs_second_confirmation",
}
FORBIDDEN_TOP_LEVEL = ("torch", "transformers", "peft", "trl", "lm_eval")
FORBIDDEN_GSM8K = ("gsm8k.training", "gsm8k.evaluation", "gsm8k.train_cmd", "gsm8k.harness")


# --- helpers ---------------------------------------------------------------------------------------


def _paths(dirs) -> tuple[Path, Path]:
    """The temp run log and the temp finalists file (neither created)."""
    return dirs.results, dirs.results.parent / "finalists.json"


def _app(dirs):
    from gsm8k.service.app import create_app

    results, finalists = _paths(dirs)
    return create_app(results=results, finalists=finalists, outputs=dirs.outputs)


def _client(dirs):
    from fastapi.testclient import TestClient

    return TestClient(_app(dirs))


def _row(run_id, *, method="base", data="gsm8k-dev", value=0.35, minutes=12.5, model=Q06, adapter_run=""):
    return RunRow(
        date="2026-11-01T20:00:00Z",
        run_id=run_id,
        model=model,
        method=method,
        data=data,
        metric="accuracy",
        value=value,
        minutes=minutes,
        config_hash="0" * 64,
        adapter_run=adapter_run,
    )


def _run_folder(outputs: Path, run_id: str, *, model=Q06, method="sft", split="dev") -> Path:
    """A run folder with its config.json (C2), as the launcher writes it before the run starts."""
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    cfg = RunConfig(run_id=run_id, model=model, method=method, split=split)
    (folder / "config.json").write_text(json.dumps(to_dict(cfg), indent=2) + "\n", encoding="utf-8")
    return folder


def _metric_line(step: int, total: int = 10) -> str:
    line = {
        "v": 1,
        "step": step,
        "total_steps": total,
        "loss": round(1.0 / step, 4),
        "learning_rate": 0.0002,
        "elapsed_s": float(step),
        "eta_s": float(total - step),
    }
    return json.dumps(line) + "\n"


def _write_metrics(folder: Path, steps, partial: str = "") -> Path:
    path = folder / "metrics.jsonl"
    path.write_text("".join(_metric_line(s) for s in steps) + partial, encoding="utf-8")
    return path


def _assert_error(response, status: int, error: str) -> dict:
    """C6 Error: a JSON object with `error` (the enum value) and a `message`."""
    assert response.status_code == status, response.text
    body = response.json()
    assert body.get("error") == error, body
    assert isinstance(body.get("message"), str) and body["message"], body
    return body


def _queue_entries(client) -> list[dict]:
    response = client.get(f"{API}/queue")
    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert isinstance(entries, list)
    return entries


def _finalist_ids(client) -> list[str]:
    response = client.get(f"{API}/finalists")
    assert response.status_code == 200, response.text
    items = response.json()["finalists"]
    return [item if isinstance(item, str) else item["run_id"] for item in items]


def _stub_build_argv(monkeypatch) -> None:
    """Point H2's command builder at a harmless command, so a confirm can never start a real run."""
    monkeypatch.setattr(
        "gsm8k.run_control.launch.build_argv", lambda *args, **kwargs: [sys.executable, "-c", "pass"]
    )


def _check(client, dials: dict) -> dict:
    response = client.post(f"{API}/runs/check", json=dials)
    assert response.status_code == 200, response.text
    return response.json()


def _check_and_confirm(client, dials: dict, **extra) -> dict:
    checked = _check(client, dials)
    response = client.post(f"{API}/runs/confirm", json={"check_id": checked["check_id"], **extra})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attempt_id"] == checked["attempt_id"]
    return body


def _read_events(client, *, want, headers=None):
    """Start reading the C7 stream in a daemon thread until want(events) is true; returns at once.

    Returns (info, events, done): `info` holds the status code and content type, `events` the parsed
    SSE events so far (dicts of field -> value, `data` lines joined), `done` a threading.Event set
    when the reader has stopped. The list fills while the reader runs; callers bound every wait.
    """
    info: dict = {}
    events: list[dict] = []
    done = threading.Event()

    def reader() -> None:
        try:
            with client.stream("GET", f"{API}/stream", headers=headers or {}) as response:
                info["status"] = response.status_code
                info["content_type"] = response.headers.get("content-type", "")
                current: dict = {}
                for line in response.iter_lines():
                    if line == "":
                        if current:
                            events.append(current)
                            current = {}
                            if want(events):
                                break
                        continue
                    if line.startswith(":"):
                        continue  # keep-alive comment
                    name, _, value = line.partition(":")
                    value = value[1:] if value.startswith(" ") else value
                    if name == "data" and "data" in current:
                        current["data"] += "\n" + value
                    else:
                        current[name] = value
        except Exception as exc:  # reported by the caller through info
            info["error"] = repr(exc)
        finally:
            done.set()

    threading.Thread(target=reader, daemon=True).start()
    return info, events, done


def _metric_events(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("event") == "metric"]


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


STUB_RUN = textwrap.dedent(
    """
    import os, signal, sys, time
    from pathlib import Path

    from gsm8k.run_records import folder, lock

    run_id = sys.argv[1]
    rdir = Path(os.environ["GSM8K_OUTPUTS_DIR"]) / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    held = lock.GpuLock()
    held.acquire(run_id, started_by="worker")


    def on_term(signum, frame):
        folder.write_status(rdir, run_id=run_id, status="stopped", exit_code=130, reason="Stopped by SIGTERM")
        held.release()
        sys.exit(130)


    signal.signal(signal.SIGTERM, on_term)
    with open(rdir / "metrics.jsonl", "a", encoding="utf-8") as f:
        f.write('{"v": 1, "step": 1, "total_steps": 10, "loss": 1.0, "elapsed_s": 1.0, "eta_s": 9.0}\\n')
    (rdir / "ready").write_text("1", encoding="utf-8")
    for _ in range(1200):
        time.sleep(0.05)
    """
)


# --- US3.1: run list and status --------------------------------------------------------------------


def test_AC3_1_1_get_runs_lists_every_run_once(tmp_project_dirs):
    results, _ = _paths(tmp_project_dirs)
    append_row(results, _row("q06-base-dev-1", value=0.35, minutes=12.5))
    append_row(results, _row("q06-sft-dev-1", method="sft", value=0.41, minutes=48.0))
    append_row(results, _row("q06-base-test-1", data="gsm8k-test", value=0.33, minutes=30.0))
    stopped = _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-2")
    write_status(
        stopped, run_id="q06-sft-dev-2", status="stopped", exit_code=130, reason="Stopped by SIGTERM"
    )

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["skipped_rows"] == 0
    ids = [run["run_id"] for run in body["runs"]]
    assert sorted(ids) == sorted(["q06-base-dev-1", "q06-sft-dev-1", "q06-base-test-1", "q06-sft-dev-2"])
    by_id = {run["run_id"]: run for run in body["runs"]}
    base = by_id["q06-base-dev-1"]
    assert base["model"] == Q06 and base["method"] == "base"
    assert base["dev_accuracy"] == pytest.approx(0.35)
    assert base["minutes"] == pytest.approx(12.5)
    assert base["date"] == "2026-11-01T20:00:00Z"
    assert by_id["q06-sft-dev-1"]["method"] == "sft"
    assert by_id["q06-base-test-1"]["test_accuracy"] == pytest.approx(0.33)
    assert by_id["q06-sft-dev-2"]["status"] == "stopped"


def test_AC3_1_3_get_runs_reports_the_skipped_row_count(tmp_project_dirs):
    results, _ = _paths(tmp_project_dirs)
    append_row(results, _row("q06-base-dev-1"))
    with results.open("a", encoding="utf-8") as f:
        f.write("2026-11-01T21:00:00Z,q06-base-dev-2,NotAModel,base,gsm8k-dev,accuracy,0.5,1.0,abc,\n")
    append_row(results, _row("q06-sft-dev-1", method="sft"))

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["skipped_rows"] == 1
    assert sorted(run["run_id"] for run in body["runs"]) == ["q06-base-dev-1", "q06-sft-dev-1"]


def test_AC3_1_4_get_runs_without_a_results_file_is_empty(tmp_project_dirs):
    results, _ = _paths(tmp_project_dirs)
    assert not results.exists()

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    assert response.status_code == 200, response.text
    assert response.json() == {"runs": [], "skipped_rows": 0}


def test_AC3_1_4_get_runs_with_an_unreadable_results_file_names_the_file(tmp_project_dirs):
    results, _ = _paths(tmp_project_dirs)
    results.write_bytes(b"date,run_id\n\xff\xfe\xfa not utf-8\n")

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    body = _assert_error(response, 500, "run_log_unreadable")
    assert str(results) in body.get("file", ""), body


def test_AC3_1_1_get_run_detail_returns_config_status_and_timings(tmp_project_dirs):
    folder = _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-2")
    write_status(folder, run_id="q06-sft-dev-2", status="stopped", exit_code=130, reason="Stopped by SIGTERM")

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs/q06-sft-dev-2")
        missing = client.get(f"{API}/runs/q06-sft-dev-9")

    assert response.status_code == 200, response.text
    body = response.json()
    assert {"config", "status", "timings"} <= set(body)
    assert body["config"]["run_id"] == "q06-sft-dev-2"
    assert body["config"]["method"] == "sft"
    assert body["status"]["status"] == "stopped"
    _assert_error(missing, 404, "not_found")


def test_AC3_1_2_status_reads_idle_when_no_lock_file_exists(tmp_project_dirs):
    assert not lock_path().exists()

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert STATUS_KEYS <= set(body)
    assert body["status"] == "IDLE"


def test_AC3_1_2_status_reads_idle_when_the_lock_file_exists_but_is_free(tmp_project_dirs):
    held = GpuLock()
    held.acquire("q06-base-dev-1")
    held.release()
    assert lock_path().exists()

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/status")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "IDLE"


def test_AC3_1_2_status_reads_idle_when_a_free_lock_still_names_a_run(tmp_project_dirs):
    # The process ended without finishing; the kernel freed the lock, the content stayed (AC3.3.3).
    _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-4")
    lock_path().write_text(
        json.dumps(
            {
                "v": 1,
                "run_id": "q06-sft-dev-4",
                "pid": 999999,
                "started_at": "2026-11-01T20:00:00Z",
                "started_by": "worker",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/status")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "IDLE"


def test_AC3_1_5_serve_binds_to_127_0_0_1_only(tmp_project_dirs, monkeypatch):
    import uvicorn

    from gsm8k import cli

    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert cli.main(["serve"]) == 0
    assert len(calls) == 1
    assert calls[0][1].get("host") == "127.0.0.1"
    assert calls[0][1].get("port") == 8000

    calls.clear()
    assert cli.main(["serve", "--port", "8123"]) == 0
    assert len(calls) == 1
    assert calls[0][1].get("host") == "127.0.0.1"
    assert calls[0][1].get("port") == 8123

    for option in (["--host", "0.0.0.0"], ["--host=0.0.0.0"], ["--bind", "0.0.0.0"]):
        calls.clear()
        assert cli.main(["serve", *option]) != 0, option
        assert calls == [], option

    parser = cli.build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    serve = subparsers.choices["serve"]
    for action in serve._actions:
        names = " ".join([action.dest, *action.option_strings]).lower()
        assert "host" not in names and "bind" not in names and "address" not in names, names


# --- US3.3: one run at a time; status and stream after a service restart ---------------------------


def test_AC3_3_4_status_reads_running_with_the_holders_run_id(tmp_project_dirs):
    _run_folder(tmp_project_dirs.outputs, ACTIVE_RUN)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="worker")
    try:
        with _client(tmp_project_dirs) as client:
            first = client.get(f"{API}/status")
        # A fresh service instance (the service restarted) still sees the same run.
        with _client(tmp_project_dirs) as client:
            again = client.get(f"{API}/status")
    finally:
        held.release()

    for response in (first, again):
        assert response.status_code == 200, response.text
        body = response.json()
        assert STATUS_KEYS <= set(body)
        assert body["status"] == "RUNNING"
        assert body["run_id"] == ACTIVE_RUN


def test_AC3_3_4_metrics_stream_resumes_after_a_service_restart(tmp_project_dirs):
    folder = _run_folder(tmp_project_dirs.outputs, ACTIVE_RUN)
    partial_head = '{"v": 1, "step": 4, "total_steps": 10, '
    partial_tail = '"loss": 0.25, "learning_rate": 0.0002, "elapsed_s": 4.0, "eta_s": 6.0}\n'
    metrics = _write_metrics(folder, [1, 2, 3], partial=partial_head)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="worker")
    try:
        # The first service instance, before the restart.
        with _client(tmp_project_dirs) as client:
            assert client.get(f"{API}/status").json()["status"] == "RUNNING"

        # A fresh instance, created after the lines were written.
        with _client(tmp_project_dirs) as client:
            status = client.get(f"{API}/status").json()
            assert status["status"] == "RUNNING" and status["run_id"] == ACTIVE_RUN

            info, events, done = _read_events(client, want=lambda evs: len(_metric_events(evs)) >= 4)
            assert _wait_until(lambda: len(_metric_events(events)) >= 3 or done.is_set(), 10.0), info
            assert info.get("status") == 200, info
            assert info.get("content_type", "").startswith("text/event-stream"), info
            seen = _metric_events(events)
            assert [json.loads(e["data"])["step"] for e in seen[:3]] == [1, 2, 3], events
            # The half-written fourth line is never sent as data.
            assert all(json.loads(e["data"])["step"] != 4 for e in seen), events

            # Completing the line sends it as the next event (live, within the 5-second budget).
            with metrics.open("a", encoding="utf-8") as f:
                f.write(partial_tail)
            assert done.wait(10.0), (info, events)
            seen = _metric_events(events)
            steps = [json.loads(e["data"])["step"] for e in seen]
            assert steps == [1, 2, 3, 4], events
            for event in seen:
                data = json.loads(event["data"])
                assert data["run_id"] == ACTIVE_RUN
                assert event.get("id", "").startswith(f"{ACTIVE_RUN}:"), event
            assert len({e["id"] for e in seen}) == 4
            assert any(e.get("retry") == "3000" for e in events), events

            # Reconnecting with Last-Event-ID resends only the lines after it.
            first_id = seen[0]["id"]
            info2, events2, done2 = _read_events(
                client,
                headers={"Last-Event-ID": first_id},
                want=lambda evs: len(_metric_events(evs)) >= 3,
            )
            assert done2.wait(10.0), (info2, events2)
            assert [json.loads(e["data"])["step"] for e in _metric_events(events2)] == [2, 3, 4], events2
    finally:
        held.release()


def test_AC3_3_4_metrics_endpoint_returns_complete_lines_after_a_line_number(tmp_project_dirs):
    folder = _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-2")
    _write_metrics(folder, [1, 2, 3], partial='{"v": 1, "step": 4')
    _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-3")  # no metrics.jsonl yet

    with _client(tmp_project_dirs) as client:
        everything = client.get(f"{API}/runs/q06-sft-dev-2/metrics")
        after_two = client.get(f"{API}/runs/q06-sft-dev-2/metrics", params={"after": 2})
        empty = client.get(f"{API}/runs/q06-sft-dev-3/metrics")

    assert everything.status_code == 200, everything.text
    body = everything.json()
    assert [line["step"] for line in body["lines"]] == [1, 2, 3]
    assert body["next"] == 3
    body = after_two.json()
    assert [line["step"] for line in body["lines"]] == [3]
    assert body["next"] == 3
    assert empty.status_code == 200, empty.text
    assert empty.json()["lines"] == []


def test_AC3_3_1_confirm_while_a_run_holds_the_lock_queues_the_run(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="terminal")
    try:
        with _client(tmp_project_dirs) as client:
            confirmed = _check_and_confirm(client, {"method": "base", "split": "dev", "limit": 5})
            entries = _queue_entries(client)
            status = client.get(f"{API}/status").json()
    finally:
        held.release()

    assert confirmed["state"] == "queued"
    assert isinstance(confirmed["position"], int)
    assert [e["attempt_id"] for e in entries] == [confirmed["attempt_id"]]
    assert entries[0]["position"] == confirmed["position"]
    assert status["status"] == "RUNNING" and status["run_id"] == ACTIVE_RUN


# --- C6 start, queue, stop and finalists endpoints (US3.2, US3.4, US3.6, US3.7) --------------------


def test_AC3_2_1_check_returns_the_summary_and_launches_nothing(tmp_project_dirs):
    results, _ = _paths(tmp_project_dirs)
    append_row(results, _row("q06-base-dev-1"))

    with _client(tmp_project_dirs) as client:
        checked = _check(client, {"method": "base", "split": "dev", "limit": 5})
        entries = _queue_entries(client)
        status = client.get(f"{API}/status").json()

    assert CHECKED_RUN_KEYS <= set(checked), checked
    assert isinstance(checked["check_id"], str) and checked["check_id"]
    assert checked["attempt_id"] == "q06-base-dev-2"
    assert checked["model"] == Q06
    assert checked["method"] == "base"
    assert isinstance(checked["changes"], list)
    assert all(isinstance(c, str) for c in checked["changes"])
    assert checked["estimate_s"] is None or isinstance(checked["estimate_s"], int | float)
    assert isinstance(checked["over_cap"], bool)
    assert isinstance(checked["queue_position"], int)
    assert checked["needs_second_confirmation"] is False
    command = checked["command"]
    assert isinstance(command, list) and all(isinstance(part, str) for part in command)
    for token in (
        "evaluate",
        "--config",
        "--run-id",
        "q06-base-dev-2",
        "--results",
        "--started-by",
        "worker",
    ):
        assert token in command, command
    # Nothing launched, queued or written.
    assert entries == []
    assert status["status"] == "IDLE"
    assert not (tmp_project_dirs.outputs / "q06-base-dev-2" / "config.json").exists()


def test_AC3_2_4_check_rejects_an_invalid_dial_naming_the_dial_and_range(tmp_project_dirs):
    with _client(tmp_project_dirs) as client:
        response = client.post(f"{API}/runs/check", json={"method": "sft", "learning_rate": 5.0})
        entries = _queue_entries(client)

    body = _assert_error(response, 422, "invalid_dial")
    assert body.get("field") == "learning_rate", body
    assert "learning_rate" in body["message"]
    assert "1e-05" in body["message"] and "0.0005" in body["message"], body
    assert entries == []


def test_AC3_2_4_confirm_without_a_matching_check_launches_nothing(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    with _client(tmp_project_dirs) as client:
        response = client.post(f"{API}/runs/confirm", json={"check_id": "no-such-check"})
        entries = _queue_entries(client)

    assert response.status_code == 404, response.text
    body = response.json()
    assert body.get("error") in ("not_found", "check_expired"), body
    assert isinstance(body.get("message"), str) and body["message"]
    assert entries == []


def test_AC3_7_3_confirm_with_ten_waiting_is_refused_as_queue_full(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="terminal")
    try:
        with _client(tmp_project_dirs) as client:
            dials = {"method": "base", "split": "dev", "limit": 5}
            for _ in range(9):
                _check_and_confirm(client, dials)
            extra = _check(client, {**dials, "model": Q17})  # checked while 9 wait
            _check_and_confirm(client, dials)  # the tenth
            response = client.post(f"{API}/runs/confirm", json={"check_id": extra["check_id"]})
            entries = _queue_entries(client)
    finally:
        held.release()

    body = _assert_error(response, 409, "queue_full")
    assert body["message"] == "The queue is full (10 waiting)"
    assert len(entries) == 10
    assert extra["attempt_id"] not in [e["attempt_id"] for e in entries]


def test_AC3_7_4_delete_queue_entry_removes_the_waiting_run(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="terminal")
    try:
        with _client(tmp_project_dirs) as client:
            ids = [
                _check_and_confirm(client, {"method": "base", "split": "dev", "limit": 5})["attempt_id"]
                for _ in range(3)
            ]
            removed = client.delete(f"{API}/queue/{ids[1]}")
            entries = _queue_entries(client)
            missing = client.delete(f"{API}/queue/q06-base-dev-99")
    finally:
        held.release()

    assert removed.status_code == 204, removed.text
    assert [e["attempt_id"] for e in entries] == [ids[0], ids[2]]
    positions = [e["position"] for e in entries]
    assert positions[1] == positions[0] + 1  # the later run moved up
    _assert_error(missing, 404, "not_found")


def test_AC3_7_5_queue_survives_a_service_restart(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="terminal")
    try:
        with _client(tmp_project_dirs) as client:
            for _ in range(2):
                _check_and_confirm(client, {"method": "base", "split": "dev", "limit": 5})
            before = _queue_entries(client)
        with _client(tmp_project_dirs) as client:
            after = _queue_entries(client)
    finally:
        held.release()

    assert len(before) == 2
    assert [(e["attempt_id"], e["position"]) for e in after] == [
        (e["attempt_id"], e["position"]) for e in before
    ]


def test_AC3_4_3_stop_when_idle_says_no_run_is_active(tmp_project_dirs):
    with _client(tmp_project_dirs) as client:
        before = sorted(str(p) for p in tmp_project_dirs.outputs.rglob("*"))
        response = client.post(f"{API}/stop")
        after = sorted(str(p) for p in tmp_project_dirs.outputs.rglob("*"))
        status = client.get(f"{API}/status").json()

    body = _assert_error(response, 409, "no_active_run")
    assert body["message"] == "No run is active"
    assert after == before
    assert status["status"] == "IDLE"


def test_AC3_4_1_stop_ends_the_active_run(tmp_project_dirs, tmp_path):
    script = tmp_path / "stub_run.py"
    script.write_text(STUB_RUN, encoding="utf-8")
    run_id = "q06-sft-dev-5"
    ready = tmp_project_dirs.outputs / run_id / "ready"
    proc = subprocess.Popen([sys.executable, str(script), run_id], env=os.environ.copy())
    try:
        assert _wait_until(ready.exists, 30.0), "the stub run did not start"
        with _client(tmp_project_dirs) as client:
            assert client.get(f"{API}/status").json()["run_id"] == run_id
            response = client.post(f"{API}/stop")
            assert response.status_code == 200, response.text
            assert STATUS_KEYS <= set(response.json())
            assert proc.wait(timeout=40) == 130
            status = client.get(f"{API}/status").json()
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGKILL)
            proc.wait()

    assert status["status"] != "RUNNING"
    stopped = json.loads((tmp_project_dirs.outputs / run_id / "status.json").read_text(encoding="utf-8"))
    assert stopped["status"] == "stopped"
    assert (tmp_project_dirs.outputs / run_id / "metrics.jsonl").read_text(encoding="utf-8").strip()


def test_AC3_6_1_finalists_mark_list_and_unmark(tmp_project_dirs):
    results, finalists = _paths(tmp_project_dirs)
    append_row(results, _row("q06-sft-dev-1", method="sft", value=0.41))
    append_row(results, _row("q06-sft-dev-2", method="sft", value=0.43))

    with _client(tmp_project_dirs) as client:
        assert _finalist_ids(client) == []
        marked = client.put(f"{API}/finalists/q06-sft-dev-2")
        listed = _finalist_ids(client)
        saved = json.loads(finalists.read_text(encoding="utf-8"))
        unknown = client.put(f"{API}/finalists/q06-sft-dev-9")
        unmarked = client.delete(f"{API}/finalists/q06-sft-dev-2")
        after = _finalist_ids(client)

    assert marked.status_code in (200, 204), marked.text
    assert listed == ["q06-sft-dev-2"]
    assert saved["v"] == 1
    assert [entry["run_id"] for entry in saved["finalists"]] == ["q06-sft-dev-2"]
    assert isinstance(saved["finalists"][0]["marked_at"], str)
    _assert_error(unknown, 404, "not_found")
    assert unmarked.status_code in (200, 204), unmarked.text
    assert after == []
    assert json.loads(finalists.read_text(encoding="utf-8"))["finalists"] == []


def test_AC3_6_5_unreadable_finalists_file_is_an_error_naming_the_file(tmp_project_dirs):
    _, finalists = _paths(tmp_project_dirs)
    finalists.write_text("{not json", encoding="utf-8")

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/finalists")

    body = _assert_error(response, 500, "finalists_unreadable")
    assert str(finalists) in body.get("file", ""), body


def test_AC3_6_2_test_split_check_needs_a_finalist_and_a_second_confirmation(tmp_project_dirs, monkeypatch):
    _stub_build_argv(monkeypatch)
    results, _ = _paths(tmp_project_dirs)
    append_row(results, _row("q06-sft-dev-1", method="sft", value=0.41))
    _run_folder(tmp_project_dirs.outputs, "q06-sft-dev-1", method="sft")
    adapter = tmp_project_dirs.checkpoints / "q06-sft-dev-1"
    adapter.mkdir()
    dials = {"method": "best", "split": "test", "adapter_path": str(adapter)}
    held = GpuLock()
    held.acquire(ACTIVE_RUN, started_by="terminal")
    try:
        with _client(tmp_project_dirs) as client:
            refused = client.post(f"{API}/runs/check", json=dials)
            assert client.put(f"{API}/finalists/q06-sft-dev-1").status_code in (200, 204)
            checked = _check(client, dials)
            first = client.post(f"{API}/runs/confirm", json={"check_id": checked["check_id"]})
            queued_after_first = _queue_entries(client)
            confirmed = _check_and_confirm(client, dials, second_confirmation=True)
            entries = _queue_entries(client)
    finally:
        held.release()

    _assert_error(refused, 409, "not_finalist")
    assert checked["needs_second_confirmation"] is True
    assert first.status_code >= 400, first.text  # AC3.6.3: no launch without the second confirmation
    assert queued_after_first == []
    assert confirmed["state"] == "queued"
    assert [e["attempt_id"] for e in entries] == [confirmed["attempt_id"]]


# --- ADR-006: the service never imports training code ----------------------------------------------


def test_AC3_1_5_service_starts_without_loading_training_code(tmp_path):
    code = textwrap.dedent(
        """
        import json, sys
        from pathlib import Path

        import gsm8k.service.app as app_module

        tmp = Path(sys.argv[1])
        app_module.create_app(results=tmp / "runs.csv", finalists=tmp / "finalists.json", outputs=tmp / "out")
        print(json.dumps(sorted(sys.modules)))
        """
    )
    (tmp_path / "out").mkdir()
    proc = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
        env={**os.environ, "GSM8K_OUTPUTS_DIR": str(tmp_path / "out")},
    )
    assert proc.returncode == 0, proc.stderr
    modules = json.loads(proc.stdout.strip().splitlines()[-1])
    loaded = [
        name
        for name in modules
        if name.split(".")[0] in FORBIDDEN_TOP_LEVEL
        or any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN_GSM8K)
    ]
    assert loaded == [], loaded
