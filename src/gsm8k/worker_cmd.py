"""RunCommands: ``gsm8k worker``, the run-queue worker as its own process (US3.7; ADR-004, ADR-006).

It starts the waiting runs of ``outputs/queue/`` one at a time while the GPU lock is free; the runs are
separate ``gsm8k train`` or ``gsm8k evaluate`` processes. SIGTERM or Ctrl-C stops the worker (exit 0);
runs it launched keep going.
"""

import argparse
from pathlib import Path
from typing import Any


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a number, got {text!r}") from exc
    if not value > 0:
        raise argparse.ArgumentTypeError(f"expected a number above 0, got {value}")
    return value


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "worker",
        help="start queued runs one at a time while the GPU is free",
        description="Run the queue worker: launch the waiting runs of outputs/queue/ one at a time.",
    )
    parser.add_argument(
        "--results", type=Path, help="run log the launched runs append to (default results/runs.csv)"
    )
    parser.add_argument(
        "--poll-seconds", type=_positive_float, default=1.0, help="seconds between queue checks (default 1)"
    )
    parser.add_argument("--once", action="store_true", help="do one step and exit")
    parser.set_defaults(func=worker_command)


def worker_command(args: argparse.Namespace) -> int:
    from gsm8k.run_control.worker import run_worker

    return run_worker(results=args.results, poll_seconds=args.poll_seconds, once=args.once)
