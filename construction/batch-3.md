# batch-3: u4-run-service

Branch `wip/batch-3`. `test_command`: `scripts/check.sh` (Ruff, then pytest with coverage on `src/gsm8k`, failing under 80%, on the CPU through `scripts/in-env.sh`). Every project tool runs through `scripts/in-env.sh`.

Why u4 alone: u7-grpo, u8-tuning and u9-ablations are ready by their dependencies, but stories.md Conventions (Priority) says the Could Have groups 7-9 are built only after everything else works (Q2), and stories.md outranks the unit files. Order: batch-3 u4, then u5-website and u6-final-and-report, then u7, u8, u9.

## Spec to read

`S` = `aidlc/spaces/default/intents/261030-gsm8k-finetune`.
- Criteria: `S/inception/user-stories/stories.md` US3.1-US3.7 (AC3.1.1-AC3.7.6) and its Conventions.
- Requirements: `S/inception/requirements-analysis/requirements.md` FR3.1-FR3.7 (FR3.4 as changed 2026-10-31: the queue), NFR6 (127.0.0.1 only), NFR8, NFR10.
- Design: `S/inception/domain-design/components.md` (RunControl, RunService, RunRecords queue and finalists), `S/inception/domain-design/decisions.md` (ADR-004, ADR-006: the service never imports training code; launches go through `gsm8k` commands as processes; ADR-008).
- Contracts: `S/inception/contract-design/contract-summary.md` C1, C2, C3 (lock and queue), C4 (finalists), C5 (worker launch: argument list, `--config`, `--started-by worker`, exit codes, SIGTERM then SIGKILL after 30 s), C6 (HTTP API `/api/v1`), C7 (Server-Sent Events).
- Built so far (reuse, do not break): `src/gsm8k/`, `construction/batch-1.md` and `construction/batch-2.md` Interfaces. Useful: `run_records.lock` (`GpuLock`, `read_lock`, `is_free`), `run_records.log` (`read_rows` with skip count), `run_records.folder`, `run_records.paths` (`outputs_root`, `run_dir`, `DEFAULT_RESULTS`), `run_config` (`check_dials`, `validate`, `config_hash`, `to_dict`, `from_dict`), `estimates`, `training.loop.read_metrics` (complete metrics lines only), `prune.read_finalists`, `cli.ATTEMPT_ID_PATTERN`.

## Criteria

AC3.1.1-AC3.1.5, AC3.2.1-AC3.2.5, AC3.3.1-AC3.3.4, AC3.4.1-AC3.4.3, AC3.5.1-AC3.5.3, AC3.6.1-AC3.6.5, AC3.7.1-AC3.7.6. No `[manual]` criterion and no long run in u4.

## Rules for every part

- Tests run on the CPU and never load a model. A launched run in tests is a stub: a tiny Python script (written by the test into its temp folder) that takes the `gsm8k` arguments, holds the GPU lock through `gsm8k.run_records.lock.GpuLock` like a real run, writes metrics lines and a status file, and sleeps or exits as the test needs. The launcher's command builder is a module attribute the tests can point at that stub; the real default is `[sys.executable, "-m", "gsm8k", <command>, ...]`.
- No test touches the project's `outputs/`, `checkpoints/`, `results/runs.csv` or `results/finalists.json`: use `tmp_project_dirs` and pass explicit temp results and finalists paths. No test binds a real port except AC3.1.5's check of the bind address (bind to 127.0.0.1 on port 0 or inspect the configured host).
- Every test is named by its criterion ID (`test_AC3_7_3_...`). Ruff-clean, snake_case, English. Full module-path imports; subpackage `__init__.py` files stay empty.
- ADR-006: nothing under `gsm8k.run_control` or `gsm8k.service` imports `gsm8k.training`, `gsm8k.train_cmd`, `gsm8k.evaluation`, `gsm8k.harness`, torch, transformers, peft, trl or lm_eval (a test checks this by importing the service in a subprocess and listing `sys.modules`).
- Process launches are argument lists, never a shell string (`subprocess.Popen(argv, shell=False, start_new_session=True)`), so a run outlives the service and the browser (AC3.2.2, AC3.2.5).
- Command modules expose `register(subparsers)` and set `func`; the lead adds them to `COMMAND_MODULES` in `cli.py`.

## Interfaces (the contract between the parts)

Part H1, runs, status and finalists (`gsm8k.run_control`):
- `runs.py`: `@dataclass RunSummary(run_id, model, method, dev_accuracy: float | None, test_accuracy: float | None, minutes: float | None, date: str | None, status: str | None)`; `list_runs(results: Path, outputs: Path | None = None) -> tuple[list[RunSummary], int]` (every run once, from the run log rows plus run folders without a row; the int is the skipped-row count, AC3.1.1, AC3.1.3; no file -> empty list; unreadable -> `OSError` naming the file, AC3.1.4); `next_attempt_id(base_id: str, results: Path, outputs: Path | None = None, queue_ids: Iterable[str] = ()) -> str` (one more than the highest `<base id>-<n>` among rows, run folders and queued ids, AC3.2.3).
- `status.py`: `@dataclass RunStatus(state: str, run_id: str | None, reason: str | None, log_tail: list[str], started_at: str | None)` with `state` in `IDLE`, `RUNNING`, `FAILED`, `STOPPED`, `FINISHED`; `current_status(outputs: Path | None = None) -> RunStatus`: lock held -> RUNNING with the holder's run id (AC3.3.4); lock free and the lock content names a run whose folder has no `status.json` -> that run FAILED with "The run process ended without finishing" while the overall state reads IDLE (return it as `state="IDLE"` plus a `last_run` field, or a separate `last_run_status(...)`; pick one and keep it); `run_status(run_id, outputs: Path | None = None) -> RunStatus` from its `status.json`: exit code nonzero -> FAILED with the reason and the last 20 lines of `run.log` (AC3.5.1); a CUDA out-of-memory line in the log -> reason "GPU out of memory" (AC3.5.2); unreadable log -> "Run log could not be read: <path>" (AC3.5.3); status `stopped` -> STOPPED (AC3.4.1).
- `finalists.py`: `FINALISTS_DEFAULT` = `ROOT / "results" / "finalists.json"`; `list_finalists(path) -> list[str]` (no file -> [], unreadable -> `ValueError` naming the file, AC3.6.5); `mark(path, run_id, results: Path) -> None` (the run must exist in the run log; atomic write, C4 shape with `marked_at`); `unmark(path, run_id) -> None` (AC3.6.1); `check_test_split_allowed(run_id, path) -> None` raising `ValueError("Only finalists can be scored on the test split")` (AC3.6.2) or the unreadable-file error (AC3.6.5).

Part H2, queue, launch, worker and stop (`gsm8k.run_control`):
- `queue.py`: `MAX_WAITING = 10`; `queue_dir(outputs: Path | None = None) -> Path` (`outputs_root()/queue`); `@dataclass QueueEntry(position: int, attempt_id: str, config: dict, added_at: str)`; `list_queue(...) -> list[QueueEntry]` (by position, AC3.7.5); `add(attempt_id, config: dict, ...) -> QueueEntry` (raises `QueueFull("The queue is full (10 waiting)")`, AC3.7.3; C3 file name `<position:03d>-<attempt_id>.json`, atomic write); `remove(attempt_id, ...) -> None` (AC3.7.4; positions move up); `pop_head(...)`/`peek_head(...)`.
- `launch.py`: `@dataclass CheckedRun(check_id: str, attempt_id: str, model: str, method: str, command: str, argv: list[str], estimate: Estimate, changes: dict, config: dict)`; `check_run(dials: dict, *, kind: str, results: Path, finalists: Path, outputs: Path | None = None, test_confirmed: bool = False) -> CheckedRun` (`kind` is `train` or `evaluate`; `run_config.check_dials` raises `ConfigError` with the dial and range, AC3.2.4; a training kind on the test split is refused, AC3.6.4; an evaluation of the test split needs the run to be a finalist, AC3.6.2, AC3.6.5; the attempt id from `runs.next_attempt_id`; `changes` = the dials that differ from the last run of the same model and method; the estimate from `gsm8k.estimates`; the exact command shown as text); launches nothing (AC3.2.1). Checked runs are kept in memory by check id; `confirm(check_id, *, second_confirmation: bool = False) -> ConfirmResult` launches nothing when the check id is unknown (AC3.2.4) and nothing for a test-split evaluation without the second confirmation (AC3.6.3); otherwise it writes `outputs/<attempt_id>/config.json` and adds the run to the queue (the worker launches it; with an idle worker and free lock it starts at once, AC3.7.1, AC3.3.1). `build_argv(kind, attempt_id, config_path, results) -> list[str]` (module attribute; C5: `--config`, `--run-id`, `--results`, `--started-by worker`; never a shell string, AC3.2.5).
- `worker.py`: `run_worker(*, outputs: Path | None = None, results: Path | None = None, poll_seconds: float = 1.0, once: bool = False) -> int`: loop: when the lock is free and the queue has a head, launch it with `build_argv` as its own process (new session), wait until that process holds the lock (`read_lock()["run_id"] == attempt_id`) and only then remove the queue entry (C3 rule); a launch that exits 3 puts the entry back at the head and waits for the lock (AC3.7.6); runs started from the terminal are respected (AC3.7.6); after a run ends the next waiting run starts (AC3.7.2). `once=True` processes one step for tests.
- `stop.py`: `stop_active(outputs: Path | None = None, grace_seconds: float = 30.0) -> str`: no active run -> "No run is active", nothing changes (AC3.4.3); otherwise SIGTERM to the lock holder's pid, then SIGKILL after the grace period; the run writes its own `status.json` stopped/130 and no row (AC3.4.1); afterwards the lock is free (AC3.4.2).
- `worker_cmd.py`: `gsm8k worker` (calls `run_worker`).

Part H3, the HTTP service (`gsm8k.service`, RunService):
- `service/app.py`: `create_app(*, results: Path | None = None, finalists: Path | None = None, outputs: Path | None = None) -> FastAPI` with every C6 endpoint under `/api/v1` (runs list with the skipped count, run detail, metrics, status, check, confirm, queue list and remove, stop, finalists list, mark and unmark), error bodies as C6 says, and the C7 event stream of complete metrics lines (from `training.loop.read_metrics`-style reading of `metrics.jsonl`, resuming after a service restart, AC3.3.4) plus status changes. It calls only H1 and H2 functions.
- `serve_cmd.py`: `gsm8k serve [--port 8000]`, binding to 127.0.0.1 only (AC3.1.5; no option to bind elsewhere), through uvicorn.
- `Makefile` target `serve`: starts `gsm8k serve` and `gsm8k worker` as two local processes (unit-of-work.md U4).

## Parts

| Part | Criteria | Owned files | Test files |
|---|---|---|---|
| H1 runs and status | AC3.1.1, AC3.1.3, AC3.1.4, AC3.3.3, AC3.5.1, AC3.5.2, AC3.5.3, AC3.6.1, AC3.6.5 | `src/gsm8k/run_control/runs.py`, `src/gsm8k/run_control/status.py`, `src/gsm8k/run_control/finalists.py` | `tests/test_u4_runs_status.py` |
| H2 queue and worker | AC3.2.1, AC3.2.2, AC3.2.3, AC3.2.4, AC3.2.5, AC3.3.1, AC3.3.2, AC3.4.1, AC3.4.2, AC3.4.3, AC3.6.2, AC3.6.3, AC3.6.4, AC3.7.1-AC3.7.6 | `src/gsm8k/run_control/queue.py`, `src/gsm8k/run_control/launch.py`, `src/gsm8k/run_control/worker.py`, `src/gsm8k/run_control/stop.py`, `src/gsm8k/worker_cmd.py` | `tests/test_u4_queue_worker.py` |
| H3 service | AC3.1.2, AC3.1.5, AC3.3.4 | `src/gsm8k/service/app.py`, `src/gsm8k/serve_cmd.py`, `Makefile` | `tests/test_u4_service.py` |

AC3.3.2 (a terminal command refuses while a run holds the lock) is already done by `gsm8k evaluate` and `gsm8k train`; H2's test writer names a test for it that runs the command with the lock held. AC3.1.2 and AC3.3.4 are tested through the HTTP API (H3) on H1's `current_status`.

## Lead's shared files and dependencies

- `src/gsm8k/cli.py` (`COMMAND_MODULES` gains `gsm8k.worker_cmd` and `gsm8k.serve_cmd`), `src/gsm8k/run_control/__init__.py`, `src/gsm8k/service/__init__.py`, `requirements.txt`, `tests/conftest.py` (a `stub_run` helper if two parts need it).
- Dependencies: fastapi, uvicorn, httpx (for FastAPI's TestClient), pinned at install.

## Long runs

None in u4. The baseline and SFT runs queued in `STATE.md` `pending_runs` can later be launched by `gsm8k worker`.
