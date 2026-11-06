"""RunCommands: ``gsm8k train``, the LoRA fine-tune (US2.2, US2.4; contracts C2, C3, C5).

Steps: check the configuration (exit 2, nothing written), print the estimate, take the GPU lock
(exit 3, nothing written), write ``config.json``, train while streaming ``metrics.jsonl``, save the
adapter to ``checkpoints/<run_id>/``, score it on dev, write ``timings.json``, append one row
(method ``sft``, data ``gsm8k-dev``) and end with ``status.json``: 0 finished, 1 failed, 130 stopped.

The base model is loaded through the module attribute ``load_base_model``, read at call time, so tests
can hand in a tiny model.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from gsm8k import cli, evaluation, run_config
from gsm8k.run_records import folder, lock, log, paths

# Dial flags (C2 field names); with --config none of them, nor the other config flags, may be given.
_DIAL_FLAGS = (
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
)
_CONFIG_FLAGS = (*_DIAL_FLAGS, "limit", "max_new_tokens")
TEST_SPLIT_MESSAGE = "The test split is never used for training or tuning"


def load_base_model(model_id: str, revision: str) -> tuple[Any, Any]:
    """The pinned base model and tokenizer (``gsm8k.evaluation.load_model``, looked up at call time)."""
    return evaluation.load_model(model_id, revision)


@dataclasses.dataclass
class TrainPrepared:
    cfg: run_config.RunConfig
    run_id: str
    run_dir: Path
    adapter_dir: Path
    results: Path | None  # None: a new temporary file inside the run folder (BR4.2)
    config_hash: str
    config_given: Path | None
    eval_every: int | None
    max_steps: int | None


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


def _examples(text: str) -> int | str:
    return "all" if text == "all" else _whole(text)


def register(subparsers: Any) -> None:
    tr = subparsers.add_parser(
        "train",
        help="fine-tune a model with LoRA, score the adapter on dev and log the result",
        description="LoRA fine-tune on the GSM8K train split; the adapter is scored on dev and logged.",
    )
    tr.add_argument("--config", type=Path, help="config.json written by the launcher (needs --run-id)")
    tr.add_argument("--run-id", help="attempt id <base id>-<n>, e.g. q06-sft-dev-1")
    tr.add_argument(
        "--results",
        type=Path,
        help="run log to append to (default results/runs.csv); used only with --run-id",
    )
    tr.add_argument("--started-by", choices=("worker", "terminal"), default="terminal")
    tr.add_argument("--model", help="Qwen/Qwen3-0.6B-Base (default) or Qwen/Qwen3-1.7B-Base")
    tr.add_argument("--learning-rate", type=_number, help="1e-5 to 5e-4 (default 2e-4)")
    tr.add_argument("--epochs", type=_whole, help="1 to 3 (default 1)")
    tr.add_argument("--lora-rank", type=_whole, help="4, 8, 16, 32 or 64 (default 16)")
    tr.add_argument("--lora-alpha", type=_whole, help="1 to 128 (default 32)")
    tr.add_argument("--max-seq-len", type=_whole, help="256 to 1024 tokens (default 512)")
    tr.add_argument("--train-examples", type=_examples, help="50 to 6973, or all (default all)")
    tr.add_argument("--batch-size", type=_whole, help="1 to 16 (default 4)")
    tr.add_argument("--warmup-ratio", type=_number, help="0 to 0.2 (default 0.03)")
    tr.add_argument("--seed", type=_whole, help="0 to 2^31-1 (default 42)")
    tr.add_argument("--answer-format", help="step-by-step (default) or terse")
    tr.add_argument("--limit", type=cli._positive_int, help="score only the first N dev problems")
    tr.add_argument(
        "--max-new-tokens", type=cli._positive_int, help="generation cap per dev answer (default 512)"
    )
    tr.add_argument("--eval-every", type=cli._positive_int, help="score on dev every N training steps")
    tr.add_argument("--max-steps", type=cli._positive_int, help="stop after N training steps (tests)")
    tr.set_defaults(func=train_command)


def _config_from_flags(args: argparse.Namespace, run_id: str) -> run_config.RunConfig:
    fields: dict = {"run_id": run_id, "method": "sft", "split": "dev"}
    for name in (*_DIAL_FLAGS, "limit", "max_new_tokens"):
        value = getattr(args, name)
        if value is not None:
            fields[name] = value
    return run_config.RunConfig(**fields)


def _prepare(args: argparse.Namespace) -> TrainPrepared:
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
            "e.g. q06-sft-dev-1)"
        )
    try:
        paths.check_run_id(run_id)
    except ValueError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    try:
        run_config.validate(cfg)
    except run_config.ConfigError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    if cfg.split == "test":  # NFR8: also when validate lets it through
        raise cli.InvalidInput(TEST_SPLIT_MESSAGE)
    if cfg.method != "sft":
        raise cli.InvalidInput(f"method must be sft for gsm8k train, got {cfg.method!r}")
    if cfg.split != "dev":
        raise cli.InvalidInput(f"split must be dev for gsm8k train (the closing score), got {cfg.split!r}")
    if cfg.adapter_path is not None:
        raise cli.InvalidInput(
            f"gsm8k train starts from the base model; adapter_path must be empty, got {cfg.adapter_path!r}"
        )

    results: Path | None = None
    if args.run_id is not None:
        results = Path(args.results) if args.results is not None else paths.DEFAULT_RESULTS
    rdir = paths.run_dir(run_id)
    adapter_dir = paths.checkpoints_root() / run_id
    try:
        used = (
            (results is not None and log.has_run_id(results, run_id))
            or folder.run_already_happened(rdir)
            or adapter_dir.exists()
            or (rdir / "metrics.jsonl").exists()
        )
    except OSError as exc:
        raise cli.InvalidInput(str(exc)) from exc
    if used:
        raise cli.InvalidInput(f"Run id already used: {run_id}")

    return TrainPrepared(
        cfg=cfg,
        run_id=run_id,
        run_dir=rdir,
        adapter_dir=adapter_dir,
        results=results,
        config_hash=run_config.config_hash(cfg),
        config_given=config_given,
        eval_every=args.eval_every,
        max_steps=args.max_steps,
    )


def _print_estimate(prep: TrainPrepared) -> None:
    from gsm8k import estimates
    from gsm8k.training import sft

    cfg = prep.cfg
    steps = sft.total_steps_for(sft.planned_examples(cfg), cfg.batch_size, cfg.epochs, prep.max_steps)
    estimate = estimates.estimate_training(cfg.model, steps)
    print(f"training steps: {steps}")
    print(f"estimate: {estimate.text}")
    if estimate.over_cap:
        print(estimates.OVER_CAP, file=sys.stderr)


def _write_known_timings(run_dir: Path) -> None:
    """On a failure during training, save what is known: seconds per step from the metrics lines
    and the peak GPU memory so far (BR4.4)."""
    from gsm8k.training import loop

    training = [
        line for line in loop.read_metrics(run_dir / loop.METRICS_FILE) if line.get("loss") is not None
    ]
    if not training or (run_dir / "timings.json").exists():
        return
    last = training[-1]
    step, elapsed = last.get("step"), last.get("elapsed_s")
    seconds = (
        elapsed / step if isinstance(step, int) and step > 0 and isinstance(elapsed, int | float) else None
    )
    try:
        peak = loop.gpu_peak_gb()
    except Exception:  # the GPU itself may be what failed
        peak = 0.0
    try:
        folder.write_timings(
            run_dir, seconds_per_problem=None, seconds_per_step=seconds, peak_gpu_memory_gb=peak
        )
    except OSError as exc:
        print(f"Timings could not be written: {exc}", file=sys.stderr)


def _run(prep: TrainPrepared) -> int:
    """Inside the lock. Every exit writes status.json (BR5.2)."""
    from gsm8k.training import loop, sft

    cfg = prep.cfg
    started = time.monotonic()
    prep.run_dir.mkdir(parents=True, exist_ok=True)
    previous = cli._install_sigterm()
    try:
        own_config = prep.run_dir / "config.json"
        if prep.config_given is None or not (own_config.exists() and own_config.samefile(prep.config_given)):
            folder.write_config(prep.run_dir, cfg)

        data = sft.load_training_data(cfg)
        model, tokenizer = load_base_model(cfg.model, cfg.model_revision)
        result = sft.train_sft(
            cfg,
            prep.run_dir,
            prep.adapter_dir,
            model=model,
            tokenizer=tokenizer,
            eval_every=prep.eval_every,
            max_steps=prep.max_steps,
            data=data,
        )
        print(f"adapter: {prep.adapter_dir}")

        def on_prediction(record: dict) -> None:
            folder.append_prediction(prep.run_dir, record)

        eval_started = time.monotonic()
        score = sft.score_on_dev(result.model, result.tokenizer, cfg, data, on_prediction=on_prediction)
        minutes = (time.monotonic() - started) / 60
        # The closing dev line continues the training lines' clock (elapsed since training began).
        lines = loop.read_metrics(prep.run_dir / loop.METRICS_FILE)
        trained_s = lines[-1].get("elapsed_s") if lines else None
        trained_s = trained_s if isinstance(trained_s, int | float) else 0.0
        loop.MetricsWriter(prep.run_dir).write(
            step=result.steps,
            total_steps=result.steps,
            elapsed_s=round(trained_s + time.monotonic() - eval_started, 3),
            eta_s=0.0,
            dev_accuracy=score.accuracy,
        )
        folder.write_timings(
            prep.run_dir,
            seconds_per_problem=score.seconds_per_problem,
            seconds_per_step=result.seconds_per_step,
            peak_gpu_memory_gb=max(result.peak_gpu_memory_gb, score.peak_gpu_memory_gb),
        )
        print(f"dev accuracy: {score.accuracy:.4f} ({score.correct}/{score.scored})")
        print(f"training steps: {result.steps}, seconds per step: {result.seconds_per_step:.3f}")
        print(f"minutes: {minutes:.1f}")
        print(f"run folder: {prep.run_dir}")

        results = prep.results if prep.results is not None else cli._new_temp_results(prep.run_dir)
        log.append_row(
            results,
            log.RunRow(
                date=cli._iso(cli._utc_now()),
                run_id=prep.run_id,
                model=cfg.model,
                method="sft",
                data="gsm8k-dev",
                metric="accuracy",
                value=score.accuracy,
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
        _write_known_timings(prep.run_dir)
        folder.write_status(
            prep.run_dir, run_id=prep.run_id, status="failed", exit_code=cli.EXIT_FAILED, reason=reason
        )
        print(f"Run failed: {reason}", file=sys.stderr)
        return cli.EXIT_FAILED
    finally:
        cli._restore_sigterm(previous)


def train_command(args: argparse.Namespace) -> int:
    try:
        prep = _prepare(args)
    except cli.InvalidInput as exc:
        print(str(exc), file=sys.stderr)
        return cli.EXIT_INVALID

    _print_estimate(prep)
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
