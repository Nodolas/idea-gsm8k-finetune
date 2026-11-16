"""RunCommands: ``gsm8k course inspect`` (US12.2, contract C9).

This module imports no torch or transformers and sets no environment variable on import (``gsm8k``
imports every command module when it builds its parser). The handler hides the GPU first and loads
the inspection code only then. Exit 0 written, 1 a model could not be read (nothing written).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

EXIT_FINISHED = 0
EXIT_FAILED = 1


def _outputs_root(given: Path | None) -> Path:
    if given is not None:
        return Path(given)
    from gsm8k.run_records.paths import outputs_root

    return outputs_root()


def run_inspect(args: argparse.Namespace) -> int:
    # The inspection never uses the GPU: hide it before torch can initialise CUDA.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from gsm8k.course import inspect as course_inspect

    outputs = _outputs_root(args.outputs)
    try:
        path = course_inspect.write_architectures(outputs)
    except course_inspect.InspectError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILED
    print(f"Wrote {path}")
    return EXIT_FINISHED


def register(subparsers) -> None:
    course = subparsers.add_parser(
        "course",
        help="the learning course: model-design inspection",
        description="Read the design of the course's models (configuration and tokenizer only, on the CPU).",
    )
    course_sub = course.add_subparsers(dest="course_command", required=True)
    inspect_parser = course_sub.add_parser(
        "inspect", help="write outputs/course/architectures.json for the Course Models"
    )
    inspect_parser.add_argument("--outputs", type=Path, help="outputs folder (default outputs/)")
    inspect_parser.set_defaults(func=run_inspect)
