"""RunCommands: ``gsm8k cot-generate``, the self-taught chain-of-thought generation (US10.1; C2, C5).

Steps: check the configuration (exit 2, nothing written), take the GPU lock (exit 3, nothing written),
write ``config.json``, sample the first ``cot_problems`` training problems by index with the fixed
4-shot prompt while streaming ``metrics.jsonl`` (step = problems done), write ``cot_data.jsonl``,
``cot_stats.json`` and ``timings.json``, append one row (method ``cotgen``, data ``gsm8k-train``,
metric ``kept_fraction``) and end with ``status.json``: 0 finished, 1 failed, 130 stopped.

The model is loaded through ``gsm8k.evaluation.load_model``, read at call time, so tests can hand in a
tiny model. Heavy libraries are imported inside the functions.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from gsm8k import cli, evaluation, run_config
from gsm8k.run_records import folder, lock, log, paths

# Flags that set configuration fields; with --config none of them may be given (BR4.8).
_CONFIG_FLAGS = ("model", "cot_problems", "cot_samples", "cot_temperature", "seed", "max_new_tokens")
COT_DATA_FILE = "cot_data.jsonl"
COT_STATS_FILE = "cot_stats.json"
ROW_DATA = "gsm8k-train"
ROW_METRIC = "kept_fraction"


@dataclasses.dataclass
class CotPrepared:
    cfg: run_config.RunConfig
    run_id: str
    run_dir: Path
    results: Path | None  # None: a new temporary file inside the run folder (BR4.2)
    config_hash: str
    config_given: Path | None


def _number(text: str) -> float:
    try:
        return float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a number, got {text!r}") from exc


def _whole(text: str) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from exc


def _problems(text: str) -> int | str:
    if text == "all":
        return "all"
    try:
        return int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected 'all' or a whole number, got {text!r}") from exc


def register(subparsers: Any) -> None:
    cg = subparsers.add_parser(
        "cot-generate",
        help="sample the model's own step-by-step solutions to training problems and keep the correct ones",
        description=(
            "Self-taught chain of thought, step 1: sample several solutions per training problem with the "
            "fixed 4-shot prompt, keep the first correct one with reasoning, and log the kept fraction."
        ),
    )
    cg.add_argument("--config", type=Path, help="config.json written by the launcher (needs --run-id)")
    cg.add_argument("--run-id", help="attempt id <base id>-<n>, e.g. q17-cotgen-train-1")
    cg.add_argument(
        "--results",
        type=Path,
        help="run log to append to (default results/runs.csv); used only with --run-id",
    )
    cg.add_argument("--started-by", choices=("worker", "terminal"), default="terminal")
    cg.add_argument("--model", help="Qwen/Qwen3-0.6B-Base (default) or Qwen/Qwen3-1.7B-Base")
    cg.add_argument(
        "--cot-problems",
        type=_problems,
        help=f"first N training problems by index, 50 to {run_config.TRAIN_SPLIT_SIZE} or all (default 1500)",
    )
    cg.add_argument("--cot-samples", type=_whole, help="samples per problem, 1 to 8 (default 4)")
    cg.add_argument("--cot-temperature", type=_number, help="sampling temperature, 0.1 to 1.5 (default 0.7)")
    cg.add_argument("--seed", type=_whole, help="0 to 2^31-1 (default 42)")
    cg.add_argument(
        "--max-new-tokens", type=cli._positive_int, help="generation cap per sample (default 512)"
    )
    cg.set_defaults(func=cot_generate_command)


def _config_from_flags(args: argparse.Namespace, run_id: str) -> run_config.RunConfig:
    fields: dict = {"run_id": run_id, "method": run_config.COT_METHOD, "split": run_config.COT_SPLIT}
    for name in _CONFIG_FLAGS:
        value = getattr(args, name)
        if value is not None:
            fields[name] = value
    return run_config.RunConfig(**fields)


def _prepare(args: argparse.Namespace) -> CotPrepared:
    """Build and check the configuration. Raises cli.InvalidInput; writes nothing."""
    config_given: Path | None = None
    if args.config is not None:
        given = [name for name in _CONFIG_FLAGS if getattr(args, name) is not None]
        if given:
            flags = ", ".join("--" + name.replace("_", "-") for name in given)
            raise cli.InvalidInput(f"--config is used unchanged; do not also give {flags}")
        if args.run_id is None:
            raise cli.InvalidInput(f"--config needs --run-id: {args.config}")
        try:
            cfg = run_config.read_config(args.config)
        except run_config.ConfigError as exc:
            raise cli.InvalidInput(str(exc)) from exc
        if cfg.run_id != args.run_id:
            raise cli.InvalidInput(
                f"Run id in {args.config} is {cfg.run_id!r}, not the --run-id {args.run_id!r}"
            )
        config_given = Path(args.config)
        run_id = args.run_id
    else:
        run_id = args.run_id if args.run_id is not None else cli._adhoc_run_id()
        try:
            cfg = _config_from_flags(args, run_id)
        except (TypeError, run_config.ConfigError) as exc:
            raise cli.InvalidInput(str(exc)) from exc

    if args.run_id is not None and not cli.ATTEMPT_ID_PATTERN.fullmatch(args.run_id):
        raise cli.InvalidInput(
            f"Invalid run id: {args.run_id!r} (--run-id takes an attempt id <base id>-<n>, "
            "e.g. q17-cotgen-train-1)"
        )
    try:
        paths.check_run_id(run_id)
    except ValueError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    try:
        run_config.validate(cfg)
    except run_config.ConfigError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    if cfg.method != run_config.COT_METHOD:
        raise cli.InvalidInput(
            f"method must be {run_config.COT_METHOD} for gsm8k cot-generate, got {cfg.method!r}"
        )
    if cfg.adapter_path is not None:
        raise cli.InvalidInput(
            f"gsm8k cot-generate samples the base model; adapter_path must be empty, got {cfg.adapter_path!r}"
        )

    results: Path | None = None
    if args.run_id is not None:
        results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    rdir = paths.run_dir(run_id)
    try:
        used = (
            (results is not None and log.has_run_id(results, run_id))
            or folder.run_already_happened(rdir)
            or (rdir / COT_DATA_FILE).exists()
            or (rdir / "metrics.jsonl").exists()
        )
    except OSError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    if used:
        raise cli.InvalidInput(f"Run id already used: {run_id}")

    return CotPrepared(
        cfg=cfg,
        run_id=run_id,
        run_dir=rdir,
        results=results,
        config_hash=run_config.config_hash(cfg),
        config_given=config_given,
    )


def _write_json(path: Path, data: dict) -> None:
    folder.atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_cot_data(run_dir: Path, records: list[dict]) -> None:
    """``cot_data.jsonl``: one line per kept problem, problem index order; empty when nothing is kept."""
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    folder.atomic_write_text(Path(run_dir) / COT_DATA_FILE, text)


def write_cot_timings(
    run_dir: Path, *, seconds_per_generated_problem: float | None, peak_gpu_memory_gb: float
) -> None:
    """C2: a cotgen run leaves ``seconds_per_problem`` null (several samples per problem would skew
    evaluation estimates) and adds ``seconds_per_generated_problem``."""
    _write_json(
        Path(run_dir) / "timings.json",
        {
            "v": folder.SCHEMA_VERSION,
            "seconds_per_step": None,
            "seconds_per_problem": None,
            "seconds_per_generated_problem": seconds_per_generated_problem,
            "peak_gpu_memory_gb": peak_gpu_memory_gb,
        },
    )


def _write_known_timings(run_dir: Path, progress: dict) -> None:
    """BR4.4: on a failure after sampling started, save what is known about the timings."""
    if progress["gen_started"] is None or (run_dir / "timings.json").exists():
        return
    done = progress["done"]
    seconds = (time.monotonic() - progress["gen_started"]) / done if done else None
    try:
        peak = evaluation.peak_gpu_memory_gb(progress["model"])
    except Exception:  # the GPU itself may be what failed
        peak = 0.0
    try:
        write_cot_timings(run_dir, seconds_per_generated_problem=seconds, peak_gpu_memory_gb=peak)
    except OSError as exc:
        print(f"Timings could not be written: {exc}", file=sys.stderr)


def _run(prep: CotPrepared) -> int:
    """Inside the lock. Every exit writes status.json (BR5.2)."""
    from gsm8k.cot import generate
    from gsm8k.training import loop, sft

    cfg = prep.cfg
    started = time.monotonic()
    prep.run_dir.mkdir(parents=True, exist_ok=True)
    progress: dict = {"model": None, "gen_started": None, "done": 0}
    previous = cli._install_sigterm()
    try:
        own_config = prep.run_dir / "config.json"
        if prep.config_given is None or not (own_config.exists() and own_config.samefile(prep.config_given)):
            folder.write_config(prep.run_dir, cfg)

        # The first cot_problems training problems by index; load_training_data runs the split guard
        # (never a dev, test or other evaluation problem, NFR8).
        data = sft.load_training_data(dataclasses.replace(cfg, train_examples=cfg.cot_problems))
        problems = data.train
        total = len(problems)
        print(
            f"problems: {total}, samples per problem: {cfg.cot_samples}, temperature: {cfg.cot_temperature:g}"
        )

        model, tokenizer = evaluation.load_model(cfg.model, cfg.model_revision)
        progress["model"] = model
        metrics = loop.MetricsWriter(prep.run_dir)
        gen_started = time.monotonic()
        progress["gen_started"] = gen_started
        metrics.write(step=0, total_steps=total, elapsed_s=0.0, eta_s=None)

        def on_progress(done: int, total_steps: int) -> None:
            progress["done"] = done
            elapsed = time.monotonic() - gen_started
            eta = elapsed / done * (total_steps - done) if done else None
            metrics.write(
                step=done,
                total_steps=total_steps,
                elapsed_s=round(elapsed, 3),
                eta_s=round(eta, 3) if eta is not None else None,
            )

        result = generate.generate_cot(
            model, tokenizer, problems, data.prompt_for, cfg, on_progress=on_progress
        )
        write_cot_data(prep.run_dir, result.records)
        _write_json(prep.run_dir / COT_STATS_FILE, result.stats(prep.run_id))
        write_cot_timings(
            prep.run_dir,
            seconds_per_generated_problem=result.seconds_per_generated_problem,
            peak_gpu_memory_gb=result.peak_gpu_memory_gb,
        )
        minutes = (time.monotonic() - started) / 60
        print(f"kept fraction: {result.kept_fraction:.4f} ({result.kept}/{result.problems})")
        print(f"solved: {result.solved}/{result.problems}")
        print(f"minutes: {minutes:.1f}")
        print(f"run folder: {prep.run_dir}")

        results = prep.results if prep.results is not None else cli._new_temp_results(prep.run_dir)
        log.append_row(
            results,
            log.RunRow(
                date=cli._iso(cli._utc_now()),
                run_id=prep.run_id,
                model=cfg.model,
                method=run_config.COT_METHOD,
                data=ROW_DATA,
                metric=ROW_METRIC,
                value=result.kept_fraction,
                minutes=minutes,
                config_hash=prep.config_hash,
                adapter_run="",
            ),
        )
        print(f"results: {results}")
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="finished", exit_code=cli.EXIT_FINISHED, reason=None
        )
        return cli.EXIT_FINISHED
    except (KeyboardInterrupt, cli.RunStopped) as exc:
        signame = "SIGTERM" if isinstance(exc, cli.RunStopped) else "SIGINT"
        folder.write_status(
            prep.run_dir,
            run_id=prep.run_id,
            status="stopped",
            exit_code=cli.EXIT_STOPPED,
            reason=f"Stopped by {signame}",
        )
        print(f"Run stopped ({signame}): {prep.run_id}", file=sys.stderr)
        return cli.EXIT_STOPPED
    except Exception as exc:
        reason = cli._failure_reason(exc)
        traceback.print_exc(file=sys.stderr)
        _write_known_timings(prep.run_dir, progress)
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="failed", exit_code=cli.EXIT_FAILED, reason=reason
        )
        print(f"Run failed: {reason}", file=sys.stderr)
        return cli.EXIT_FAILED
    finally:
        cli._restore_sigterm(previous)


def cot_generate_command(args: argparse.Namespace) -> int:
    try:
        prep = _prepare(args)
    except cli.InvalidInput as exc:
        print(str(exc), file=sys.stderr)
        return cli.EXIT_INVALID

    gpu_lock = lock.GpuLock()
    try:
        gpu_lock.acquire(prep.run_id, started_by=args.started_by)
    except lock.LockHeld as exc:
        print(f"A run is already active: {exc.run_id}", file=sys.stderr)
        return cli.EXIT_LOCKED
    try:
        return _run(prep)
    finally:
        gpu_lock.release()
