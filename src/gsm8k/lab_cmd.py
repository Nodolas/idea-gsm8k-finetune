"""RunCommands: ``gsm8k lab list|run`` (US11.1, US11.2, contract C8).

This module imports no torch, transformers or peft and sets no environment variable on import
(``gsm8k`` imports every command module when it builds its parser). The ``run`` handler hides the GPU
before CUDA is first used and imports the training code only then.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from gsm8k.lab import config as lab_config
from gsm8k.lab.lessons import LESSONS

EXIT_FINISHED = 0
EXIT_INVALID = 2


def _outputs_root(given: Path | None) -> Path:
    if given is not None:
        return Path(given)
    from gsm8k.run_records.paths import outputs_root

    return outputs_root()


def run_list(args: argparse.Namespace) -> int:
    for lesson in LESSONS:
        count = len(lesson.variants)
        noun = "variant" if count == 1 else "variants"
        minutes = lab_config.estimate_minutes(lesson)
        print(f"{lesson.id}  {lesson.title}  ({count} {noun}, about {minutes} min)")
    return EXIT_FINISHED


def run_run(args: argparse.Namespace) -> int:
    lesson = next((item for item in LESSONS if item.id == args.lesson), None)
    if lesson is None:
        print(f"Unknown lesson: {args.lesson}", file=sys.stderr)
        return EXIT_INVALID
    wanted = list(dict.fromkeys(args.variant or []))
    known = {v.name for v in lesson.variants}
    unknown = [name for name in wanted if name not in known]
    if unknown:
        print(f"Unknown variant of {lesson.id}: {', '.join(unknown)}", file=sys.stderr)
        return EXIT_INVALID
    names = [v.name for v in lesson.variants if not wanted or v.name in wanted]
    # The lab never uses the GPU: hide it before torch can initialise CUDA.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from gsm8k.lab import runner

    return runner.run_lesson(lesson, names, _outputs_root(args.outputs), args.threads)


def _threads(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {text!r}") from exc
    if not 1 <= value <= 8:
        raise argparse.ArgumentTypeError(f"threads must be from 1 to 8, got {value}")
    return value


def register(subparsers) -> None:
    lab = subparsers.add_parser(
        "lab",
        help="the fine-tuning lab: short CPU experiments on a very small model",
        description="List the lab lessons, or run one on the CPU (it never uses the GPU).",
    )
    lab_sub = lab.add_subparsers(dest="lab_command", required=True)
    listing = lab_sub.add_parser("list", help="print one line per lesson")
    listing.set_defaults(func=run_list)
    run = lab_sub.add_parser("run", help="run a lesson on the CPU")
    run.add_argument("lesson", help="lesson id, for example l01")
    run.add_argument("--variant", action="append", help="run only this variant (repeatable)")
    run.add_argument("--outputs", type=Path, help="outputs folder (default outputs/)")
    run.add_argument("--threads", type=_threads, help="CPU threads (default from the configuration)")
    run.set_defaults(func=run_run)
