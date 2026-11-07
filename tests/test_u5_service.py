"""Service side of the website, u5-website part W0 (C6 as changed 2026-11-07).

The run list gains ``data``, ``adapter_run``, ``gain`` and ``started_at``; ``test_accuracy`` is joined
across runs (a tuned run's test score sits on the ``best`` run that names it in ``adapter_run``); a run
folder whose id waits in the queue lists as ``queued``; and ``GET /api/v1/dials`` serves the eleven
Training Dials. The tests are named after the website criteria whose service side they check
(AC4.3.1 scores, AC4.5.5 past runs, AC4.6.1 dials; construction/batch-4.md, Part W0).

Every test builds its own data in temp folders (`tmp_project_dirs`) with a temp run log and a temp
finalists file; nothing touches the project's outputs/, results/runs.csv or results/finalists.json.
FastAPI's `TestClient` binds no port; no model loads; everything runs on the CPU. The run service
modules are imported inside each test, so a missing piece fails each test on its own.
"""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gsm8k.run_config import RunConfig, to_dict
from gsm8k.run_records.folder import write_status
from gsm8k.run_records.lock import GpuLock, lock_path, read_lock
from gsm8k.run_records.log import RunRow, append_row

API = "/api/v1"
Q06 = "Qwen/Qwen3-0.6B-Base"
Q17 = "Qwen/Qwen3-1.7B-Base"
ISO_TO_THE_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|\+00:00)$")
BATCH3_RUN_FIELDS = {
    "run_id",
    "model",
    "method",
    "dev_accuracy",
    "test_accuracy",
    "minutes",
    "date",
    "status",
    "finalist",
}
NEW_RUN_FIELDS = {"data", "adapter_run", "gain", "started_at"}
DIAL_ORDER = [
    "model",
    "learning_rate",
    "epochs",
    "lora_rank",
    "lora_alpha",
    "max_seq_len",
    "train_examples",
    "batch_size",
    "warmup_ratio",
    "seed",
    "answer_format",
]
DIAL_KEYS = {"name", "label", "kind", "options", "min", "max", "allow_all", "default", "help"}


# --- helpers ---------------------------------------------------------------------------------------


def _row(
    run_id,
    *,
    model=Q06,
    method="base",
    data="gsm8k-dev",
    value=0.35,
    minutes=12.5,
    date="2026-11-01T20:00:00Z",
    metric="accuracy",
    adapter_run="",
):
    return RunRow(
        date=date,
        run_id=run_id,
        model=model,
        method=method,
        data=data,
        metric=metric,
        value=value,
        minutes=minutes,
        config_hash="0" * 64,
        adapter_run=adapter_run,
    )


def _finalists_path(dirs) -> Path:
    return dirs.results.parent / "finalists.json"


def _client(dirs):
    from fastapi.testclient import TestClient

    from gsm8k.service.app import create_app

    app = create_app(results=dirs.results, finalists=_finalists_path(dirs), outputs=dirs.outputs)
    return TestClient(app)


def _run_folder(outputs: Path, run_id: str, *, model=Q06, method="sft", split="dev") -> Path:
    """A run folder with its config.json (C2), as the launcher writes it before the run starts."""
    folder = outputs / run_id
    folder.mkdir(parents=True, exist_ok=True)
    cfg = RunConfig(run_id=run_id, model=model, method=method, split=split)
    (folder / "config.json").write_text(json.dumps(to_dict(cfg), indent=2) + "\n", encoding="utf-8")
    return folder


def _by_id(runs) -> dict:
    ids = [run.run_id for run in runs]
    assert len(ids) == len(set(ids)), f"a run appears more than once: {ids}"
    return {run.run_id: run for run in runs}


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def _scored_log(results: Path) -> None:
    """A run log with two models, baselines, tuned runs and their test-split rows (file order = date
    order). Q06: base dev 0.30 then 0.32 (the latest is the baseline), sft dev 0.41 and 0.50, test rows
    on base and best runs. Q17: one sft dev run, no baseline."""
    rows = [
        _row("q06-base-dev-1", value=0.30, minutes=40.0, date="2026-11-01T10:00:00Z"),
        _row("q06-base-test-1", data="gsm8k-test", value=0.33, minutes=90.0, date="2026-11-01T12:00:00Z"),
        _row("q06-sft-dev-1", method="sft", value=0.41, minutes=95.0, date="2026-11-02T10:00:00Z"),
        _row("q06-base-dev-2", value=0.32, minutes=41.0, date="2026-11-02T12:00:00Z"),
        _row(
            "q06-best-test-1",
            method="best",
            data="gsm8k-test",
            value=0.38,
            minutes=60.0,
            date="2026-11-03T10:00:00Z",
            adapter_run="q06-sft-dev-1",
        ),
        _row("q06-base-test-2", data="gsm8k-test", value=0.34, minutes=91.0, date="2026-11-03T12:00:00Z"),
        _row(
            "q06-best-test-2",
            method="best",
            data="gsm8k-test",
            value=0.40,
            minutes=61.0,
            date="2026-11-04T10:00:00Z",
            adapter_run="q06-sft-dev-1",
        ),
        # Later rows naming the same adapter that are not gsm8k-test accuracy never count as its test score.
        _row(
            "q06-best-harness-1",
            method="best",
            data="gsm8k-test-harness",
            metric="harness_flexible_accuracy",
            value=0.90,
            minutes=70.0,
            date="2026-11-04T12:00:00Z",
            adapter_run="q06-sft-dev-1",
        ),
        _row(
            "q06-best-gsmplus-1",
            method="best",
            data="gsmplus-testmini",
            value=0.80,
            minutes=30.0,
            date="2026-11-04T14:00:00Z",
            adapter_run="q06-sft-dev-1",
        ),
        _row("q06-sft-dev-2", method="sft", value=0.50, minutes=100.0, date="2026-11-05T10:00:00Z"),
        # Another model's base test row never reaches the Q06 runs.
        _row(
            "q17-base-test-1",
            model=Q17,
            data="gsm8k-test",
            value=0.55,
            minutes=120.0,
            date="2026-11-05T12:00:00Z",
        ),
        _row(
            "q17-sft-dev-1", model=Q17, method="sft", value=0.66, minutes=150.0, date="2026-11-06T10:00:00Z"
        ),
    ]
    for row in rows:
        append_row(results, row)


# --- AC4.3.1 scores: data, adapter_run, joined test accuracy, gain ---------------------------------


def test_AC4_3_1_service_gain_against_model_baseline(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    _scored_log(tmp_project_dirs.results)
    runs, skipped = list_runs(tmp_project_dirs.results, tmp_project_dirs.outputs)

    assert skipped == 0
    by_id = _by_id(runs)
    # Gain = dev accuracy minus the dev accuracy of the model's latest base gsm8k-dev run (0.32).
    assert by_id["q06-sft-dev-1"].gain == pytest.approx(0.41 - 0.32)
    assert by_id["q06-sft-dev-2"].gain == pytest.approx(0.50 - 0.32)
    # The baseline itself has no gain.
    assert by_id["q06-base-dev-2"].gain is None
    # Runs without a dev score have no gain.
    for run_id in ("q06-base-test-1", "q06-best-test-2", "q06-best-harness-1", "q06-best-gsmplus-1"):
        assert by_id[run_id].gain is None, run_id
    # A model without a base dev run has no baseline to compare with.
    assert by_id["q17-sft-dev-1"].gain is None


def test_AC4_3_1_service_data_and_adapter_run_come_from_the_rows(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    _scored_log(tmp_project_dirs.results)
    by_id = _by_id(list_runs(tmp_project_dirs.results, tmp_project_dirs.outputs)[0])

    assert by_id["q06-base-dev-1"].data == "gsm8k-dev"
    assert by_id["q06-best-test-2"].data == "gsm8k-test"
    assert by_id["q06-best-harness-1"].data == "gsm8k-test-harness"
    assert by_id["q06-best-gsmplus-1"].data == "gsmplus-testmini"
    assert by_id["q06-best-test-2"].adapter_run == "q06-sft-dev-1"
    assert by_id["q06-best-gsmplus-1"].adapter_run == "q06-sft-dev-1"
    # An empty C1 adapter_run means none.
    assert not by_id["q06-base-dev-1"].adapter_run
    assert not by_id["q06-sft-dev-1"].adapter_run


def test_AC4_3_1_service_tuned_run_takes_latest_test_row_naming_it(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    _scored_log(tmp_project_dirs.results)
    by_id = _by_id(list_runs(tmp_project_dirs.results, tmp_project_dirs.outputs)[0])

    tuned = by_id["q06-sft-dev-1"]
    assert tuned.dev_accuracy == pytest.approx(0.41)
    # The latest gsm8k-test accuracy row whose adapter_run is this run (q06-best-test-2), not the
    # earlier one, the harness row or the generalisation row.
    assert tuned.test_accuracy == pytest.approx(0.40)
    # A tuned run that no test row names has no test score.
    assert by_id["q06-sft-dev-2"].test_accuracy is None
    assert by_id["q17-sft-dev-1"].test_accuracy is None


def test_AC4_3_1_service_base_dev_run_takes_its_models_base_test_row(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results = tmp_project_dirs.results
    _scored_log(results)
    # A base test row with an adapter_run is not the model's base test score.
    append_row(
        results,
        _row(
            "q06-base-test-3",
            data="gsm8k-test",
            value=0.99,
            minutes=90.0,
            date="2026-11-06T12:00:00Z",
            adapter_run="q06-sft-dev-2",
        ),
    )
    # A Q17 base dev run whose model has no base test row.
    append_row(results, _row("q17-base-dev-1", model=Q17, value=0.60, date="2026-11-06T14:00:00Z"))
    by_id = _by_id(list_runs(results, tmp_project_dirs.outputs)[0])

    # The latest base gsm8k-test row of Q06 with an empty adapter_run (q06-base-test-2), never Q17's.
    assert by_id["q06-base-dev-2"].test_accuracy == pytest.approx(0.34)
    assert by_id["q06-base-dev-1"].test_accuracy == pytest.approx(0.34)
    # Q17 has a base gsm8k-test row (q17-base-test-1), so its base dev run takes it.
    assert by_id["q17-base-dev-1"].test_accuracy == pytest.approx(0.55)


def test_AC4_3_1_service_base_dev_run_without_a_base_test_row_has_no_test_score(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results = tmp_project_dirs.results
    append_row(results, _row("q17-base-dev-1", model=Q17, value=0.60, date="2026-11-01T10:00:00Z"))
    append_row(
        results,
        _row("q06-base-test-1", data="gsm8k-test", value=0.33, minutes=90.0, date="2026-11-01T12:00:00Z"),
    )
    by_id = _by_id(list_runs(results, tmp_project_dirs.outputs)[0])

    assert by_id["q17-base-dev-1"].test_accuracy is None
    assert by_id["q17-base-dev-1"].gain is None


def test_AC4_3_1_service_own_test_row_wins_over_a_joined_one(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results = tmp_project_dirs.results
    # A base run with its own dev and test rows (first in the file).
    append_row(results, _row("q06-base-dev-7", value=0.31, date="2026-10-31T10:00:00Z"))
    append_row(results, _row("q06-base-dev-7", data="gsm8k-test", value=0.36, date="2026-10-31T11:00:00Z"))
    # A base dev run without its own test row, then the model's latest base test row.
    append_row(results, _row("q06-base-dev-1", value=0.30, date="2026-11-01T10:00:00Z"))
    append_row(results, _row("q06-base-test-1", data="gsm8k-test", value=0.33, date="2026-11-01T11:00:00Z"))
    # A tuned run with its own dev and test rows; a later best row names it as adapter.
    append_row(results, _row("q06-sft-dev-5", method="sft", value=0.50, date="2026-11-02T10:00:00Z"))
    append_row(
        results,
        _row("q06-sft-dev-5", method="sft", data="gsm8k-test", value=0.45, date="2026-11-02T11:00:00Z"),
    )
    append_row(
        results,
        _row(
            "q06-best-test-1",
            method="best",
            data="gsm8k-test",
            value=0.47,
            date="2026-11-03T10:00:00Z",
            adapter_run="q06-sft-dev-5",
        ),
    )
    # A tuned run without its own test row takes the joined one.
    append_row(results, _row("q06-sft-dev-6", method="sft", value=0.52, date="2026-11-04T10:00:00Z"))
    append_row(
        results,
        _row(
            "q06-best-test-2",
            method="best",
            data="gsm8k-test",
            value=0.49,
            date="2026-11-04T12:00:00Z",
            adapter_run="q06-sft-dev-6",
        ),
    )
    by_id = _by_id(list_runs(results, tmp_project_dirs.outputs)[0])

    # Own test rows win.
    assert by_id["q06-sft-dev-5"].test_accuracy == pytest.approx(0.45)
    assert by_id["q06-base-dev-7"].test_accuracy == pytest.approx(0.36)
    assert by_id["q06-base-test-1"].test_accuracy == pytest.approx(0.33)
    # Without one, the joined score.
    assert by_id["q06-sft-dev-6"].test_accuracy == pytest.approx(0.49)
    assert by_id["q06-base-dev-1"].test_accuracy == pytest.approx(0.33)


def test_AC4_3_1_service_runs_endpoint_carries_the_new_fields(tmp_project_dirs):
    from gsm8k.run_control import finalists

    _scored_log(tmp_project_dirs.results)
    finalists.mark(_finalists_path(tmp_project_dirs), "q06-sft-dev-1", tmp_project_dirs.results)

    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["skipped_rows"] == 0
    by_id = {run["run_id"]: run for run in body["runs"]}
    # Every batch-3 field stays; the four new ones are on every item.
    for run in body["runs"]:
        assert BATCH3_RUN_FIELDS | NEW_RUN_FIELDS <= set(run), run
    tuned = by_id["q06-sft-dev-1"]
    assert tuned["model"] == Q06 and tuned["method"] == "sft"
    assert tuned["data"] == "gsm8k-dev"
    assert tuned["dev_accuracy"] == pytest.approx(0.41)
    assert tuned["test_accuracy"] == pytest.approx(0.40)
    assert tuned["gain"] == pytest.approx(0.09)
    assert tuned["minutes"] == pytest.approx(95.0)
    assert tuned["date"] == "2026-11-02T10:00:00Z"
    assert tuned["status"] == "finished"
    assert tuned["finalist"] is True
    assert _utc(tuned["started_at"]) == _utc("2026-11-02T10:00:00Z") - timedelta(minutes=95.0)
    best = by_id["q06-best-test-2"]
    assert best["adapter_run"] == "q06-sft-dev-1"
    assert best["data"] == "gsm8k-test"
    assert best["test_accuracy"] == pytest.approx(0.40)
    assert best["gain"] is None
    assert best["finalist"] is False
    baseline = by_id["q06-base-dev-2"]
    assert baseline["gain"] is None
    assert baseline["test_accuracy"] == pytest.approx(0.34)
    assert by_id["q17-sft-dev-1"]["gain"] is None


# --- AC4.5.5 past runs: start time and queued status ------------------------------------------------


def test_AC4_5_5_service_started_at_is_row_date_minus_minutes(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results, outputs = tmp_project_dirs.results, tmp_project_dirs.outputs
    append_row(results, _row("q06-base-dev-1", minutes=12.5, date="2026-11-01T20:00:00Z"))
    append_row(results, _row("q06-sft-dev-1", method="sft", minutes=95.3, date="2026-11-02T01:10:00Z"))
    # A failed run without a row and without the lock has no start time.
    failed = _run_folder(outputs, "q06-sft-dev-2")
    write_status(failed, run_id="q06-sft-dev-2", status="failed", exit_code=1, reason="GPU out of memory")

    by_id = _by_id(list_runs(results, outputs)[0])

    base = by_id["q06-base-dev-1"].started_at
    assert isinstance(base, str) and ISO_TO_THE_SECOND.fullmatch(base), base
    assert _utc(base) == datetime(2026, 11, 1, 19, 47, 30, tzinfo=UTC)
    sft = by_id["q06-sft-dev-1"].started_at
    assert isinstance(sft, str) and ISO_TO_THE_SECOND.fullmatch(sft), sft
    # 95.3 minutes = 1 h 35 min 18 s before 01:10:00.
    assert _utc(sft) == datetime(2026, 11, 1, 23, 34, 42, tzinfo=UTC)
    assert by_id["q06-sft-dev-2"].status == "failed"
    assert by_id["q06-sft-dev-2"].started_at is None


def test_AC4_5_5_service_active_run_takes_the_locks_started_at(tmp_project_dirs):
    from gsm8k.run_control.runs import list_runs

    results, outputs = tmp_project_dirs.results, tmp_project_dirs.outputs
    append_row(results, _row("q06-base-dev-1", minutes=12.5, date="2026-11-01T20:00:00Z"))
    _run_folder(outputs, "q06-sft-dev-1")
    held = GpuLock()
    held.acquire("q06-sft-dev-1", started_by="worker")
    try:
        started = read_lock(lock_path())["started_at"]
        runs, _ = list_runs(results, outputs)
        with _client(tmp_project_dirs) as client:
            response = client.get(f"{API}/runs")
    finally:
        held.release()

    active = _by_id(runs)["q06-sft-dev-1"]
    assert active.status == "running"
    assert active.started_at == started
    assert response.status_code == 200, response.text
    item = {run["run_id"]: run for run in response.json()["runs"]}["q06-sft-dev-1"]
    assert item["status"] == "running"
    assert item["started_at"] == started


def test_AC4_5_5_service_queued_run_folder_lists_as_queued(tmp_project_dirs):
    from gsm8k.run_control import queue as run_queue
    from gsm8k.run_control.runs import list_runs

    results, outputs = tmp_project_dirs.results, tmp_project_dirs.outputs
    append_row(results, _row("q06-base-dev-1"))
    folder = _run_folder(outputs, "q06-sft-dev-3")
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    run_queue.add("q06-sft-dev-3", config, kind="train", outputs=outputs)
    # A folder of a run that is not waiting and has no status stays without the queued word.
    _run_folder(outputs, "q06-sft-dev-4")

    by_id = _by_id(list_runs(results, outputs)[0])
    with _client(tmp_project_dirs) as client:
        response = client.get(f"{API}/runs")

    assert by_id["q06-sft-dev-3"].status == "queued"
    assert by_id["q06-sft-dev-3"].started_at is None
    assert by_id["q06-sft-dev-4"].status != "queued"
    assert by_id["q06-base-dev-1"].status == "finished"
    assert response.status_code == 200, response.text
    items = {run["run_id"]: run for run in response.json()["runs"]}
    assert items["q06-sft-dev-3"]["status"] == "queued"
    assert items["q06-sft-dev-3"]["started_at"] is None


# --- AC4.6.1 dials: the Training Dials table from the service ----------------------------------------


def _dials(dirs) -> list[dict]:
    with _client(dirs) as client:
        response = client.get(f"{API}/dials")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"dials"}, body
    return body["dials"]


def test_AC4_6_1_service_dials_lists_eleven_dials_in_table_order(tmp_project_dirs):
    dials = _dials(tmp_project_dirs)

    assert [dial["name"] for dial in dials] == DIAL_ORDER
    for dial in dials:
        assert set(dial) == DIAL_KEYS, dial
        assert dial["kind"] in ("select", "number", "integer"), dial
        assert isinstance(dial["label"], str) and dial["label"].strip(), dial
        assert isinstance(dial["help"], str) and dial["help"].strip(), dial
        assert isinstance(dial["allow_all"], bool), dial
        if dial["kind"] == "select":
            assert isinstance(dial["options"], list) and dial["options"], dial
            assert dial["default"] in dial["options"], dial
        else:
            assert dial["options"] is None, dial
            assert dial["min"] is not None and dial["max"] is not None, dial
    # Reading the dials writes nothing.
    assert list(tmp_project_dirs.outputs.iterdir()) == []
    assert not tmp_project_dirs.results.exists()


def test_AC4_6_1_service_dials_defaults_and_bounds_match_the_table(tmp_project_dirs):
    from gsm8k import run_config

    by_name = {dial["name"]: dial for dial in _dials(tmp_project_dirs)}
    defaults = RunConfig(run_id="unset")

    def spec(name):
        dial = by_name[name]
        return dial["kind"], dial["options"], dial["min"], dial["max"], dial["allow_all"], dial["default"]

    assert spec("model") == ("select", list(run_config.MODELS), None, None, False, run_config.DEFAULT_MODEL)
    assert by_name["model"]["options"] == [Q06, Q17]
    assert spec("learning_rate")[0] == "number"
    assert by_name["learning_rate"]["min"] == pytest.approx(1e-5)
    assert by_name["learning_rate"]["max"] == pytest.approx(5e-4)
    assert by_name["learning_rate"]["default"] == pytest.approx(2e-4)
    assert by_name["learning_rate"]["allow_all"] is False
    assert "1e-5" in by_name["learning_rate"]["help"] and "5e-4" in by_name["learning_rate"]["help"]
    assert spec("epochs") == ("integer", None, 1, 3, False, 1)
    assert spec("lora_rank") == ("select", [4, 8, 16, 32, 64], None, None, False, 16)
    assert spec("lora_alpha") == ("integer", None, 1, 128, False, 32)
    assert spec("max_seq_len") == ("integer", None, 256, 1024, False, 512)
    assert spec("train_examples") == ("integer", None, 50, 6973, True, "all")
    assert spec("batch_size") == ("integer", None, 1, 16, False, 4)
    assert spec("warmup_ratio")[0] == "number"
    assert by_name["warmup_ratio"]["min"] == pytest.approx(0.0)
    assert by_name["warmup_ratio"]["max"] == pytest.approx(0.2)
    assert by_name["warmup_ratio"]["default"] == pytest.approx(0.03)
    assert by_name["warmup_ratio"]["allow_all"] is False
    assert spec("seed") == ("integer", None, 0, 2**31 - 1, False, 42)
    assert spec("answer_format") == ("select", ["step-by-step", "terse"], None, None, False, "step-by-step")
    # Every default is the run_config default, so a run started with untouched dials hashes the same.
    for name in DIAL_ORDER:
        assert by_name[name]["default"] == getattr(defaults, name), name
