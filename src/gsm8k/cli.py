"""RunCommands: the ``gsm8k`` command line (US1.4, workflow W4, contract C5).

``gsm8k evaluate`` checks its input (exit 2, nothing written), takes the GPU lock (exit 3 when held,
nothing written), evaluates, writes the run folder and one run-log row, and ends with a status file:
0 finished, 1 failed, 130 stopped (BR5.2).

Importing ``gsm8k`` (done first by this module's package) sets the in-folder caches before torch,
transformers or datasets load (BR1.1). The model is reached through the ``evaluation`` module
attribute and the default results file through ``paths.DEFAULT_RESULTS``, both read at call time.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import os
import re
import signal
import sys
import tempfile
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from gsm8k import evaluation, run_config
from gsm8k.run_records import folder, lock, log, paths

EXIT_FINISHED = 0
EXIT_FAILED = 1
EXIT_INVALID = 2
EXIT_LOCKED = 3
EXIT_STOPPED = 130

# A run id given with --run-id must be a C1 attempt id; "adhoc-<timestamp>" is only the name the
# command gives itself when --run-id is absent, and never goes into a real results file (C1, BR4.2).
ATTEMPT_ID_PATTERN = re.compile(r"(?:q06|q17)-[a-z0-9]+-[a-z0-9]+-[0-9]+")

# Flags that set configuration fields; with --config they may not be given (BR4.8: used unchanged).
_CONFIG_FLAGS = ("split", "limit", "model", "adapter", "seed", "max_new_tokens")

# Other units' commands: each module exposes ``register(subparsers)``, which adds its subcommand
# and sets ``func`` (a callable taking the parsed arguments and returning the exit code).
COMMAND_MODULES = ("gsm8k.harness", "gsm8k.train_cmd", "gsm8k.prune")


class InvalidInput(Exception):
    """A check before the run starts failed: exit 2, nothing written (BR5.2)."""


class RunStopped(BaseException):
    """SIGTERM arrived during the run (SIGINT arrives as KeyboardInterrupt)."""


@dataclasses.dataclass
class Prepared:
    cfg: run_config.RunConfig
    run_id: str
    run_dir: Path
    results: Path | None  # None: a new temporary file is made at the end (BR4.2)
    adapter: Path | None
    adapter_run: str
    config_hash: str
    config_given: Path | None


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number of at least 1, got {value}")
    return value


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a whole number of at least 0, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gsm8k", description="GSM8K fine-tuning project commands.")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    ev = sub.add_parser(
        "evaluate",
        help="evaluate a model (or a model plus an adapter) on a split and log the result",
        description="Evaluate a model on a GSM8K split and append one row to the run log.",
    )
    ev.add_argument("--config", type=Path, help="config.json written by the launcher (needs --run-id)")
    ev.add_argument("--run-id", help="attempt id <base id>-<n>, e.g. q06-base-dev-1")
    ev.add_argument(
        "--results",
        type=Path,
        help="run log to append to (default results/runs.csv); used only with --run-id",
    )
    ev.add_argument("--started-by", choices=("worker", "terminal"), default="terminal")
    ev.add_argument("--split", choices=("dev", "test"))
    ev.add_argument("--limit", type=_positive_int, help="score only the first N problems")
    ev.add_argument("--model", help="model id, default Qwen/Qwen3-0.6B-Base")
    ev.add_argument("--adapter", help="adapter folder under checkpoints/")
    ev.add_argument("--seed", type=_non_negative_int)
    ev.add_argument("--max-new-tokens", type=_positive_int, help="generation cap per answer (default 512)")
    for name in COMMAND_MODULES:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:  # a command whose unit is not built yet
            if exc.name != name:
                raise
            continue
        module.register(sub)
    return parser


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _adhoc_run_id() -> str:
    return "adhoc-" + _utc_now().strftime("%Y%m%d-%H%M%S")


def _config_from_flags(args: argparse.Namespace, run_id: str) -> run_config.RunConfig:
    fields: dict = {"run_id": run_id}
    if args.model is not None:
        fields["model"] = args.model
    if args.split is not None:
        fields["split"] = args.split
    if args.limit is not None:
        fields["limit"] = args.limit
    if args.seed is not None:
        fields["seed"] = args.seed
    if args.max_new_tokens is not None:
        fields["max_new_tokens"] = args.max_new_tokens
    if args.adapter is not None:
        fields["adapter_path"] = args.adapter
    return run_config.RunConfig(**fields)


def _adapter_method(adapter: Path) -> tuple[str, str]:
    """BR4.7: the adapter's run id is its folder name; the method comes from that run's config.json."""
    adapter_run = adapter.name
    try:
        method = run_config.read_config(paths.run_dir(adapter_run) / "config.json").method
    except (run_config.ConfigError, ValueError, OSError) as exc:
        raise InvalidInput(f"Adapter run unknown: {adapter_run}") from exc
    return method, adapter_run


def _prepare(args: argparse.Namespace) -> Prepared:
    """W4 steps 2-3: build and check the configuration. Raises InvalidInput; writes nothing."""
    config_given: Path | None = None
    if args.config is not None:
        given = [name for name in _CONFIG_FLAGS if getattr(args, name) is not None]
        if given:
            flags = ", ".join("--" + name.replace("_", "-") for name in given)
            raise InvalidInput(f"--config is used unchanged; do not also give {flags}")
        if args.run_id is None:
            raise InvalidInput(f"--config needs --run-id: {args.config}")
        try:
            cfg = run_config.read_config(args.config)
        except run_config.ConfigError as exc:
            raise InvalidInput(str(exc)) from exc
        if cfg.run_id != args.run_id:
            raise InvalidInput(f"Run id in {args.config} is {cfg.run_id!r}, not the --run-id {args.run_id!r}")
        config_given = Path(args.config)
        run_id = args.run_id
    else:
        run_id = args.run_id if args.run_id is not None else _adhoc_run_id()
        try:
            cfg = _config_from_flags(args, run_id)
        except (TypeError, run_config.ConfigError) as exc:
            raise InvalidInput(str(exc)) from exc

    if args.run_id is not None and not ATTEMPT_ID_PATTERN.fullmatch(args.run_id):
        raise InvalidInput(
            f"Invalid run id: {args.run_id!r} (--run-id takes an attempt id <base id>-<n>, "
            "e.g. q06-base-dev-1)"
        )
    try:
        paths.check_run_id(run_id)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    if cfg.split not in ("dev", "test"):
        raise InvalidInput(f"split must be one of dev, test for gsm8k evaluate, got {cfg.split!r}")
    try:
        run_config.validate(cfg)
    except run_config.ConfigError as exc:
        raise InvalidInput(str(exc)) from exc

    adapter: Path | None = None
    adapter_run = ""
    if cfg.adapter_path is not None:
        try:
            adapter = paths.resolve_adapter(cfg.adapter_path)
        except (FileNotFoundError, ValueError) as exc:
            raise InvalidInput(str(exc)) from exc
        method, adapter_run = _adapter_method(adapter)
        if method != cfg.method:
            if config_given is not None:  # a launcher's config is used unchanged (BR4.8)
                raise InvalidInput(
                    f"Method in {config_given} is {cfg.method!r}, but adapter run {adapter_run} is {method!r}"
                )
            cfg = dataclasses.replace(cfg, method=method)

    results: Path | None = None
    if args.run_id is not None:
        results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    rdir = paths.run_dir(run_id)
    try:
        used = (results is not None and log.has_run_id(results, run_id)) or folder.run_already_happened(rdir)
    except OSError as exc:
        raise InvalidInput(str(exc)) from exc
    if used:
        raise InvalidInput(f"Run id already used: {run_id}")

    return Prepared(
        cfg=cfg,
        run_id=run_id,
        run_dir=rdir,
        results=results,
        adapter=adapter,
        adapter_run=adapter_run,
        config_hash=run_config.config_hash(cfg),
        config_given=config_given,
    )


def _new_temp_results(run_dir: Path) -> Path:
    """BR4.2: a run without --run-id writes its row to a new temporary file, never results/runs.csv.
    The file is made inside the run's own folder, so nothing is written above the project (NFR5.2)."""
    fd, name = tempfile.mkstemp(prefix="gsm8k-runs-", suffix=".csv", dir=run_dir)
    os.close(fd)
    return Path(name).resolve()


def _install_sigterm() -> object | None:
    if threading.current_thread() is not threading.main_thread():
        return None

    def _on_sigterm(signum, frame):
        raise RunStopped()

    return signal.signal(signal.SIGTERM, _on_sigterm)


def _restore_sigterm(previous: object | None) -> None:
    if previous is not None:
        signal.signal(signal.SIGTERM, previous)


def _failure_reason(exc: BaseException) -> str:
    torch = sys.modules.get("torch")
    oom = getattr(getattr(torch, "cuda", None), "OutOfMemoryError", None) if torch else None
    if (oom is not None and isinstance(exc, oom)) or "CUDA out of memory" in str(exc):
        return "GPU out of memory"
    return str(exc) or type(exc).__name__


def _write_known_timings(run_dir: Path, progress: dict) -> None:
    """BR4.4: on a failure after generation started, save what is known about the timings."""
    if progress["gen_started"] is None or progress["timings_written"]:
        return
    scored = progress["scored"]
    seconds = (time.monotonic() - progress["gen_started"]) / scored if scored else None
    try:
        peak = evaluation.peak_gpu_memory_gb(progress["model"])
    except Exception:  # the GPU itself may be what failed
        peak = 0.0
    try:
        folder.write_timings(run_dir, seconds_per_problem=seconds, peak_gpu_memory_gb=peak)
    except OSError as exc:
        print(f"Timings could not be written: {exc}", file=sys.stderr)


def _run(prep: Prepared) -> int:
    """W4 steps 5-9, inside the lock. Every exit writes status.json (BR5.2)."""
    from gsm8k.datasets_prompts import hub, prompt, split

    cfg = prep.cfg
    started = time.monotonic()
    prep.run_dir.mkdir(parents=True, exist_ok=True)
    # What is known about timings if the run fails after generation started (BR4.4).
    progress = {"model": None, "gen_started": None, "scored": 0, "timings_written": False}

    def on_prediction(record: dict) -> None:
        folder.append_prediction(prep.run_dir, record)
        progress["scored"] += 1

    previous = _install_sigterm()
    try:
        own_config = prep.run_dir / "config.json"
        if prep.config_given is None or not (own_config.exists() and own_config.samefile(prep.config_given)):
            folder.write_config(prep.run_dir, cfg)

        problems = hub.load_gsm8k(cfg.dataset_revision)
        train_ids = [p.id for p in problems["train"]]
        data_split = split.load_or_build_split(train_ids, split_seed=cfg.split_seed)
        exemplar_ids = prompt.choose_exemplars(data_split.dev_ids, cfg.split_seed)
        by_id = {p.id: p for p in problems["train"]}
        exemplars = [by_id[i] for i in exemplar_ids]
        to_score = prompt.problems_to_score(cfg.split, data_split, problems, exemplar_ids, cfg.limit)

        model, tokenizer = evaluation.load_model(cfg.model, cfg.model_revision, prep.adapter)
        import torch

        torch.manual_seed(cfg.seed)
        torch.backends.cuda.matmul.allow_tf32 = False
        progress["model"] = model
        progress["gen_started"] = time.monotonic()
        result = evaluation.evaluate(
            model,
            tokenizer,
            to_score,
            lambda p: prompt.build_prompt(exemplars, p.question),
            batch_size=evaluation.batch_size_for(cfg.model),
            max_new_tokens=cfg.max_new_tokens,
            on_prediction=on_prediction,
        )
        folder.write_timings(
            prep.run_dir,
            seconds_per_problem=result.seconds_per_problem,
            peak_gpu_memory_gb=result.peak_gpu_memory_gb,
        )
        progress["timings_written"] = True
        minutes = (time.monotonic() - started) / 60
        print(f"accuracy: {result.accuracy:.4f} ({result.correct}/{result.scored})")
        print(f"problems scored: {result.scored}")
        print(f"minutes: {minutes:.1f}")
        print(f"run folder: {prep.run_dir}")

        results = prep.results if prep.results is not None else _new_temp_results(prep.run_dir)
        log.append_row(
            results,
            log.RunRow(
                date=_iso(_utc_now()),
                run_id=prep.run_id,
                model=cfg.model,
                method=cfg.method,
                data=f"gsm8k-{cfg.split}",
                metric="accuracy",
                value=result.accuracy,
                minutes=minutes,
                config_hash=prep.config_hash,
                adapter_run=prep.adapter_run,
            ),
        )
        print(f"results: {results}")
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="finished", exit_code=EXIT_FINISHED, reason=None
        )
        return EXIT_FINISHED
    except (KeyboardInterrupt, RunStopped) as exc:
        signame = "SIGTERM" if isinstance(exc, RunStopped) else "SIGINT"
        folder.write_status(
            prep.run_dir,
            run_id=prep.run_id,
            status="stopped",
            exit_code=EXIT_STOPPED,
            reason=f"Stopped by {signame}",
        )
        print(f"Run stopped ({signame}): {prep.run_id}", file=sys.stderr)
        return EXIT_STOPPED
    except Exception as exc:
        reason = _failure_reason(exc)
        traceback.print_exc(file=sys.stderr)
        _write_known_timings(prep.run_dir, progress)
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="failed", exit_code=EXIT_FAILED, reason=reason
        )
        print(f"Run failed: {reason}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        _restore_sigterm(previous)


def evaluate_command(args: argparse.Namespace) -> int:
    try:
        prep = _prepare(args)
    except InvalidInput as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID

    gpu_lock = lock.GpuLock()
    try:
        gpu_lock.acquire(prep.run_id, started_by=args.started_by)
    except lock.LockHeld as exc:
        print(f"A run is already active: {exc.run_id}", file=sys.stderr)
        return EXIT_LOCKED
    try:
        return _run(prep)
    finally:
        gpu_lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # --help (0) or an unknown option or bad value (2)
        return exc.code if isinstance(exc.code, int) else EXIT_INVALID
    if args.command == "evaluate":
        return evaluate_command(args)
    if getattr(args, "func", None) is not None:
        return args.func(args)
    parser.print_help()
    return EXIT_INVALID
