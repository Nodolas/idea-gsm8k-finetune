"""Evaluation: ``gsm8k harness``, the lm-evaluation-harness cross-check (US1.5, AC1.5.5; AC6.1.3).

The harness's own ``gsm8k`` task (5-shot, flexible-extract filter, test split) runs on the model object
loaded by the project, and the accuracy goes into one run-log row with data ``gsm8k-test-harness`` and
metric ``harness_flexible_accuracy`` (C1). The model is the base model (method ``base``) or the base
model plus a finalist's adapter (method ``best``, ``--adapter``, ``adapter_run`` on the row; BR4.7/BR4.8
as changed 2026-11-07, C5): the harness scores the test split, so an adapter needs method ``best`` and a
finalist, checked as ``gsm8k evaluate`` checks it. The run follows ``gsm8k evaluate``
(W4, C5): checks (exit 2, nothing written), the GPU lock (exit 3, nothing written), ``config.json``,
the harness, ``timings.json``, the row, then ``status.json`` (0 finished, 1 failed, 130 stopped).

The harness reads the pinned dataset revision into the project's Hugging Face cache; its request cache
(off here) would go to ``.cache/lm_eval``, and it writes no sample logs or result files. Heavy imports
(torch, lm_eval) stay inside the functions, so ``import gsm8k.cli`` and ``gsm8k --help`` stay light.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from gsm8k import cli, evaluation, run_config
from gsm8k._env import ROOT
from gsm8k.datasets_prompts.hub import DATASET_REVISION
from gsm8k.run_records import folder, lock, log, paths

DEFAULT_MODEL = "Qwen/Qwen3-1.7B-Base"
TASK = "gsm8k"
NUM_FEWSHOT = 5
RESULT_KEY = "exact_match,flexible-extract"
DATA = "gsm8k-test-harness"
METRIC = "harness_flexible_accuracy"
EVALUATOR = "lm-eval-harness"  # C2 field: a harness run's config (and hash) differs from `evaluate`'s
TEST_SIZE = 1319  # GSM8K test problems
LM_EVAL_CACHE = ROOT / ".cache" / "lm_eval"


def load_model(model_id: str, revision: str, adapter_path: Path | None = None) -> tuple[Any, Any]:
    """The command's model loader (tests replace this attribute); defaults to the project's loader,
    looked up at call time."""
    return evaluation.load_model(model_id, revision, adapter_path)


def _task_config() -> dict:
    """The harness's registered ``gsm8k`` task config, unchanged except the dataset read at the pinned
    revision (the same commit the project's own evaluation uses)."""
    from lm_eval.tasks import TaskManager
    from lm_eval.tasks._yaml_loader import load_yaml

    entry = TaskManager().task_index.get(TASK)
    if entry is None or entry.yaml_path is None:
        raise RuntimeError(f"lm-evaluation-harness has no {TASK} task")
    cfg = load_yaml(entry.yaml_path, resolve_func=True)
    cfg["dataset_kwargs"] = {**(cfg.get("dataset_kwargs") or {}), "revision": DATASET_REVISION}
    return cfg


def run_harness(model: Any, tokenizer: Any, *, limit: int | None, batch_size: int = 8) -> float:
    """Run the lm-evaluation-harness ``gsm8k`` task (5-shot, test split) on the given model object and
    return its flexible-extract exact-match accuracy, from 0 to 1. ``limit`` scores the first N
    test problems; None scores all of them."""
    os.environ["LM_HARNESS_CACHE_PATH"] = str(LM_EVAL_CACHE)
    from lm_eval import simple_evaluate
    from lm_eval.models.huggingface import HFLM

    # HFLM caps generation through max_length (context + 256 new tokens), but a generation_config
    # max_new_tokens (2048 for Qwen3) overrides it in transformers; clear it so the harness's own cap
    # applies (inception/changes.md 2026-11-07).
    generation_config = getattr(model, "generation_config", None)
    if generation_config is not None:
        generation_config.max_new_tokens = None
    lm = HFLM(pretrained=model, tokenizer=tokenizer, batch_size=batch_size)
    out = simple_evaluate(
        model=lm,
        tasks=[_task_config()],
        num_fewshot=NUM_FEWSHOT,
        limit=limit,
        cache_requests=False,
        write_out=False,
        log_samples=False,
        apply_chat_template=False,
    )
    if out is None:
        raise RuntimeError("lm-evaluation-harness returned no results")
    try:
        value = out["results"][TASK][RESULT_KEY]
    except KeyError as exc:
        raise RuntimeError(f"lm-evaluation-harness result has no {TASK} {RESULT_KEY!r}") from exc
    return float(value)


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "harness",
        help="cross-check a model (or a finalist's adapter) with the lm-evaluation-harness gsm8k task",
        description=(
            "Score a base model, or with --method best --adapter a finalist's adapter, with the "
            "lm-evaluation-harness gsm8k task (5-shot, flexible extract, test split) and append one row "
            "to the run log, as a cross-check only."
        ),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model id, default {DEFAULT_MODEL}")
    parser.add_argument(
        "--method",
        choices=("base", "best"),
        help="base (default, the base model) or best: a finalist's adapter (needs --adapter)",
    )
    parser.add_argument("--adapter", help="finalist's adapter folder, e.g. checkpoints/q17-sft-dev-1")
    cli.add_finalists_argument(parser)
    parser.add_argument("--run-id", help="attempt id <base id>-<n>, e.g. q17-base-harness-1")
    parser.add_argument(
        "--results",
        type=Path,
        help="run log to append to (default results/runs.csv); used only with --run-id",
    )
    parser.add_argument("--limit", type=cli._positive_int, help="score only the first N test problems")
    parser.add_argument("--started-by", choices=("worker", "terminal"), default="terminal")
    parser.set_defaults(func=harness_command)


def _prepare(args: argparse.Namespace) -> cli.Prepared:
    """Build and check the configuration. Raises cli.InvalidInput; writes nothing."""
    if args.run_id is not None and not cli.ATTEMPT_ID_PATTERN.fullmatch(args.run_id):
        raise cli.InvalidInput(
            f"Invalid run id: {args.run_id!r} (--run-id takes an attempt id <base id>-<n>, "
            "e.g. q17-base-harness-1)"
        )
    run_id = args.run_id if args.run_id is not None else cli._adhoc_run_id()
    try:
        paths.check_run_id(run_id)
    except ValueError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    try:
        cfg = run_config.RunConfig(
            run_id=run_id,
            model=args.model,
            method=args.method if args.method is not None else "base",
            split="test",
            adapter_path=args.adapter,
            limit=args.limit,
            evaluator=EVALUATOR,
        )
        run_config.validate(cfg)
    except (TypeError, run_config.ConfigError) as exc:
        raise cli.InvalidInput(str(exc)) from exc
    cfg, adapter, adapter_run = cli.resolve_adapter(cfg, None, cli.finalists_path(args))

    results: Path | None = None
    if args.run_id is not None:
        results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    rdir = paths.run_dir(run_id)
    try:
        used = (results is not None and log.has_run_id(results, run_id)) or folder.run_already_happened(rdir)
    except OSError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    if used:
        raise cli.InvalidInput(f"Run id already used: {run_id}")

    return cli.Prepared(
        cfg=cfg,
        run_id=run_id,
        run_dir=rdir,
        results=results,
        adapter=adapter,
        adapter_run=adapter_run,
        config_hash=run_config.config_hash(cfg),
        config_given=None,
    )


def _write_known_timings(run_dir: Path, model: Any) -> None:
    """On a failure after the model loaded, save the peak GPU memory that is known."""
    if model is None:
        return
    try:
        peak = evaluation.peak_gpu_memory_gb(model)
    except Exception:  # the GPU itself may be what failed
        peak = 0.0
    try:
        folder.write_timings(run_dir, seconds_per_problem=None, peak_gpu_memory_gb=peak)
    except OSError as exc:
        print(f"Timings could not be written: {exc}", file=sys.stderr)


def _run(prep: cli.Prepared) -> int:
    """Inside the lock: config, model, harness, timings, row, status. Every exit writes status.json."""
    cfg = prep.cfg
    started = time.monotonic()
    prep.run_dir.mkdir(parents=True, exist_ok=True)
    model = None
    timings_written = False
    previous = cli._install_sigterm()
    try:
        folder.write_config(prep.run_dir, cfg)
        model, tokenizer = load_model(cfg.model, cfg.model_revision, prep.adapter)
        import torch

        torch.manual_seed(cfg.seed)
        accuracy = run_harness(
            model, tokenizer, limit=cfg.limit, batch_size=evaluation.batch_size_for(cfg.model)
        )
        # The harness's per-problem time is not the project evaluation's (other prompt, other token
        # cap), so it is not offered to the evaluation estimates: only the peak memory is saved.
        folder.write_timings(
            prep.run_dir,
            seconds_per_problem=None,
            peak_gpu_memory_gb=evaluation.peak_gpu_memory_gb(model),
        )
        timings_written = True
        minutes = (time.monotonic() - started) / 60
        n_problems = min(cfg.limit, TEST_SIZE) if cfg.limit is not None else TEST_SIZE
        print(f"harness accuracy (flexible extract): {accuracy:.4f}")
        print(f"problems scored: {n_problems}")
        print(f"minutes: {minutes:.1f}")
        print(f"run folder: {prep.run_dir}")

        results = prep.results if prep.results is not None else cli._new_temp_results(prep.run_dir)
        log.append_row(
            results,
            log.RunRow(
                date=cli._iso(cli._utc_now()),
                run_id=prep.run_id,
                model=cfg.model,
                method=cfg.method,
                data=DATA,
                metric=METRIC,
                value=accuracy,
                minutes=minutes,
                config_hash=prep.config_hash,
                adapter_run=prep.adapter_run,
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
        if not timings_written:
            _write_known_timings(prep.run_dir, model)
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="failed", exit_code=cli.EXIT_FAILED, reason=reason
        )
        print(f"Run failed: {reason}", file=sys.stderr)
        return cli.EXIT_FAILED
    finally:
        cli._restore_sigterm(previous)


def harness_command(args: argparse.Namespace) -> int:
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
